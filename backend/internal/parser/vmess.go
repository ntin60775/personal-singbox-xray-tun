package parser

import (
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
)

// ParseVMess parses a VMess proxy URI.
//
// Format: vmess://<base64-encoded-JSON>
func ParseVMess(rawURI string) (*ParsedNode, error) {
	body := strings.TrimSpace(rawURI[len("vmess://"):])
	if body == "" {
		return nil, newParseError("Vmess-ссылка не содержит данных.")
	}

	decoded, err := decodeBase64Text(body)
	if err != nil {
		return nil, newParseError("Vmess-ссылка содержит некорректный base64.")
	}

	var payload map[string]interface{}
	if err := json.Unmarshal([]byte(decoded), &payload); err != nil {
		return nil, newParseError("Vmess-конфигурация должна быть JSON-объектом.")
	}

	address := getStringField(payload, "add")
	portRaw := getStringField(payload, "port")
	userID := getStringField(payload, "id")

	if address == "" || !isNumeric(portRaw) || userID == "" {
		return nil, newParseError("Vmess-ссылка должна содержать add, port и id.")
	}

	port, _ := strconv.Atoi(strings.TrimSpace(portRaw))

	network := strings.ToLower(strings.TrimSpace(getStringField(payload, "net")))
	if network == "" {
		network = "tcp"
	}
	if !supportedVMessNetworks[network] {
		return nil, newParseErrorf("Неподдерживаемый transport '%s' для vmess.", network)
	}

	streamType := strings.ToLower(strings.TrimSpace(getStringField(payload, "type")))
	if streamType != "" && streamType != "none" {
		return nil, newParseErrorf("Неподдерживаемый header/type '%s' для vmess.", streamType)
	}

	security := strings.ToLower(strings.TrimSpace(getStringField(payload, "tls")))
	if security == "" {
		security = strings.ToLower(strings.TrimSpace(getStringField(payload, "security")))
	}
	if security == "" {
		security = "none"
	}
	if !supportedVMessSecurities[security] {
		return nil, newParseErrorf("Неподдерживаемая security '%s' для vmess.", security)
	}

	serviceName := ""
	path := strings.TrimSpace(getStringField(payload, "path"))
	if network == "grpc" {
		serviceName = strings.TrimPrefix(path, "/")
		if serviceName == "" {
			serviceName = strings.TrimSpace(getStringField(payload, "serviceName"))
		}
		if serviceName == "" {
			return nil, newParseError("Для vmess gRPC обязателен path/serviceName.")
		}
		path = ""
	} else if network == "ws" && path == "" {
		path = "/"
	}

	serverName := strings.TrimSpace(getStringField(payload, "sni"))
	if security == "tls" && serverName == "" {
		return nil, newParseError("Для TLS-vmess обязателен sni.")
	}

	aidRaw := strings.TrimSpace(getStringField(payload, "aid"))
	if aidRaw == "" {
		aidRaw = "0"
	}
	alterID, err := strconv.Atoi(aidRaw)
	if err != nil {
		return nil, newParseError("aid в vmess должен быть целым числом.")
	}

	cipher := strings.TrimSpace(getStringField(payload, "scy"))
	if cipher == "" {
		cipher = "auto"
	}

	displayName := strings.TrimSpace(getStringField(payload, "ps"))

	fingerprint := strings.TrimSpace(getStringField(payload, "fp"))

	node := &ParsedNode{
		Protocol:      "vmess",
		Address:       address,
		Port:          port,
		UUID:          userID,
		Network:       network,
		Security:      security,
		Host:          strings.TrimSpace(getStringField(payload, "host")),
		Path:          path,
		ServerName:    serverName,
		ServiceName:   serviceName,
		GRPCAuthority: strings.TrimSpace(getStringField(payload, "authority")),
		Fingerprint:   fingerprint,
		PublicKey:     "",
		ShortID:       "",
		SpiderX:       "/",
		Mode:          "auto",
		ALPN:          splitCSV(getStringField(payload, "alpn")),
		AllowInsecure: boolValue(getStringField(payload, "allowInsecure")),
		DisplayName:   defaultName(displayName, "vmess", address, port),
		RawURI:        strings.TrimSpace(rawURI),
	}

	// Suppress unused warnings (alter_id and cipher are part of the node identity
	// but not directly stored in ParsedNode; FingerprintPayload includes them via
	// the caller's map).
	_ = alterID
	_ = cipher

	return node, nil
}

func getStringField(m map[string]interface{}, key string) string {
	v, ok := m[key]
	if !ok {
		return ""
	}
	switch val := v.(type) {
	case string:
		return val
	case float64:
		if val == float64(int64(val)) {
			return fmt.Sprintf("%d", int64(val))
		}
		return fmt.Sprintf("%v", val)
	case json.Number:
		return val.String()
	default:
		return fmt.Sprintf("%v", val)
	}
}

func isNumeric(s string) bool {
	s = strings.TrimSpace(s)
	if s == "" {
		return false
	}
	_, err := strconv.Atoi(s)
	return err == nil
}
