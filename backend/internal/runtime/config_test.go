package runtime

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/subvost/xray-tun/backend/internal/domain"
)

// =============================================================================
// TestNodeCanRenderRuntime
// =============================================================================

func TestNodeCanRenderRuntime(t *testing.T) {
	tests := []struct {
		name string
		node *domain.Node
		want bool
	}{
		{
			name: "nil node",
			node: nil,
			want: false,
		},
		{
			name: "disabled node",
			node: &domain.Node{
				Normalized: domain.NodeAddress{
					Protocol: "vless",
					Address:  "1.2.3.4",
					Port:     443,
				},
				Enabled: false,
			},
			want: false,
		},
		{
			name: "valid enabled node",
			node: &domain.Node{
				Normalized: domain.NodeAddress{
					Protocol: "vless",
					Address:  "1.2.3.4",
					Port:     443,
				},
				Enabled: true,
			},
			want: true,
		},
		{
			name: "missing protocol",
			node: &domain.Node{
				Normalized: domain.NodeAddress{
					Address: "1.2.3.4",
					Port:    443,
				},
				Enabled: true,
			},
			want: false,
		},
		{
			name: "parse error suppresses render",
			node: &domain.Node{
				Normalized: domain.NodeAddress{
					Protocol: "vless",
					Address:  "1.2.3.4",
					Port:     443,
				},
				Enabled:    true,
				ParseError: "invalid URI",
			},
			want: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := NodeCanRenderRuntime(tt.node)
			if got != tt.want {
				t.Errorf("NodeCanRenderRuntime() = %v, want %v", got, tt.want)
			}
		})
	}
}

// =============================================================================
// TestRenderRuntimeConfig
// =============================================================================

func readTemplateConfig(t *testing.T) []byte {
	t.Helper()

	// Resolve project-root xray-tun-subvost.json from the test package directory.
	// The test runs with cwd equal to the package directory (backend/internal/runtime/).
	candidates := []string{
		"../../../xray-tun-subvost.json",
		filepath.Join("..", "..", "..", "xray-tun-subvost.json"),
	}

	// Also try an absolute path via GOWORK or module root hint.
	if wd, err := os.Getwd(); err == nil {
		candidates = append(candidates, filepath.Join(wd, "..", "..", "..", "xray-tun-subvost.json"))
	}

	for _, p := range candidates {
		data, err := os.ReadFile(p)
		if err == nil {
			return data
		}
	}

	t.Skip("xray-tun-subvost.json not found — skip integration-style render test")
	return nil
}

func TestRenderRuntimeConfig(t *testing.T) {
	template := readTemplateConfig(t)

	node := &domain.Node{
		ID:      "test-node-1",
		Enabled: true,
		Normalized: domain.NodeAddress{
			Protocol:   "vless",
			Address:    "45.137.69.71",
			Port:       443,
			UUID:       "df254e06-709a-4389-8fd9-112160535b17",
			Network:    "xhttp",
			Security:   "reality",
			PublicKey:  "IohigEU1uGoJbLQeOrLvM2M_rhTFGVBXfdvYzEdFKVo",
			ShortID:    "6ba85179e30d4fc2",
			ServerName: "fn.video.subvost.fun",
			Path:       "/",
			Mode:       "auto",
			Fingerprint: "chrome",
		},
	}

	rendered, err := RenderRuntimeConfig(template, node, nil)
	if err != nil {
		t.Fatalf("RenderRuntimeConfig failed: %v", err)
	}

	var cfg map[string]interface{}
	if err := json.Unmarshal(rendered, &cfg); err != nil {
		t.Fatalf("rendered config is not valid JSON: %v", err)
	}

	outbounds, ok := cfg["outbounds"].([]interface{})
	if !ok || len(outbounds) == 0 {
		t.Fatal("rendered config missing outbounds array")
	}

	// Find the proxy outbound.
	var proxyOutbound map[string]interface{}
	for _, ob := range outbounds {
		if m, ok := ob.(map[string]interface{}); ok {
			if tag, _ := m["tag"].(string); tag == "proxy" {
				proxyOutbound = m
				break
			}
		}
	}
	if proxyOutbound == nil {
		t.Fatal("rendered config missing outbound with tag=proxy")
	}

	if protocol, _ := proxyOutbound["protocol"].(string); protocol != "vless" {
		t.Errorf("proxy outbound protocol = %q, want %q", protocol, "vless")
	}

	settings, ok := proxyOutbound["settings"].(map[string]interface{})
	if !ok {
		t.Fatal("proxy outbound missing settings")
	}
	vnext, ok := settings["vnext"].([]interface{})
	if !ok || len(vnext) == 0 {
		t.Fatal("proxy outbound settings missing vnext array")
	}
	firstVnext, ok := vnext[0].(map[string]interface{})
	if !ok {
		t.Fatal("first vnext entry is not an object")
	}
	if addr, _ := firstVnext["address"].(string); addr != node.Normalized.Address {
		t.Errorf("vnext address = %q, want %q", addr, node.Normalized.Address)
	}
	if port, _ := firstVnext["port"].(float64); int(port) != node.Normalized.Port {
		t.Errorf("vnext port = %v, want %d", port, node.Normalized.Port)
	}
}

func TestRenderRuntimeConfigMissingProxy(t *testing.T) {
	// A config that has outbounds but no tag=proxy.
	template := []byte(`{
  "outbounds": [
    {"tag": "direct", "protocol": "freedom"},
    {"tag": "block", "protocol": "blackhole"}
  ]
}`)

	node := &domain.Node{
		ID:      "test-node",
		Enabled: true,
		Normalized: domain.NodeAddress{
			Protocol: "vless",
			Address:  "1.2.3.4",
			Port:     443,
		},
	}

	_, err := RenderRuntimeConfig(template, node, nil)
	if err == nil {
		t.Fatal("expected error for template without proxy outbound, got nil")
	}
	if !strings.Contains(err.Error(), "proxy") {
		t.Errorf("error %q should mention 'proxy'", err.Error())
	}
}

