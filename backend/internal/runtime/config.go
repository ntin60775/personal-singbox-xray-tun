package runtime

import (
	"encoding/json"
	"fmt"

	"github.com/subvost/xray-tun/backend/internal/domain"
)

// NodeCanRenderRuntime checks whether a node has enough data to produce a
// valid Xray runtime configuration.
func NodeCanRenderRuntime(node *domain.Node) bool {
	if node == nil {
		return false
	}
	n := node.Normalized
	if n.Protocol == "" || n.Address == "" || n.Port == 0 {
		return false
	}
	if node.ParseError != "" {
		return false
	}
	return node.Enabled
}

// RenderRuntimeConfig materializes a runtime Xray configuration by
// substituting the active node's proxy settings into the template.
// An optional routing overlay (partial Xray config JSON) is merged in.
func RenderRuntimeConfig(template []byte, node *domain.Node, routingOverlay []byte) ([]byte, error) {
	if !NodeCanRenderRuntime(node) {
		return nil, fmt.Errorf("active node cannot be materialized into a runtime config")
	}

	var config map[string]interface{}
	if err := json.Unmarshal(template, &config); err != nil {
		return nil, fmt.Errorf("parse template config: %w", err)
	}

	outbounds, ok := config["outbounds"].([]interface{})
	if !ok {
		return nil, fmt.Errorf("template config missing outbounds array")
	}

	replaced := false
	for i, ob := range outbounds {
		outbound, ok := ob.(map[string]interface{})
		if !ok {
			continue
		}
		if tag, _ := outbound["tag"].(string); tag == "proxy" {
			newOB, err := buildProxyOutbound(&node.Normalized, outbound)
			if err != nil {
				return nil, fmt.Errorf("build proxy outbound: %w", err)
			}
			outbounds[i] = newOB
			replaced = true
			break
		}
	}
	if !replaced {
		return nil, fmt.Errorf("no outbound with tag=proxy found in template config")
	}
	config["outbounds"] = outbounds

	// Merge optional routing overlay.
	if len(routingOverlay) > 0 {
		var overlay map[string]interface{}
		if err := json.Unmarshal(routingOverlay, &overlay); err != nil {
			return nil, fmt.Errorf("parse routing overlay: %w", err)
		}
		for _, section := range []string{"routing", "inbounds", "dns"} {
			if v, ok := overlay[section]; ok {
				config[section] = v
			}
		}
	}

	return json.MarshalIndent(config, "", "  ")
}

// buildProxyOutbound constructs an Xray outbound object from the
// normalized node data and inherits the tag from the template outbound.
func buildProxyOutbound(n *domain.NodeAddress, template map[string]interface{}) (map[string]interface{}, error) {
	tag := "proxy"
	if t, ok := template["tag"].(string); ok {
		tag = t
	}

	proto := n.Protocol
	if proto == "ss" {
		proto = "shadowsocks"
	}

	outbound := map[string]interface{}{
		"tag":      tag,
		"protocol": proto,
	}

	settings, err := buildProtocolSettings(n)
	if err != nil {
		return nil, err
	}
	outbound["settings"] = settings

	tplStream := map[string]interface{}{}
	if ts, ok := template["streamSettings"]; ok {
		if m, ok := ts.(map[string]interface{}); ok {
			tplStream = m
		}
	}
	outbound["streamSettings"] = buildStreamSettings(n, tplStream)

	return outbound, nil
}

// buildProtocolSettings builds the protocol-specific "settings" block.
func buildProtocolSettings(n *domain.NodeAddress) (map[string]interface{}, error) {
	switch n.Protocol {
	case "vless":
		user := map[string]interface{}{
			"id":         n.UUID,
			"encryption": n.Encryption,
		}
		if n.Encryption == "" {
			user["encryption"] = "none"
		}
		if n.Flow != "" {
			user["flow"] = n.Flow
		}
		return map[string]interface{}{
			"vnext": []interface{}{
				map[string]interface{}{
					"address": n.Address,
					"port":    n.Port,
					"users":   []interface{}{user},
				},
			},
		}, nil

	case "vmess":
		cipher := n.Cipher
		if cipher == "" {
			cipher = "auto"
		}
		return map[string]interface{}{
			"vnext": []interface{}{
				map[string]interface{}{
					"address": n.Address,
					"port":    n.Port,
					"users": []interface{}{
						map[string]interface{}{
							"id":       n.UUID,
							"alterId":  n.AlterID,
							"security": cipher,
						},
					},
				},
			},
		}, nil

	case "trojan":
		return map[string]interface{}{
			"servers": []interface{}{
				map[string]interface{}{
					"address":  n.Address,
					"port":     n.Port,
					"password": n.Password,
				},
			},
		}, nil

	case "ss":
		return map[string]interface{}{
			"servers": []interface{}{
				map[string]interface{}{
					"address":  n.Address,
					"port":     n.Port,
					"method":   n.Method,
					"password": n.Password,
				},
			},
		}, nil

	default:
		return nil, fmt.Errorf("unsupported protocol for runtime generation: %s", n.Protocol)
	}
}

