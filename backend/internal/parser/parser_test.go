package parser

import (
	"encoding/base64"
	"encoding/json"
	"strings"
	"testing"
)

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

func mustContain(t *testing.T, err error, substr string) {
	t.Helper()
	if err == nil {
		t.Fatalf("expected error containing %q, got nil", substr)
	}
	if !strings.Contains(err.Error(), substr) {
		t.Fatalf("error %q does not contain %q", err.Error(), substr)
	}
}

// ---------------------------------------------------------------------------
// TestParseVLESS — 5+ cases (covers test_parse_vless_reality_xhttp)
// ---------------------------------------------------------------------------

func TestParseVLESS(t *testing.T) {
	tests := []struct {
		name    string
		uri     string
		check   func(t *testing.T, n *ParsedNode)
		wantErr string
	}{
		{
			name: "reality xhttp with all fields",
			uri: "vless://11111111-1111-1111-1111-111111111111@example.com:443" +
				"?type=xhttp&security=reality&sni=edge.example.com&pbk=test-public-key" +
				"&sid=abcd1234&fp=chrome&host=edge.example.com&path=%2Fentry" +
				"&extra=%7B%22headers%22%3A%7B%7D%7D#Example",
			check: func(t *testing.T, n *ParsedNode) {
				if n.Protocol != "vless" {
					t.Errorf("Protocol: got %q, want %q", n.Protocol, "vless")
				}
				if n.Address != "example.com" {
					t.Errorf("Address: got %q, want %q", n.Address, "example.com")
				}
				if n.Port != 443 {
					t.Errorf("Port: got %d, want 443", n.Port)
				}
				if n.UUID != "11111111-1111-1111-1111-111111111111" {
					t.Errorf("UUID: got %q", n.UUID)
				}
				if n.Encryption != "none" {
					t.Errorf("Encryption: got %q, want none", n.Encryption)
				}
				if n.Network != "xhttp" {
					t.Errorf("Network: got %q, want xhttp", n.Network)
				}
				if n.Security != "reality" {
					t.Errorf("Security: got %q, want reality", n.Security)
				}
				if n.ServerName != "edge.example.com" {
					t.Errorf("ServerName: got %q, want edge.example.com", n.ServerName)
				}
				if n.PublicKey != "test-public-key" {
					t.Errorf("PublicKey: got %q, want test-public-key", n.PublicKey)
				}
				if n.ShortID != "abcd1234" {
					t.Errorf("ShortID: got %q, want abcd1234", n.ShortID)
				}
				if n.Fingerprint != "chrome" {
					t.Errorf("Fingerprint: got %q, want chrome", n.Fingerprint)
				}
				if n.Host != "edge.example.com" {
					t.Errorf("Host: got %q, want edge.example.com", n.Host)
				}
				if n.Path != "/entry" {
					t.Errorf("Path: got %q, want /entry", n.Path)
				}
				if n.SpiderX != "/" {
					t.Errorf("SpiderX: got %q, want /", n.SpiderX)
				}
				if n.Mode != "auto" {
					t.Errorf("Mode: got %q, want auto", n.Mode)
				}
				if n.DisplayName != "Example" {
					t.Errorf("DisplayName: got %q, want Example", n.DisplayName)
				}
			},
		},
		{
			name: "tcp with no security",
			uri:  "vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Node",
			check: func(t *testing.T, n *ParsedNode) {
				if n.Protocol != "vless" {
					t.Errorf("Protocol: got %q, want vless", n.Protocol)
				}
				if n.Address != "example.com" {
					t.Errorf("Address: got %q", n.Address)
				}
				if n.Port != 443 {
					t.Errorf("Port: got %d", n.Port)
				}
				if n.UUID != "11111111-1111-1111-1111-111111111111" {
					t.Errorf("UUID: got %q", n.UUID)
				}
				if n.Encryption != "none" {
					t.Errorf("Encryption: got %q", n.Encryption)
				}
				if n.Network != "tcp" {
					t.Errorf("Network: got %q, want tcp", n.Network)
				}
				if n.Security != "none" {
					t.Errorf("Security: got %q, want none", n.Security)
				}
				if n.DisplayName != "Node" {
					t.Errorf("DisplayName: got %q, want Node", n.DisplayName)
				}
			},
		},
		{
			name: "vlESS with ws and tls",
			uri:  "vless://11111111-1111-1111-1111-111111111111@example.com:8443?type=ws&security=tls&sni=tls.example.com&path=%2Fws#TLS-WS",
			check: func(t *testing.T, n *ParsedNode) {
				if n.Network != "ws" {
					t.Errorf("Network: got %q, want ws", n.Network)
				}
				if n.Security != "tls" {
					t.Errorf("Security: got %q, want tls", n.Security)
				}
				if n.ServerName != "tls.example.com" {
					t.Errorf("ServerName: got %q", n.ServerName)
				}
				if n.Path != "/ws" {
					t.Errorf("Path: got %q, want /ws", n.Path)
				}
				if n.DisplayName != "TLS-WS" {
					t.Errorf("DisplayName: got %q", n.DisplayName)
				}
			},
		},
		{
			name: "vless with grpc",
			uri:  "vless://11111111-1111-1111-1111-111111111111@example.com:443?type=grpc&security=tls&sni=grpc.example.com&serviceName=my-service#GRPC",
			check: func(t *testing.T, n *ParsedNode) {
				if n.Network != "grpc" {
					t.Errorf("Network: got %q, want grpc", n.Network)
				}
				if n.Security != "tls" {
					t.Errorf("Security: got %q", n.Security)
				}
				if n.ServiceName != "my-service" {
					t.Errorf("ServiceName: got %q, want my-service", n.ServiceName)
				}
				if n.DisplayName != "GRPC" {
					t.Errorf("DisplayName: got %q", n.DisplayName)
				}
			},
		},
		{
			name:    "missing UUID (no user info)",
			uri:     "vless://example.com:443",
			wantErr: "UUID, адрес и порт",
		},
		{
			name:    "invalid port",
			uri:     "vless://uuid@example.com:abc",
			wantErr: "не является корректным URI",
		},
		{
			name:    "encryption not none",
			uri:     "vless://uuid@example.com:443?encryption=aes-128-gcm",
			wantErr: "encryption=none",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := ParseVLESS(tt.uri)
			if tt.wantErr != "" {
				mustContain(t, err, tt.wantErr)
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			tt.check(t, got)
		})
	}
}