func TestRenderRuntimeConfigInvalidNode(t *testing.T) {
	node := &domain.Node{
		Enabled: false,
	}
	_, err := RenderRuntimeConfig([]byte(`{"outbounds":[]}`), node, nil)
	if err == nil {
		t.Fatal("expected error for invalid node, got nil")
	}
}

// =============================================================================
// TestApplyTransportHints
// =============================================================================

func minConfigWithProxyAndDirect() []byte {
	return []byte(`{
  "outbounds": [
    {
      "tag": "proxy",
      "protocol": "vless",
      "streamSettings": {}
    },
    {
      "tag": "direct",
      "protocol": "freedom",
      "streamSettings": {}
    }
  ]
}`)
}

func TestApplyTransportHints(t *testing.T) {
	config := minConfigWithProxyAndDirect()
	hint := &domain.TransportHint{
		DefaultInterface: "eth0",
		DefaultMark:      123,
	}

	patched, err := ApplyTransportHints(config, hint)
	if err != nil {
		t.Fatalf("ApplyTransportHints failed: %v", err)
	}

	var cfg map[string]interface{}
	if err := json.Unmarshal(patched, &cfg); err != nil {
		t.Fatalf("patched config is not valid JSON: %v", err)
	}

	outbounds, ok := cfg["outbounds"].([]interface{})
	if !ok {
		t.Fatal("patched config missing outbounds")
	}

	var proxyOB map[string]interface{}
	for _, ob := range outbounds {
		if m, ok := ob.(map[string]interface{}); ok {
			if tag, _ := m["tag"].(string); tag == "proxy" {
				proxyOB = m
				break
			}
		}
	}
	if proxyOB == nil {
		t.Fatal("proxy outbound missing after patch")
	}

	ss, ok := proxyOB["streamSettings"].(map[string]interface{})
	if !ok {
		t.Fatal("proxy outbound missing streamSettings")
	}

	sockopt, ok := ss["sockopt"].(map[string]interface{})
	if !ok {
		t.Fatal("streamSettings missing sockopt after hint injection")
	}

	if iface, _ := sockopt["interface"].(string); iface != "eth0" {
		t.Errorf("sockopt.interface = %q, want %q", iface, "eth0")
	}
	mark, ok := sockopt["mark"].(float64)
	if !ok {
		t.Fatal("sockopt.mark missing or not a number")
	}
	if int(mark) != 123 {
		t.Errorf("sockopt.mark = %v, want 123", mark)
	}
}

func TestApplyTransportHintsNilHint(t *testing.T) {
	config := minConfigWithProxyAndDirect()
	got, err := ApplyTransportHints(config, nil)
	if err != nil {
		t.Fatalf("ApplyTransportHints(nil hint) failed: %v", err)
	}
	// Should return the original config unmodified.
	if string(got) != string(config) {
		t.Error("ApplyTransportHints with nil hint should return config unchanged")
	}
}

func TestApplyTransportHintsEmptyHint(t *testing.T) {
	config := minConfigWithProxyAndDirect()
	got, err := ApplyTransportHints(config, &domain.TransportHint{})
	if err != nil {
		t.Fatalf("ApplyTransportHints(empty hint) failed: %v", err)
	}
	if string(got) != string(config) {
		t.Error("ApplyTransportHints with empty hint should return config unchanged")
	}
}

func TestApplyTransportHintsMissingOutbounds(t *testing.T) {
	config := []byte(`{"outbounds": [{"tag": "proxy", "protocol": "vless"}]}`)
	hint := &domain.TransportHint{DefaultInterface: "eth0"}
	_, err := ApplyTransportHints(config, hint)
	if err == nil {
		t.Fatal("expected error for config missing 'direct' outbound")
	}
}

// =============================================================================
// TestClassifyOwnership
// =============================================================================

func TestClassifyOwnership(t *testing.T) {
	const (
		installID   = "inst-001"
		projectRoot = "/opt/subvost"
	)

	tests := []struct {
		name    string
		state   map[string]string
		want    string
	}{
		{
			name:  "nil state",
			state: nil,
			want:  "unknown",
		},
		{
			name:  "empty state",
			state: map[string]string{},
			want:  "unknown",
		},
		{
			name: "matching install_id",
			state: map[string]string{
				"BUNDLE_INSTALL_ID": installID,
			},
			want: "current",
		},
		{
			name: "non-matching install_id",
			state: map[string]string{
				"BUNDLE_INSTALL_ID": "other-install",
			},
			want: "foreign",
		},
		{
			name: "matching root without install_id",
			state: map[string]string{
				"BUNDLE_PROJECT_ROOT_HINT": projectRoot,
			},
			want: "current",
		},
		{
			name: "non-matching root without install_id",
			state: map[string]string{
				"BUNDLE_PROJECT_ROOT_HINT": "/other/root",
			},
			want: "unknown",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := ClassifyOwnership(tt.state, installID, projectRoot)
			if got != tt.want {
				t.Errorf("ClassifyOwnership() = %q, want %q", got, tt.want)
			}
		})
	}
}

func TestClassifyOwnershipEmptyInstallID(t *testing.T) {
	state := map[string]string{
		"BUNDLE_INSTALL_ID": "inst-001",
	}
	got := ClassifyOwnership(state, "", "/root")
	if got != "unknown" {
		t.Errorf("ClassifyOwnership with empty installID = %q, want %q", got, "unknown")
	}
}
