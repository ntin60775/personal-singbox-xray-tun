package routing

import (
	"encoding/json"
	"fmt"
	"strings"

	"github.com/subvost/xray-tun/backend/internal/domain"
)

// ApplyRoutingProfileToConfig modifies an Xray configuration JSON by applying
// routing rules derived from a RoutingProfile. It returns the modified config bytes.
func ApplyRoutingProfileToConfig(xrayConfig []byte, rp *domain.RoutingProfile) ([]byte, error) {
	if rp == nil {
		return nil, fmt.Errorf("routing profile is nil")
	}

	var config map[string]interface{}
	if err := json.Unmarshal(xrayConfig, &config); err != nil {
		return nil, fmt.Errorf("parsing xray config: %w", err)
	}

	// Deep copy to avoid mutating the original.
	updated := deepCopyConfig(config)

	// Extract the routing section.
	routing, _ := updated["routing"].(map[string]interface{})
	if routing == nil {
		routing = make(map[string]interface{})
		updated["routing"] = routing
	}

	// Split template rules: everything before the catchall (tun-in, tcp,udp).
	baseRules, templateCatchall := splitTemplateRules(updated)

	// Build imported rules from the routing profile.
	importedRules := buildProfileRules(rp)

	// Determine catchall action.
	catchall := templateCatchall
	if catchall == nil {
		catchall = map[string]interface{}{
			"type":        "field",
			"inboundTag":  []interface{}{"tun-in"},
			"network":     "tcp,udp",
			"outboundTag": "proxy",
		}
	}
	if rp.GlobalProxy {
		catchall["outboundTag"] = "proxy"
	} else {
		catchall["outboundTag"] = "direct"
	}

	// Set domain strategy.
	domainStrategy := strings.TrimSpace(rp.DomainStrategy)
	if domainStrategy == "" {
		domainStrategy = coerceString(routing["domainStrategy"], "AsIs")
	}
	routing["domainStrategy"] = domainStrategy

	// Assemble rules: base + imported + catchall.
	allRules := make([]interface{}, 0, len(baseRules)+len(importedRules)+1)
	for _, r := range baseRules {
		allRules = append(allRules, r)
	}
	for _, r := range importedRules {
		allRules = append(allRules, r)
	}
	allRules = append(allRules, catchall)
	routing["rules"] = allRules

	result, err := json.Marshal(updated)
	if err != nil {
		return nil, fmt.Errorf("marshaling xray config: %w", err)
	}
	return result, nil
}

// splitTemplateRules separates the TUN catchall rule (the last rule with inboundTag ["tun-in"]
// and network "tcp,udp") from the preceding rules.
func splitTemplateRules(config map[string]interface{}) ([]interface{}, map[string]interface{}) {
	routing, _ := config["routing"].(map[string]interface{})
	if routing == nil {
		return nil, nil
	}
	rulesRaw, _ := routing["rules"].([]interface{})
	if rulesRaw == nil {
		return nil, nil
	}

	for i := len(rulesRaw) - 1; i >= 0; i-- {
		rule, ok := rulesRaw[i].(map[string]interface{})
		if !ok {
			continue
		}
		if isTunCatchallRule(rule) {
			baseRules := make([]interface{}, i)
			for j := 0; j < i; j++ {
				baseRules[j] = deepCopyInterface(rulesRaw[j])
			}
			catchall := deepCopyMapString(rule)
			return baseRules, catchall
		}
	}

	// No catchall found: all rules are base rules.
	baseRules := make([]interface{}, len(rulesRaw))
	for j, r := range rulesRaw {
		baseRules[j] = deepCopyInterface(r)
	}
	return baseRules, nil
}

// buildProfileRules creates Xray routing rules from a RoutingProfile's direct/proxy/block entries.
func buildProfileRules(rp *domain.RoutingProfile) []interface{} {
	routeOrder := rp.RouteOrder
	if len(routeOrder) == 0 {
		routeOrder = []string{"block", "direct", "proxy"}
	}

	var rules []interface{}

	for _, prefix := range routeOrder {
		var outboundTag string
		switch prefix {
		case "block":
			outboundTag = "block"
		case "direct":
			outboundTag = "direct"
		case "proxy":
			outboundTag = "proxy"
		default:
			continue
		}

		rule := buildProfileRule(rp, prefix, outboundTag)
		if rule != nil {
			rules = append(rules, rule)
		}
	}
	return rules
}

// buildProfileRule creates a single Xray routing rule for a given policy prefix.
func buildProfileRule(rp *domain.RoutingProfile, prefix, outboundTag string) map[string]interface{} {
	var domains, ips []string
	switch prefix {
	case "block":
		domains, ips = rp.BlockSites, rp.BlockIP
	case "direct":
		domains, ips = rp.DirectSites, rp.DirectIP
	case "proxy":
		domains, ips = rp.ProxySites, rp.ProxyIP
	}

	if len(domains) == 0 && len(ips) == 0 {
		return nil
	}

	rule := map[string]interface{}{
		"type":        "field",
		"inboundTag":  []interface{}{"tun-in"},
		"outboundTag": outboundTag,
	}
	if len(domains) > 0 {
		rule["domain"] = stringSliceToInterface(domains)
	}
	if len(ips) > 0 {
		rule["ip"] = stringSliceToInterface(ips)
	}
	return rule
}

// stringSliceToInterface converts []string to []interface{} for JSON marshaling.
func stringSliceToInterface(s []string) []interface{} {
	result := make([]interface{}, len(s))
	for i, v := range s {
		result[i] = v
	}
	return result
}

// deepCopyConfig performs a deep copy of a JSON-like config map.
func deepCopyConfig(src map[string]interface{}) map[string]interface{} {
	dst := make(map[string]interface{}, len(src))
	for k, v := range src {
		dst[k] = deepCopyValue(v)
	}
	return dst
}

func deepCopyValue(value interface{}) interface{} {
	switch v := value.(type) {
	case map[string]interface{}:
		return deepCopyMapString(v)
	case []interface{}:
		return deepCopySlice(v)
	default:
		return v
	}
}

func deepCopyMapString(src map[string]interface{}) map[string]interface{} {
	dst := make(map[string]interface{}, len(src))
	for k, v := range src {
		dst[k] = deepCopyValue(v)
	}
	return dst
}

func deepCopySlice(src []interface{}) []interface{} {
	dst := make([]interface{}, len(src))
	for i, v := range src {
		dst[i] = deepCopyValue(v)
	}
	return dst
}

// deepCopyInterface deep-copies an arbitrary JSON-like value.
func deepCopyInterface(value interface{}) interface{} {
	return deepCopyValue(value)
}