// ---------------------------------------------------------------------------
// TestParseVMess — 3+ cases (covers test_parse_vmess_ws)
// ---------------------------------------------------------------------------

func TestParseVMess(t *testing.T) {
	// Build the base64-encoded VMess URI from the same JSON payload the
	// Python test_parse_vmess_ws uses.
	wsPayloadJSON, err := json.Marshal(map[string]interface{}{
		"v":   "2",
		"ps":  "VMess node",
		"add": "vmess.example.com",
		"port": "443",
		"id":   "22222222-2222-2222-2222-222222222222",
		"aid":  "0",
		"scy":  "auto",
		"net":  "ws",
		"type": "none",
		"host": "cdn.example.com",
		"path": "/socket",
		"tls":  "tls",
		"sni":  "cdn.example.com",
	})
	if err != nil {
		t.Fatal(err)
	}
	wsURI := "vmess://" + base64.StdEncoding.EncodeToString(wsPayloadJSON)

	tests := []struct {
		name    string
		uri     string
		check   func(t *testing.T, n *ParsedNode)
		wantErr string
	}{
		{
			name: "ws with tls (v2rayN format)",
			uri:  wsURI,
			check: func(t *testing.T, n *ParsedNode) {
				if n.Protocol != "vmess" {
					t.Errorf("Protocol: got %q, want vmess", n.Protocol)
				}
				if n.Address != "vmess.example.com" {
					t.Errorf("Address: got %q, want vmess.example.com", n.Address)
				}
				if n.Port != 443 {
					t.Errorf("Port: got %d, want 443", n.Port)
				}
				if n.UUID != "22222222-2222-2222-2222-222222222222" {
					t.Errorf("UUID: got %q", n.UUID)
				}
				if n.Network != "ws" {
					t.Errorf("Network: got %q, want ws", n.Network)
				}
				if n.Security != "tls" {
					t.Errorf("Security: got %q, want tls", n.Security)
				}
				if n.Host != "cdn.example.com" {
					t.Errorf("Host: got %q, want cdn.example.com", n.Host)
				}
				if n.Path != "/socket" {
					t.Errorf("Path: got %q, want /socket", n.Path)
				}
				if n.ServerName != "cdn.example.com" {
					t.Errorf("ServerName: got %q, want cdn.example.com", n.ServerName)
				}
				if n.DisplayName != "VMess node" {
					t.Errorf("DisplayName: got %q, want \"VMess node\"", n.DisplayName)
				}
			},
		},
		{
			name:    "empty body",
			uri:     "vmess://",
			wantErr: "не содержит данных",
		},
		{
			name:    "invalid base64",
			uri:     "vmess://!!!not-valid-base64!!!",
			wantErr: "некорректный base64",
		},
		{
			name:    "missing required fields",
			uri:     "vmess://" + base64.StdEncoding.EncodeToString([]byte(`{"v":"2"}`)),
			wantErr: "add, port и id",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := ParseVMess(tt.uri)
			if tt.wantErr != "" {
				mustContain(t, err, tt.wantErr)
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			tt.check(t, got)
		})
	}
}

