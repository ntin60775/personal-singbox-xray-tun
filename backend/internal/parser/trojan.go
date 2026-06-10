package parser

import (
	"net/url"
	"strings"
)

// Allowed query keys for Trojan links.
var trojanAllowedKeys = map[string]bool{
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
}

// ParseTrojan parses a Trojan proxy URI.
//
// Format: trojan://<password>@<host>:<port>?type=...&security=...&...
func ParseTrojan(rawURI string) (*ParsedNode, error) {
	u, err := url.Parse(rawURI)
	if err != nil {
		return nil, newParseError("Trojan-ссылка не является корректным URI.")
	}

	if u.User == nil || u.User.Username() == "" {
		return nil, newParseError("Trojan-ссылка должна содержать пароль, адрес и порт.")
	}
	if u.Hostname() == "" || u.Port() == "" {
		return nil, newParseError("Trojan-ссылка должна содержать пароль, адрес и порт.")
	}

	port, ok := isValidPort(u.Port())
	if !ok {
		return nil, newParseError("Trojan-ссылка должна содержать корректный порт.")
	}

	query := singleValueQuery(u.RawQuery)
	if err := ensureSupportedQueryKeys(query, trojanAllowedKeys); err != nil {
		return nil, err
	}

	fragment, _ := url.QueryUnescape(u.Fragment)

	node := &ParsedNode{
		Protocol:    "trojan",
		Address:     u.Hostname(),
		Port:        port,
		Password:    u.User.Username(),
		DisplayName: defaultName(fragment, "trojan", u.Hostname(), port),
		RawURI:      strings.TrimSpace(rawURI),
	}

	stream, err := parseStreamCommon(query, "trojan")
	if err != nil {
		return nil, err
	}
	applyStreamSettings(node, stream)
	return node, nil
}
