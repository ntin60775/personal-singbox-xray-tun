package parser

import (
	"net/url"
	"strings"
)

// Allowed query keys for VLESS links.
var vlessAllowedKeys = map[string]bool{
	"type":          true,
	"security":      true,
	"sni":           true,
	"serverName":    true,
	"host":          true,
	"path":          true,
	"serviceName":   true,
	"service_name":  true,
	"authority":     true,
	"fp":            true,
	"fingerprint":   true,
	"pbk":           true,
	"publicKey":     true,
	"sid":           true,
	"shortId":       true,
	"spx":           true,
	"spiderX":       true,
	"mode":          true,
	"extra":         true,
	"alpn":          true,
	"allowInsecure": true,
	"insecure":      true,
	"flow":          true,
	"encryption":    true,
}

// ParseVLESS parses a VLESS proxy URI.
//
// Format: vless://<uuid>@<host>:<port>?type=...&security=...&...#fragment
func ParseVLESS(rawURI string) (*ParsedNode, error) {
	u, err := url.Parse(rawURI)
	if err != nil {
		return nil, newParseError("VLESS-ссылка не является корректным URI.")
	}

	if u.User == nil || u.User.Username() == "" {
		return nil, newParseError("VLESS-ссылка должна содержать UUID, адрес и порт.")
	}
	if u.Hostname() == "" || u.Port() == "" {
		return nil, newParseError("VLESS-ссылка должна содержать UUID, адрес и порт.")
	}

	port, ok := isValidPort(u.Port())
	if !ok {
		return nil, newParseError("VLESS-ссылка должна содержать корректный порт.")
	}

	query := singleValueQuery(u.RawQuery)
	if err := ensureSupportedQueryKeys(query, vlessAllowedKeys); err != nil {
		return nil, err
	}

	encryption := strings.ToLower(strings.TrimSpace(query["encryption"]))
	if encryption == "" {
		encryption = "none"
	}
	if encryption != "none" {
		return nil, newParseError("Для VLESS поддерживается только encryption=none.")
	}

	fragment, _ := url.QueryUnescape(u.Fragment)

	node := &ParsedNode{
		Protocol:   "vless",
		Address:    u.Hostname(),
		Port:       port,
		UUID:       u.User.Username(),
		Encryption: "none",
		Flow:       strings.TrimSpace(query["flow"]),
		DisplayName: defaultName(fragment, "vless", u.Hostname(), port),
		RawURI:     strings.TrimSpace(rawURI),
	}
	stream, err := parseStreamCommon(query, "vless")
	if err != nil {
		return nil, err
	}
	applyStreamSettings(node, stream)

	return node, nil
}