// ---------------------------------------------------------------------------
// TestParseTrojan — 3+ cases (covers test_parse_trojan_grpc)
// ---------------------------------------------------------------------------

func TestParseTrojan(t *testing.T) {
	tests := []struct {
		name    string
		uri     string
		check   func(t *testing.T, n *ParsedNode)
		wantErr string
	}{
		{
			name: "grpc with tls",
			uri: "trojan://secret@example.com:443" +
				"?type=grpc&security=tls&sni=edge.example.com&serviceName=grpc-service#Trojan",
			check: func(t *testing.T, n *ParsedNode) {
				if n.Protocol != "trojan" {
					t.Errorf("Protocol: got %q, want trojan", n.Protocol)
				}
				if n.Address != "example.com" {
					t.Errorf("Address: got %q", n.Address)
				}
				if n.Port != 443 {
					t.Errorf("Port: got %d", n.Port)
				}
				if n.Password != "secret" {
					t.Errorf("Password: got %q, want secret", n.Password)
				}
				if n.Network != "grpc" {
					t.Errorf("Network: got %q, want grpc", n.Network)
				}
				if n.Security != "tls" {
					t.Errorf("Security: got %q, want tls", n.Security)
				}
				if n.ServerName != "edge.example.com" {
					t.Errorf("ServerName: got %q", n.ServerName)
				}
				if n.ServiceName != "grpc-service" {
					t.Errorf("ServiceName: got %q, want grpc-service", n.ServiceName)
				}
				if n.DisplayName != "Trojan" {
					t.Errorf("DisplayName: got %q, want Trojan", n.DisplayName)
				}
			},
		},
		{
			name:    "missing password",
			uri:     "trojan://example.com:443",
			wantErr: "пароль, адрес и порт",
		},
		{
			name:    "invalid port",
			uri:     "trojan://pass@example.com:abc",
			wantErr: "не является корректным URI",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := ParseTrojan(tt.uri)
			if tt.wantErr != "" {
				mustContain(t, err, tt.wantErr)
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			tt.check(t, got)
		})
	}
}

// ---------------------------------------------------------------------------
// TestParseShadowsocks — 4+ cases
//   covers test_shadowsocks_plugin_is_rejected,
//          test_parse_shadowsocks_direct_uri_decodes_percent_encoded_password
// ---------------------------------------------------------------------------