// buildStreamSettings builds the streamSettings block for the outbound.
func buildStreamSettings(n *domain.NodeAddress, tplStream map[string]interface{}) map[string]interface{} {
	network := n.Network
	if network == "" {
		network = "tcp"
	}
	security := n.Security
	if security == "" {
		security = "none"
	}

	ss := map[string]interface{}{
		"network":  network,
		"security": security,
	}

	if sockopt, ok := tplStream["sockopt"]; ok {
		ss["sockopt"] = deepCopyMap(sockopt)
	}

	switch network {
	case "ws":
		wsSettings := map[string]interface{}{
			"path": n.Path,
		}
		if wsSettings["path"] == nil || wsSettings["path"] == "" {
			wsSettings["path"] = "/"
		}
		if n.Host != "" {
			wsSettings["headers"] = map[string]interface{}{
				"Host": n.Host,
			}
		}
		ss["wsSettings"] = wsSettings

	case "grpc":
		grpcSettings := map[string]interface{}{
			"serviceName": n.ServiceName,
		}
		if n.GRPCAuthority != "" {
			grpcSettings["authority"] = n.GRPCAuthority
		}
		ss["grpcSettings"] = grpcSettings

	case "xhttp":
		mode := n.Mode
		if mode == "" {
			mode = "auto"
		}
		xhttpSettings := map[string]interface{}{
			"host": n.Host,
			"path": n.Path,
			"mode": mode,
		}
		if xhttpSettings["path"] == nil || xhttpSettings["path"] == "" {
			xhttpSettings["path"] = "/"
		}
		if len(n.XhttpExtra) > 0 {
			var extra interface{}
			if json.Unmarshal(n.XhttpExtra, &extra) == nil {
				xhttpSettings["extra"] = extra
			}
		} else if tplXhttp, ok := tplStream["xhttpSettings"]; ok {
			if tplM, ok := tplXhttp.(map[string]interface{}); ok {
				if extra, ok := tplM["extra"]; ok {
					xhttpSettings["extra"] = deepCopyMap(extra)
				}
			}
		}
		ss["xhttpSettings"] = xhttpSettings
	}

	switch security {
	case "tls":
		tls := map[string]interface{}{
			"serverName": n.ServerName,
		}
		if len(n.ALPN) > 0 {
			tls["alpn"] = n.ALPN
		}
		if n.AllowInsecure {
			tls["allowInsecure"] = true
		}
		if n.Fingerprint != "" {
			tls["fingerprint"] = n.Fingerprint
		}
		ss["tlsSettings"] = tls

	case "reality":
		spiderX := n.SpiderX
		if spiderX == "" {
			spiderX = "/"
		}
		ss["realitySettings"] = map[string]interface{}{
			"serverName":  n.ServerName,
			"fingerprint": n.Fingerprint,
			"publicKey":   n.PublicKey,
			"shortId":     n.ShortID,
			"spiderX":     spiderX,
		}
	}

	return ss
}

// deepCopyMap returns a deep copy of a value parsed from JSON (map, slice, or scalar).
func deepCopyMap(v interface{}) interface{} {
	data, err := json.Marshal(v)
	if err != nil {
		return v
	}
	var out interface{}
	if err := json.Unmarshal(data, &out); err != nil {
		return v
	}
	return out
}

// ApplyTransportHints injects transport-level hints (interface binding, fwmark)
// into the runtime Xray configuration for the proxy and direct outbounds.
func ApplyTransportHints(config []byte, hint *domain.TransportHint) ([]byte, error) {
	if hint == nil || (hint.DefaultInterface == "" && hint.DefaultMark == 0) {
		return config, nil
	}

	var cfg map[string]interface{}
	if err := json.Unmarshal(config, &cfg); err != nil {
		return nil, fmt.Errorf("parse config for transport hints: %w", err)
	}

	outbounds, ok := cfg["outbounds"].([]interface{})
	if !ok {
		return config, nil
	}

	seen := map[string]bool{}
	for i, ob := range outbounds {
		outbound, ok := ob.(map[string]interface{})
		if !ok {
			continue
		}
		tag, _ := outbound["tag"].(string)
		if tag != "proxy" && tag != "direct" {
			continue
		}
		outbounds[i] = applyOutboundHints(outbound, hint)
		seen[tag] = true
	}

	missing := []string{}
	for _, tag := range []string{"proxy", "direct"} {
		if !seen[tag] {
			missing = append(missing, tag)
		}
	}
	if len(missing) > 0 {
		return nil, fmt.Errorf("required outbounds not found for transport hints: %v", missing)
	}

	cfg["outbounds"] = outbounds
	return json.MarshalIndent(cfg, "", "  ")
}

// applyOutboundHints patches a single outbound map with transport hints.
func applyOutboundHints(outbound map[string]interface{}, hint *domain.TransportHint) map[string]interface{} {
	data, _ := json.Marshal(outbound)
	var updated map[string]interface{}
	json.Unmarshal(data, &updated)

	streamSettings := map[string]interface{}{}
	if ss, ok := updated["streamSettings"]; ok {
		if m, ok := ss.(map[string]interface{}); ok {
			streamSettings = m
		}
	}

	sockopt := map[string]interface{}{}
	if so, ok := streamSettings["sockopt"]; ok {
		if m, ok := so.(map[string]interface{}); ok {
			sockopt = m
		}
	}

	if hint.DefaultInterface != "" {
		sockopt["interface"] = hint.DefaultInterface
	}
	if hint.DefaultMark > 0 {
		sockopt["mark"] = hint.DefaultMark
	}

	if len(sockopt) > 0 {
		streamSettings["sockopt"] = sockopt
	}
	updated["streamSettings"] = streamSettings

	return updated
}
