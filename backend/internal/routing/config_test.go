package routing

import (
	"encoding/base64"
	"encoding/json"
	"strings"
	"testing"

	"github.com/subvost/xray-tun/backend/internal/domain"
)

const minimalXrayConfig = `{"outbounds":[{"tag":"proxy"},{"tag":"direct"},{"tag":"block"}],"routing":{"rules":[{"type":"field","outboundTag":"proxy","inboundTag":["tun-in"]}]}}`

func TestApplyRoutingProfileToConfig(t *testing.T) {
	tests := []struct {
		name             string
		config           string
		rp               *domain.RoutingProfile
		wantRules        int
		wantDirectDomain string
		wantErr          string
	}{
		{
			name:   "direct_sites adds routing rule",
			config: minimalXrayConfig,
			rp: &domain.RoutingProfile{
				DirectSites: []string{"example.com"},
			},
			wantRules:        3, // base + direct + catchall
			wantDirectDomain: "example.com",
		},
		{
			name:   "empty direct_sites/proxy_sites no extra rules",
			config: minimalXrayConfig,
			rp: &domain.RoutingProfile{
				DirectSites: []string{},
				ProxySites:  []string{},
			},
			wantRules: 2, // base + catchall only
		},
		{
			name:    "nil profile returns error",
			config:  minimalXrayConfig,
			rp:      nil,
			wantErr: "routing profile is nil",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result, err := ApplyRoutingProfileToConfig([]byte(tt.config), tt.rp)
			if tt.wantErr != "" {
				if err == nil {
					t.Fatalf("expected error containing %q, got nil", tt.wantErr)
				}
				if !strings.Contains(err.Error(), tt.wantErr) {
					t.Errorf("error %q does not contain %q", err.Error(), tt.wantErr)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}

			var output map[string]interface{}
			if err := json.Unmarshal(result, &output); err != nil {
				t.Fatalf("failed to parse output JSON: %v", err)
			}

			routing, ok := output["routing"].(map[string]interface{})
			if !ok {
				t.Fatal("output missing routing section")
			}

			// Verify domainStrategy is set.
			ds, _ := routing["domainStrategy"].(string)
			if ds == "" {
				t.Error("output missing domainStrategy")
			}

			rules, ok := routing["rules"].([]interface{})
			if !ok {
				t.Fatal("output missing routing.rules")
			}

			if len(rules) != tt.wantRules {
				t.Errorf("got %d rules, want %d", len(rules), tt.wantRules)
			}

			if tt.wantDirectDomain != "" {
				found := false
				for _, r := range rules {
					rule, ok := r.(map[string]interface{})
					if !ok {
						continue
					}
					if rule["outboundTag"] != "direct" {
						continue
					}
					domains, ok := rule["domain"].([]interface{})
					if !ok {
						continue
					}
					for _, d := range domains {
						if s, ok := d.(string); ok && s == tt.wantDirectDomain {
							found = true
							break
						}
					}
					if found {
						break
					}
				}
				if !found {
					t.Errorf("no direct rule found with domain %q", tt.wantDirectDomain)
				}
			}
		})
	}
}

func TestImportRoutingProfile(t *testing.T) {
	payload := `{"Name":"Test","GlobalProxy":true,"DirectSites":["example.com"]}`
	encoded := base64.StdEncoding.EncodeToString([]byte(payload))
	uri := "happ://routing/add/" + encoded

	store := &domain.Store{
		Routing: domain.RoutingState{
			Profiles: []domain.RoutingProfile{},
		},
	}

	profile, isNew, err := ImportRoutingProfile(store, uri)
	if err != nil {
		t.Fatalf("ImportRoutingProfile failed: %v", err)
	}

	if !isNew {
		t.Error("expected isNew=true for new profile")
	}
	if profile.Name != "Test" {
		t.Errorf("Name = %q, want %q", profile.Name, "Test")
	}
	if profile.NameKey != "test" {
		t.Errorf("NameKey = %q, want %q", profile.NameKey, "test")
	}
	if !profile.GlobalProxy {
		t.Error("GlobalProxy = false, want true")
	}
	if len(profile.DirectSites) != 1 || profile.DirectSites[0] != "example.com" {
		t.Errorf("DirectSites = %v, want [example.com]", profile.DirectSites)
	}
	if profile.SourceFormat != "happ_uri" {
		t.Errorf("SourceFormat = %q, want %q", profile.SourceFormat, "happ_uri")
	}
	if profile.ActivationMode != "add" {
		t.Errorf("ActivationMode = %q, want %q", profile.ActivationMode, "add")
	}
	if profile.ID == "" {
		t.Error("ID is empty, expected auto-generated")
	}
	if profile.CreatedAt == "" {
		t.Error("CreatedAt is empty")
	}
	if profile.UpdatedAt == "" {
		t.Error("UpdatedAt is empty")
	}
}