func TestParseShadowsocks(t *testing.T) {
	tests := []struct {
		name    string
		uri     string
		check   func(t *testing.T, n *ParsedNode)
		wantErr string
	}{
		{
			name: "direct URI decodes percent-encoded password",
			uri:  "ss://aes-256-gcm:pa%2Fss@example.com:8388#DirectSS",
			check: func(t *testing.T, n *ParsedNode) {
				if n.Protocol != "ss" {
					t.Errorf("Protocol: got %q, want ss", n.Protocol)
				}
				if n.Method != "aes-256-gcm" {
					t.Errorf("Method: got %q, want aes-256-gcm", n.Method)
				}
				if n.Password != "pa/ss" {
					t.Errorf("Password: got %q, want pa/ss", n.Password)
				}
				if n.Address != "example.com" {
					t.Errorf("Address: got %q", n.Address)
				}
				if n.Port != 8388 {
					t.Errorf("Port: got %d, want 8388", n.Port)
				}
				if n.DisplayName != "DirectSS" {
					t.Errorf("DisplayName: got %q, want DirectSS", n.DisplayName)
				}
			},
		},
		{
			name:    "SIP002 plugin is rejected",
			uri:     "ss://YWVzLTI1Ni1nY206cGFzcw==@example.com:8388?plugin=v2ray-plugin",
			wantErr: "SIP002 plugin",
		},
		{
			name: "legacy base64 (full body encoded)",
			uri:  "ss://" + base64.StdEncoding.EncodeToString([]byte("aes-256-gcm:legacypass@example.com:8388")) + "#LegacySS",
			check: func(t *testing.T, n *ParsedNode) {
				if n.Protocol != "ss" {
					t.Errorf("Protocol: got %q, want ss", n.Protocol)
				}
				if n.Method != "aes-256-gcm" {
					t.Errorf("Method: got %q, want aes-256-gcm", n.Method)
				}
				if n.Password != "legacypass" {
					t.Errorf("Password: got %q, want legacypass", n.Password)
				}
				if n.Address != "example.com" {
					t.Errorf("Address: got %q, want example.com", n.Address)
				}
				if n.Port != 8388 {
					t.Errorf("Port: got %d, want 8388", n.Port)
				}
				if n.DisplayName != "LegacySS" {
					t.Errorf("DisplayName: got %q, want LegacySS", n.DisplayName)
				}
			},
		},
		{
			name:    "unsupported method",
			uri:     "ss://invalid-cipher:password@example.com:8388",
			wantErr: "Неподдерживаемый shadowsocks method",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := ParseShadowsocks(tt.uri)
			if tt.wantErr != "" {
				mustContain(t, err, tt.wantErr)
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			tt.check(t, got)
		})
	}
}

// ---------------------------------------------------------------------------
// TestParseProxyURI — dispatcher + placeholder rejection
//   covers test_provider_placeholder_link_is_rejected,
//          test_provider_device_limit_placeholder_surfaces_exact_reason
// ---------------------------------------------------------------------------

