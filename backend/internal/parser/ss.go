package parser

import (
	"net/url"
	"strings"
)

// ParseShadowsocks parses a Shadowsocks proxy URI.
//
// Format 1 (legacy): ss://<base64(method:password@host:port)>#fragment
// Format 2 (SIP002): ss://<base64(method:password)>@<host>:<port>#fragment
// Format 3 (plain):  ss://method:password@host:port#fragment
func ParseShadowsocks(rawURI string) (*ParsedNode, error) {
	u, err := url.Parse(rawURI)
	if err != nil {
		return nil, newParseError("SS-ссылка не является корректным URI.")
	}

	// Reject SIP002 plugins
	query := singleValueQuery(u.RawQuery)
	plugin := strings.TrimSpace(query["plugin"])
	if plugin != "" {
		return nil, newParseError("SIP002 plugin для shadowsocks не поддерживается.")
	}

	// Strip scheme, fragment, and query to get the body.
	body := rawURI[len("ss://"):]
	if idx := strings.IndexByte(body, '#'); idx >= 0 {
		body = body[:idx]
	}
	if idx := strings.IndexByte(body, '?'); idx >= 0 {
		body = body[:idx]
	}

	var credentialPart, hostPortPart string
	decodeDirectUserinfo := false

	if idx := strings.LastIndex(body, "@"); idx >= 0 {
		credentialPart = body[:idx]
		hostPortPart = body[idx+1:]
		if !strings.Contains(credentialPart, ":") {
			// Legacy base64-encoded credential
			decoded, err := decodeBase64Text(credentialPart)
			if err != nil {
				return nil, newParseError("SS-ссылка содержит некорректный base64.")
			}
			credentialPart = decoded
		} else {
			// Plain method:password — will need percent-decoding
			decodeDirectUserinfo = true
		}
	} else {
		// Entire body is base64-encoded "method:password@host:port"
		decoded, err := decodeBase64Text(body)
		if err != nil {
			return nil, newParseError("SS-ссылка содержит некорректный base64.")
		}
		if idx := strings.LastIndex(decoded, "@"); idx < 0 {
			return nil, newParseError("Shadowsocks-ссылка не содержит host:port.")
		}
		credentialPart = decoded[:idx]
		hostPortPart = decoded[idx+1:]
	}

	if !strings.Contains(credentialPart, ":") {
		return nil, newParseError("Shadowsocks-ссылка не содержит method:password.")
	}

	colonIdx := strings.Index(credentialPart, ":")
	method := credentialPart[:colonIdx]
	password := credentialPart[colonIdx+1:]

	if decodeDirectUserinfo {
		m, err := url.QueryUnescape(method)
		if err != nil {
			return nil, newParseError("SS-ссылка содержит некорректный method.")
		}
		p, err := url.QueryUnescape(password)
		if err != nil {
			return nil, newParseError("SS-ссылка содержит некорректный password.")
		}
		method = m
		password = p
	}

	method = strings.TrimSpace(strings.ToLower(method))
	password = strings.TrimSpace(password)

	if method == "" || password == "" {
		return nil, newParseError("Shadowsocks-ссылка должна содержать method и password.")
	}
	if !SUPPORTED_SS_METHODS[method] {
		return nil, newParseErrorf("Неподдерживаемый shadowsocks method '%s'.", method)
	}

	// Parse host:port from authority
	authority := "ss://dummy@" + hostPortPart
	au, err := url.Parse(authority)
	if err != nil || au.Hostname() == "" || au.Port() == "" {
		return nil, newParseError("Shadowsocks-ссылка должна содержать адрес и порт.")
	}

	port, ok := isValidPort(au.Port())
	if !ok {
		return nil, newParseError("Shadowsocks-ссылка должна содержать корректный порт.")
	}

	fragment, _ := url.QueryUnescape(u.Fragment)

	node := &ParsedNode{
		Protocol:    "ss",
		Address:     au.Hostname(),
		Port:        port,
		Method:      method,
		Password:    password,
		Network:     "tcp",
		Security:    "none",
		SpiderX:     "/",
		Mode:        "auto",
		DisplayName: defaultName(fragment, "ss", au.Hostname(), port),
		RawURI:      strings.TrimSpace(rawURI),
	}
	return node, nil
}