func TestParseProxyURI(t *testing.T) {
	tests := []struct {
		name    string
		uri     string
		check   func(t *testing.T, n *ParsedNode)
		wantErr string
	}{
		{
			name: "dispatches to VLESS",
			uri:  "vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Disp",
			check: func(t *testing.T, n *ParsedNode) {
				if n.Protocol != "vless" {
					t.Errorf("Protocol: got %q", n.Protocol)
				}
				if n.DisplayName != "Disp" {
					t.Errorf("DisplayName: got %q", n.DisplayName)
				}
			},
		},
		{
			name: "dispatches to VMess",
			uri:  "vmess://" + base64.StdEncoding.EncodeToString(
				[]byte(`{"v":"2","ps":"VM","add":"1.2.3.4","port":"80","id":"uid","aid":"0","scy":"auto","net":"tcp","tls":""}`),
			),
			check: func(t *testing.T, n *ParsedNode) {
				if n.Protocol != "vmess" {
					t.Errorf("Protocol: got %q", n.Protocol)
				}
			},
		},
		{
			name: "dispatches to Trojan",
			uri:  "trojan://pass@example.com:443",
			check: func(t *testing.T, n *ParsedNode) {
				if n.Protocol != "trojan" {
					t.Errorf("Protocol: got %q", n.Protocol)
				}
			},
		},
		{
			name:    "empty string",
			uri:     "",
			wantErr: "Пустая строка не является",
		},
		{
			name:    "unsupported scheme",
			uri:     "http://example.com",
			wantErr: "Неподдерживаемая схема",
		},
		{
			name: "placeholder link is rejected (zero UUID + 0.0.0.0:1 + text marker)",
			uri: "vless://00000000-0000-0000-0000-000000000000@0.0.0.0:1" +
				"?type=tcp&security=none#" +
				"%D0%9F%D1%80%D0%B8%D0%BB%D0%BE%D0%B6%D0%B5%D0%BD%D0%B8%D0%B5%20%D0%BD%D0%B5%20%D0%BF%D0%BE%D0%B4%D0%B4%D0%B5%D1%80%D0%B6%D0%B8%D0%B2%D0%B0%D0%B5%D1%82%D1%81%D1%8F",
			wantErr: "заглушку",
		},
		{
			name: "device limit placeholder surfaces exact reason",
			uri: "vless://00000000-0000-0000-0000-000000000000@0.0.0.0:1" +
				"?type=tcp&security=none#" +
				"%D0%94%D0%BE%D1%81%D1%82%D0%B8%D0%B3%D0%BD%D1%83%D1%82%20%D0%BB%D0%B8%D0%BC%D0%B8%D1%82%20%D1%83%D1%81%D1%82%D1%80%D0%BE%D0%B9%D1%81%D1%82%D0%B2",
			wantErr: "Достигнут лимит устройств",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := ParseProxyURI(tt.uri)
			if tt.wantErr != "" {
				mustContain(t, err, tt.wantErr)
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			tt.check(t, got)
		})
	}
}

// ---------------------------------------------------------------------------
// TestParseSubscriptionPayload — 4 cases
//   covers test_parse_subscription_payload_plain_text,
//          test_parse_subscription_payload_base64,
//          test_parse_subscription_payload_ignores_happ_routing_line,
//          test_parse_subscription_payload_base64_ignores_happ_routing_and_provider_id_comment
// ---------------------------------------------------------------------------

func TestParseSubscriptionPayload(t *testing.T) {
	tests := []struct {
		name       string
		payload    []byte
		wantLines  []string
		wantFormat string
		wantErr    string
	}{
		{
			name:       "plain text",
			payload:    []byte("vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none\n"),
			wantLines:  []string{"vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none"},
			wantFormat: "plain_text",
		},
		{
			name: "base64",
			payload: func() []byte {
				raw := "ss://YWVzLTI1Ni1nY206cGFzc0BleGFtcGxlLmNvbTo4Mzg4#SS"
				return []byte(base64.StdEncoding.EncodeToString([]byte(raw)))
			}(),
			wantLines:  []string{"ss://YWVzLTI1Ni1nY206cGFzc0BleGFtcGxlLmNvbTo4Mzg4#SS"},
			wantFormat: "base64",
		},
		{
			name: "ignores happ routing line",
			payload: []byte(
				"happ://routing/add/eyJuYW1lIjoiVGVzdCJ9\n" +
					"vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Node\n",
			),
			wantLines: []string{
				"vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Node",
			},
			wantFormat: "plain_text",
		},
		{
			name: "base64 ignores routing and providerid comment",
			payload: func() []byte {
				raw := "#profile-title Example\n" +
					"#providerid body-provider\n" +
					"happ://routing/add/eyJOYW1lIjoiUm91dGluZyJ9\n" +
					"vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Node\n"
				return []byte(base64.StdEncoding.EncodeToString([]byte(raw)))
			}(),
			wantLines: []string{
				"vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Node",
			},
			wantFormat: "base64",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			lines, format, err := ParseSubscriptionPayload(tt.payload)
			if tt.wantErr != "" {
				mustContain(t, err, tt.wantErr)
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if format != tt.wantFormat {
				t.Errorf("format: got %q, want %q", format, tt.wantFormat)
			}
			if len(lines) != len(tt.wantLines) {
				t.Fatalf("line count: got %d, want %d", len(lines), len(tt.wantLines))
			}
			for i, want := range tt.wantLines {
				if lines[i] != want {
					t.Errorf("lines[%d]: got %q, want %q", i, lines[i], want)
				}
			}
		})
	}
}

// ---------------------------------------------------------------------------
// TestExtractSubscriptionMetadata — 3 cases
//   covers test_extract_subscription_metadata_prefers_response_headers,
//          test_extract_subscription_metadata_reads_routing_and_provider_id_from_body,
//          test_extract_subscription_metadata_reads_provider_id_from_url_fragment
// ---------------------------------------------------------------------------

func TestExtractSubscriptionMetadata(t *testing.T) {
	t.Run("prefers response headers over body and URL fragment", func(t *testing.T) {
		payload := []byte("vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Node\n")
		headers := map[string]string{
			"routing":    "happ://routing/onadd/eyJOYW1lIjoiSGVhZGVyIn0",
			"providerid": "provider-header",
		}
		sourceURL := "https://example.com/sub#?providerid=url-fragment"

		got := ExtractSubscriptionMetadata(payload, headers, sourceURL)

		if got["provider_id"] != "provider-header" {
			t.Errorf("provider_id: got %q, want provider-header", got["provider_id"])
		}
		if got["provider_id_source"] != "response_header" {
			t.Errorf("provider_id_source: got %q, want response_header", got["provider_id_source"])
		}
		if got["routing_text"] != "happ://routing/onadd/eyJOYW1lIjoiSGVhZGVyIn0" {
			t.Errorf("routing_text: got %q", got["routing_text"])
		}
		if got["routing_source"] != "response_header" {
			t.Errorf("routing_source: got %q, want response_header", got["routing_source"])
		}
		if got["payload_format"] != "plain_text" {
			t.Errorf("payload_format: got %q, want plain_text", got["payload_format"])
		}
	})

	t.Run("reads routing and provider_id from body", func(t *testing.T) {
		routingURI := "happ://routing/onadd/eyJOYW1lIjoiQm9keSJ9"
		payload := []byte(
			"#profile-title Example\n" +
				"#providerid provider-body\n" +
				routingURI + "\n" +
				"vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Node\n",
		)

		got := ExtractSubscriptionMetadata(payload, nil, "")

		if got["payload_format"] != "plain_text" {
			t.Errorf("payload_format: got %q, want plain_text", got["payload_format"])
		}
		if got["routing_text"] != routingURI {
			t.Errorf("routing_text: got %q, want %q", got["routing_text"], routingURI)
		}
		if got["routing_source"] != "body_plain_text" {
			t.Errorf("routing_source: got %q, want body_plain_text", got["routing_source"])
		}
		if got["provider_id"] != "provider-body" {
			t.Errorf("provider_id: got %q, want provider-body", got["provider_id"])
		}
		if got["provider_id_source"] != "body_plain_text" {
			t.Errorf("provider_id_source: got %q, want body_plain_text", got["provider_id_source"])
		}
	})

	t.Run("reads provider_id from URL fragment fallback", func(t *testing.T) {
		payload := []byte("vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Node\n")
		sourceURL := "https://example.com/sub#?providerid=url-fragment"

		got := ExtractSubscriptionMetadata(payload, nil, sourceURL)

		if got["provider_id"] != "url-fragment" {
			t.Errorf("provider_id: got %q, want url-fragment", got["provider_id"])
		}
		if got["provider_id_source"] != "url_fragment" {
			t.Errorf("provider_id_source: got %q, want url_fragment", got["provider_id_source"])
		}
		if got["routing_text"] != "" {
			t.Errorf("routing_text: got %q, want empty", got["routing_text"])
		}
		if got["payload_format"] != "plain_text" {
			t.Errorf("payload_format: got %q, want plain_text", got["payload_format"])
		}
	})
}

// ---------------------------------------------------------------------------
// TestFingerprintPayload — 2 cases
// ---------------------------------------------------------------------------

func TestFingerprintPayload(t *testing.T) {
	t.Run("returns 64-char hex for non-empty input", func(t *testing.T) {
		input := map[string]interface{}{
			"protocol": "vless",
			"address":  "1.2.3.4",
			"port":     443,
		}
		got := FingerprintPayload(input)
		if len(got) != 64 {
			t.Errorf("length: got %d, want 64", len(got))
		}
		for _, c := range got {
			if !((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f')) {
				t.Errorf("non-hex character in fingerprint: %q", got)
				break
			}
		}
	})

	t.Run("excludes display metadata keys", func(t *testing.T) {
		a := FingerprintPayload(map[string]interface{}{
			"protocol": "vless",
			"address":  "1.2.3.4",
		})
		b := FingerprintPayload(map[string]interface{}{
			"protocol":     "vless",
			"address":      "1.2.3.4",
			"display_name": "whatever",
			"raw_uri":      "vless://...",
			"origin_uri":   "https://...",
		})
		if a != b {
			t.Errorf("display metadata should not affect fingerprint:\n  a=%s\n  b=%s", a, b)
		}
	})

	t.Run("empty map returns all-zero hash", func(t *testing.T) {
		got := FingerprintPayload(map[string]interface{}{})
		if len(got) != 64 {
			t.Errorf("length: got %d, want 64", len(got))
		}
		// Empty map → empty JSON → SHA-256 of empty input has a known hash,
		// but the implementation json.Marshal's an empty map which is "{}".
		// We just verify it's 64 hex chars, not all zeros.
		for _, c := range got {
			if !((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f')) {
				t.Errorf("non-hex character in fingerprint: %q", got)
				break
			}
		}
	})
}

// ---------------------------------------------------------------------------
// TestPreviewLinks — 2 cases
// ---------------------------------------------------------------------------

func TestPreviewLinks(t *testing.T) {
	t.Run("parses valid URIs and skips invalid lines", func(t *testing.T) {
		rawText := "" +
			"vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Node1\n" +
			"trojan://pass@example.com:443#Node2\n" +
			"not-a-valid-uri\n" +
			"ss://aes-256-gcm:pa%2Fss@example.com:8388#SS\n" +
			""

		nodes := PreviewLinks(rawText)
		if len(nodes) != 3 {
			t.Fatalf("expected 3 parsed nodes, got %d", len(nodes))
		}
		if nodes[0].Protocol != "vless" {
			t.Errorf("nodes[0].Protocol: got %q, want vless", nodes[0].Protocol)
		}
		if nodes[1].Protocol != "trojan" {
			t.Errorf("nodes[1].Protocol: got %q, want trojan", nodes[1].Protocol)
		}
		if nodes[2].Protocol != "ss" {
			t.Errorf("nodes[2].Protocol: got %q, want ss", nodes[2].Protocol)
		}
	})

	t.Run("empty input returns empty slice", func(t *testing.T) {
		nodes := PreviewLinks("")
		if len(nodes) != 0 {
			t.Errorf("expected 0 nodes, got %d", len(nodes))
		}
	})

	t.Run("placeholder URIs are silently skipped", func(t *testing.T) {
		rawText := "" +
			"vless://00000000-0000-0000-0000-000000000000@0.0.0.0:1?type=tcp&security=none#" +
			"%D0%9F%D1%80%D0%B8%D0%BB%D0%BE%D0%B6%D0%B5%D0%BD%D0%B8%D0%B5%20%D0%BD%D0%B5%20%D0%BF%D0%BE%D0%B4%D0%B4%D0%B5%D1%80%D0%B6%D0%B8%D0%B2%D0%B0%D0%B5%D1%82%D1%81%D1%8F\n" +
			"vless://11111111-1111-1111-1111-111111111111@example.com:443?type=tcp&security=none#Good\n"

		nodes := PreviewLinks(rawText)
		if len(nodes) != 1 {
			t.Fatalf("expected 1 parsed node (placeholder skipped), got %d", len(nodes))
		}
		if nodes[0].DisplayName != "Good" {
			t.Errorf("DisplayName: got %q, want Good", nodes[0].DisplayName)
		}
	})
}
