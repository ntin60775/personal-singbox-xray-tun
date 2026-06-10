package store

import (
	"strings"
	"testing"

	"github.com/subvost/xray-tun/backend/internal/domain"
)

// --- helpers ---

func ptrStr(s string) *string { return &s }
func ptrBool(b bool) *bool    { return &b }

// addTestNode appends a node to a profile inside the store (manual origin).
func addTestNode(store *domain.Store, profileID, nodeID, name, protocol string) {
	for i := range store.Profiles {
		if store.Profiles[i].ID == profileID {
			now := domain.ISONow()
			store.Profiles[i].Nodes = append(store.Profiles[i].Nodes, domain.Node{
				ID:        nodeID,
				Name:      name,
				Protocol:  protocol,
				RawURI:    protocol + "://" + nodeID,
				Origin:    domain.NodeOrigin{Kind: "manual"},
				Enabled:   true,
				CreatedAt: now,
				UpdatedAt: now,
			})
			return
		}
	}
}

// --- tests ---

func TestDefaultStore(t *testing.T) {
	store := DefaultStore()

	if store.Version != 3 {
		t.Errorf("version: got %d, want 3", store.Version)
	}

	if len(store.Profiles) != 1 {
		t.Fatalf("profiles count: got %d, want 1", len(store.Profiles))
	}

	mp := store.Profiles[0]
	if mp.ID != "manual" {
		t.Errorf("manual profile ID: got %q, want %q", mp.ID, "manual")
	}
	if mp.Kind != "manual" {
		t.Errorf("manual profile Kind: got %q, want %q", mp.Kind, "manual")
	}
	if mp.Name != "Локальные ссылки" {
		t.Errorf("manual profile Name: got %q, want %q", mp.Name, "Локальные ссылки")
	}
	if !mp.Enabled {
		t.Error("manual profile should be enabled")
	}
	if mp.Nodes == nil {
		t.Error("manual profile Nodes should be non-nil")
	}
	if len(mp.Nodes) != 0 {
		t.Errorf("manual profile Nodes: got %d, want 0", len(mp.Nodes))
	}

	if len(store.Subscriptions) != 0 {
		t.Errorf("subscriptions: got %d, want 0", len(store.Subscriptions))
	}

	if store.Routing.Enabled {
		t.Error("routing should be disabled by default")
	}
	if len(store.Routing.Profiles) != 0 {
		t.Errorf("routing profiles: got %d, want 0", len(store.Routing.Profiles))
	}

	if store.Meta.InitializedAt == "" {
		t.Error("Meta.InitializedAt should be set")
	}

	// ActiveSelection should be zero-value (empty strings)
	if store.ActiveSelection.ProfileID != "" || store.ActiveSelection.NodeID != "" {
		t.Error("active selection should be empty by default")
	}
}

func TestEnsureStoreInitialized(t *testing.T) {
	tmpDir := t.TempDir()
	paths := BuildAppPaths(tmpDir)

	// First call: creates store
	store1, err := EnsureStoreInitialized(paths)
	if err != nil {
		t.Fatalf("first EnsureStoreInitialized: %v", err)
	}
	if store1.Version != 3 {
		t.Errorf("version after first init: got %d, want 3", store1.Version)
	}

	// Second call: reads existing store
	store2, err := EnsureStoreInitialized(paths)
	if err != nil {
		t.Fatalf("second EnsureStoreInitialized: %v", err)
	}
	if store2.Version != 3 {
		t.Errorf("version after second init: got %d, want 3", store2.Version)
	}

	if len(store2.Profiles) != len(store1.Profiles) {
		t.Errorf("profiles mismatch: first=%d second=%d", len(store1.Profiles), len(store2.Profiles))
	}
}

func TestSaveLoadRoundtrip(t *testing.T) {
	tmpDir := t.TempDir()
	paths := BuildAppPaths(tmpDir)

	store := DefaultStore()

	// Mutate the store
	addTestNode(store, "manual", "node-a", "Test Node", "vless")
	AddSubscription(store, "My Sub", "https://example.com/sub")
	ActivateNode(store, "manual", "node-a", "test")

	// Save
	if err := SaveStore(paths, store); err != nil {
		t.Fatalf("SaveStore: %v", err)
	}

	// Load
	loaded, err := LoadStore(paths)
	if err != nil {
		t.Fatalf("LoadStore: %v", err)
	}

	// Verify key fields survived the roundtrip
	if loaded.Version != store.Version {
		t.Errorf("version: got %d, want %d", loaded.Version, store.Version)
	}
	if len(loaded.Profiles) != len(store.Profiles) {
		t.Fatalf("profiles count: got %d, want %d", len(loaded.Profiles), len(store.Profiles))
	}
	if len(loaded.Subscriptions) != len(store.Subscriptions) {
		t.Errorf("subscriptions count: got %d, want %d", len(loaded.Subscriptions), len(store.Subscriptions))
	}
	if loaded.ActiveSelection.NodeID != store.ActiveSelection.NodeID {
		t.Errorf("active node: got %q, want %q", loaded.ActiveSelection.NodeID, store.ActiveSelection.NodeID)
	}

	// Verify the added node is present
	_, node := FindNode(loaded, "manual", "node-a")
	if node == nil {
		t.Error("node-a not found after roundtrip")
	}
}

func TestAddSubscription(t *testing.T) {
	tests := []struct {
		name      string
		subName   string
		subURL    string
	}{
		{"basic", "Test Sub", "https://example.com/sub"},
		{"special chars", "Подписка №1", "https://sub.example.com/api/v1?token=abc"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tmpDir := t.TempDir()
			paths := BuildAppPaths(tmpDir)

			store := DefaultStore()
			beforeProfiles := len(store.Profiles)
			beforeSubs := len(store.Subscriptions)

			AddSubscription(store, tt.subName, tt.subURL)

			// Profile was added
			if len(store.Profiles) != beforeProfiles+1 {
				t.Fatalf("profiles: got %d, want %d", len(store.Profiles), beforeProfiles+1)
			}
			newProfile := store.Profiles[len(store.Profiles)-1]
			if newProfile.Kind != "subscription" {
				t.Errorf("profile kind: got %q, want %q", newProfile.Kind, "subscription")
			}
			if newProfile.Name != tt.subName {
				t.Errorf("profile name: got %q, want %q", newProfile.Name, tt.subName)
			}
			if !newProfile.Enabled {
				t.Error("profile should be enabled")
			}
			if newProfile.SourceSubscriptionID == "" {
				t.Error("profile SourceSubscriptionID should be set")
			}
			if newProfile.Nodes == nil || len(newProfile.Nodes) != 0 {
				t.Error("new profile should have empty nodes slice")
			}

			// Subscription was added
			if len(store.Subscriptions) != beforeSubs+1 {
				t.Fatalf("subscriptions: got %d, want %d", len(store.Subscriptions), beforeSubs+1)
			}
			newSub := store.Subscriptions[len(store.Subscriptions)-1]
			if newSub.Name != tt.subName {
				t.Errorf("sub name: got %q, want %q", newSub.Name, tt.subName)
			}
			if newSub.URL != tt.subURL {
				t.Errorf("sub URL: got %q, want %q", newSub.URL, tt.subURL)
			}
			if !newSub.Enabled {
				t.Error("subscription should be enabled")
			}

			// Sub profile ID matches subscription's ProfileID
			if newSub.ProfileID != newProfile.ID {
				t.Errorf("ProfileID mismatch: sub.ProfileID=%q profile.ID=%q", newSub.ProfileID, newProfile.ID)
			}

			// Cross-check: profile's SourceSubscriptionID matches sub's ID
			if newProfile.SourceSubscriptionID != newSub.ID {
				t.Errorf("SourceSubscriptionID mismatch: profile=%q sub=%q", newProfile.SourceSubscriptionID, newSub.ID)
			}

			// Persist and reload
			if err := SaveStore(paths, store); err != nil {
				t.Fatalf("SaveStore: %v", err)
			}
			loaded, err := LoadStore(paths)
			if err != nil {
				t.Fatalf("LoadStore: %v", err)
			}

			if len(loaded.Profiles) != beforeProfiles+1 {
				t.Errorf("profiles after reload: got %d, want %d", len(loaded.Profiles), beforeProfiles+1)
			}
			if len(loaded.Subscriptions) != beforeSubs+1 {
				t.Errorf("subscriptions after reload: got %d, want %d", len(loaded.Subscriptions), beforeSubs+1)
			}

			// Lookup by ID after reload
			sub := FindSubscription(loaded, newSub.ID)
			if sub == nil {
				t.Fatal("FindSubscription returned nil after reload")
			}
			if sub.Name != tt.subName {
				t.Errorf("reloaded sub name: got %q, want %q", sub.Name, tt.subName)
			}

			prof := FindProfile(loaded, newProfile.ID)
			if prof == nil {
				t.Fatal("FindProfile returned nil after reload")
			}
			if prof.Name != tt.subName {
				t.Errorf("reloaded profile name: got %q, want %q", prof.Name, tt.subName)
			}
		})
	}
}

func TestDeleteSubscription(t *testing.T) {
	store := DefaultStore()

	// Add a subscription
	AddSubscription(store, "To Delete", "https://example.com/sub")
	beforeProfileCount := len(store.Profiles)
	beforeSubCount := len(store.Subscriptions)

	subID := store.Subscriptions[0].ID // the subscription we just added

	// Add a routing profile linked to this subscription
	store.Routing.Profiles = append(store.Routing.Profiles, domain.RoutingProfile{
		ID:                   "rp-" + RandHex(8),
		Name:                 "Linked Route",
		SourceSubscriptionID: subID,
		AutoManaged:          true,
	})
	rpID := store.Routing.Profiles[0].ID

	// Delete the subscription
	err := DeleteSubscription(store, subID)
	if err != nil {
		t.Fatalf("DeleteSubscription: %v", err)
	}

	// Subscription should be gone
	if len(store.Subscriptions) != beforeSubCount-1 {
		t.Errorf("subscriptions after delete: got %d, want %d", len(store.Subscriptions), beforeSubCount-1)
	}
	if FindSubscription(store, subID) != nil {
		t.Error("subscription should not be found after delete")
	}

	// Profile should be gone
	if len(store.Profiles) != beforeProfileCount-1 {
		t.Errorf("profiles after delete: got %d, want %d", len(store.Profiles), beforeProfileCount-1)
	}

	// Routing profile should be gone
	if FindRoutingProfile(store, rpID) != nil {
		t.Error("routing profile linked to deleted subscription should be gone")
	}

	// Deleting non-existent subscription returns error
	err = DeleteSubscription(store, "nonexistent")
	if err == nil {
		t.Error("expected error for non-existent subscription")
	}
}

func TestActivateNode(t *testing.T) {
	store := DefaultStore()
	addTestNode(store, "manual", "n1", "Node One", "vless")

	ActivateNode(store, "manual", "n1", "gui")

	sel := store.ActiveSelection
	if sel.ProfileID != "manual" {
		t.Errorf("active profile: got %q, want %q", sel.ProfileID, "manual")
	}
	if sel.NodeID != "n1" {
		t.Errorf("active node: got %q, want %q", sel.NodeID, "n1")
	}
	if sel.Source != "gui" {
		t.Errorf("active source: got %q, want %q", sel.Source, "gui")
	}
	if sel.ActivatedAt == "" {
		t.Error("ActivatedAt should be set")
	}

	// GetActiveNode returns the same
	prof, node := GetActiveNode(store)
	if prof == nil {
		t.Fatal("GetActiveNode returned nil profile")
	}
	if prof.ID != "manual" {
		t.Errorf("GetActiveNode profile: got %q, want %q", prof.ID, "manual")
	}
	if node == nil {
		t.Fatal("GetActiveNode returned nil node")
	}
	if node.ID != "n1" {
		t.Errorf("GetActiveNode node: got %q, want %q", node.ID, "n1")
	}
}

func TestDeleteNode(t *testing.T) {
	t.Run("deletes active node and reassigns", func(t *testing.T) {
		store := DefaultStore()
		addTestNode(store, "manual", "n1", "First", "vless")
		addTestNode(store, "manual", "n2", "Second", "vmess")

		// Activate n2
		ActivateNode(store, "manual", "n2", "test")
		if store.ActiveSelection.NodeID != "n2" {
			t.Fatalf("expected active node n2, got %q", store.ActiveSelection.NodeID)
		}

		// Delete n2
		err := DeleteNode(store, "manual", "n2")
		if err != nil {
			t.Fatalf("DeleteNode: %v", err)
		}

		// n2 should be gone
		_, n2 := FindNode(store, "manual", "n2")
		if n2 != nil {
			t.Error("node n2 should be deleted")
		}

		// n1 should still exist
		_, n1 := FindNode(store, "manual", "n1")
		if n1 == nil {
			t.Error("node n1 should still exist")
		}

		// Active selection should not reference n2
		if store.ActiveSelection.NodeID == "n2" {
			t.Error("active selection should not reference deleted node n2")
		}
	})

	t.Run("errors on unknown profile", func(t *testing.T) {
		store := DefaultStore()
		err := DeleteNode(store, "no-profile", "n1")
		if err == nil {
			t.Error("expected error for unknown profile")
		}
	})

	t.Run("errors on unknown node in known profile", func(t *testing.T) {
		store := DefaultStore()
		err := DeleteNode(store, "manual", "no-node")
		if err == nil {
			t.Error("expected error for unknown node in manual profile")
		}
	})
}

func TestUpdateNodeFields(t *testing.T) {
	tests := []struct {
		name        string
		initialName string
		setName     *string
		setEnabled  *bool
		wantName    string
		wantEnabled bool
	}{
		{
			name:        "update name only",
			initialName: "original",
			setName:     ptrStr("renamed"),
			setEnabled:  nil,
			wantName:    "renamed",
			wantEnabled: true,
		},
		{
			name:        "disable node",
			initialName: "original",
			setName:     nil,
			setEnabled:  ptrBool(false),
			wantName:    "original",
			wantEnabled: false,
		},
		{
			name:        "update both",
			initialName: "original",
			setName:     ptrStr("updated"),
			setEnabled:  ptrBool(false),
			wantName:    "updated",
			wantEnabled: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			store := DefaultStore()
			addTestNode(store, "manual", "n1", tt.initialName, "vless")

			node, err := UpdateNodeFields(store, "manual", "n1", tt.setName, tt.setEnabled)
			if err != nil {
				t.Fatalf("UpdateNodeFields: %v", err)
			}
			if node.Name != tt.wantName {
				t.Errorf("name: got %q, want %q", node.Name, tt.wantName)
			}
			if node.Enabled != tt.wantEnabled {
				t.Errorf("enabled: got %v, want %v", node.Enabled, tt.wantEnabled)
			}
			if tt.setName != nil && !node.UserRenamed {
				t.Error("UserRenamed should be true after name update")
			}
			if node.UpdatedAt == "" {
				t.Error("UpdatedAt should be set")
			}

			// Verify persisted mutation in the store
			_, persisted := FindNode(store, "manual", "n1")
			if persisted == nil {
				t.Fatal("node not found after update")
			}
			if persisted.Name != tt.wantName {
				t.Errorf("persisted name: got %q, want %q", persisted.Name, tt.wantName)
			}
			if persisted.Enabled != tt.wantEnabled {
				t.Errorf("persisted enabled: got %v, want %v", persisted.Enabled, tt.wantEnabled)
			}
		})
	}

	t.Run("error on non-existent node", func(t *testing.T) {
		store := DefaultStore()
		_, err := UpdateNodeFields(store, "manual", "ghost", ptrStr("x"), nil)
		if err == nil {
			t.Error("expected error for unknown node")
		}
	})
}

func TestUpdateProfileFields(t *testing.T) {
	t.Run("update name only", func(t *testing.T) {
		store := DefaultStore()
		prof, err := UpdateProfileFields(store, "manual", ptrStr("New Name"), nil)
		if err != nil {
			t.Fatalf("UpdateProfileFields: %v", err)
		}
		if prof.Name != "New Name" {
			t.Errorf("name: got %q, want %q", prof.Name, "New Name")
		}
		if !prof.Enabled {
			t.Error("enabled should remain true")
		}
	})

	t.Run("disable profile", func(t *testing.T) {
		store := DefaultStore()
		prof, err := UpdateProfileFields(store, "manual", nil, ptrBool(false))
		if err != nil {
			t.Fatalf("UpdateProfileFields: %v", err)
		}
		if prof.Enabled {
			t.Error("profile should be disabled")
		}
	})

	t.Run("update both", func(t *testing.T) {
		store := DefaultStore()
		prof, err := UpdateProfileFields(store, "manual", ptrStr("Renamed"), ptrBool(false))
		if err != nil {
			t.Fatalf("UpdateProfileFields: %v", err)
		}
		if prof.Name != "Renamed" {
			t.Errorf("name: got %q, want %q", prof.Name, "Renamed")
		}
		if prof.Enabled {
			t.Error("profile should be disabled")
		}
	})

	t.Run("error on non-existent profile", func(t *testing.T) {
		store := DefaultStore()
		_, err := UpdateProfileFields(store, "no-such-profile", ptrStr("x"), nil)
		if err == nil {
			t.Error("expected error for unknown profile")
		}
	})
}

func TestDeleteProfile(t *testing.T) {
	t.Run("deletes subscription profile and linked sub", func(t *testing.T) {
		store := DefaultStore()
		AddSubscription(store, "To Delete", "https://example.com/sub")

		profileID := store.Profiles[1].ID // the subscription profile
		subID := store.Subscriptions[0].ID

		// Add a node to the profile and activate it
		addTestNode(store, profileID, "dn1", "Del Node", "vless")
		ActivateNode(store, profileID, "dn1", "test")

		profilesBefore := len(store.Profiles)
		subsBefore := len(store.Subscriptions)

		err := DeleteProfile(store, profileID)
		if err != nil {
			t.Fatalf("DeleteProfile: %v", err)
		}

		// Profile gone
		if len(store.Profiles) != profilesBefore-1 {
			t.Errorf("profiles: got %d, want %d", len(store.Profiles), profilesBefore-1)
		}
		if FindProfile(store, profileID) != nil {
			t.Error("profile should not be found after delete")
		}

		// Subscription gone
		if len(store.Subscriptions) != subsBefore-1 {
			t.Errorf("subscriptions: got %d, want %d", len(store.Subscriptions), subsBefore-1)
		}
		if FindSubscription(store, subID) != nil {
			t.Error("subscription should not be found after delete")
		}

		// Active selection should not reference deleted profile
		if store.ActiveSelection.ProfileID == profileID {
			t.Error("active selection should not reference deleted profile")
		}
	})

	t.Run("rejects manual profile deletion", func(t *testing.T) {
		store := DefaultStore()
		err := DeleteProfile(store, "manual")
		if err == nil {
			t.Error("expected error when deleting manual profile")
		}
		if !strings.Contains(err.Error(), "нельзя удалить") && !strings.Contains(err.Error(), "ручной") {
			t.Errorf("error should mention manual profile protection, got: %v", err)
		}
	})

	t.Run("error on non-existent profile", func(t *testing.T) {
		store := DefaultStore()
		err := DeleteProfile(store, "no-such")
		if err == nil {
			t.Error("expected error for unknown profile")
		}
	})
}

func TestFindRoutingProfile(t *testing.T) {
	store := DefaultStore()

	store.Routing.Profiles = []domain.RoutingProfile{
		{
			ID:      "rp-1",
			Name:    "Route Alpha",
			NameKey: "route-alpha",
			Enabled: true,
		},
		{
			ID:      "rp-2",
			Name:    "Route Beta",
			NameKey: "route-beta",
			Enabled: false,
		},
	}

	// Find by ID
	rp := FindRoutingProfile(store, "rp-1")
	if rp == nil {
		t.Fatal("FindRoutingProfile('rp-1') returned nil")
	}
	if rp.Name != "Route Alpha" {
		t.Errorf("name: got %q, want %q", rp.Name, "Route Alpha")
	}

	// Find by NameKey
	rpByName := FindRoutingProfileByName(store, "route-beta")
	if rpByName == nil {
		t.Fatal("FindRoutingProfileByName('route-beta') returned nil")
	}
	if rpByName.ID != "rp-2" {
		t.Errorf("ID: got %q, want %q", rpByName.ID, "rp-2")
	}

	// Non-existent by ID
	if FindRoutingProfile(store, "ghost") != nil {
		t.Error("expected nil for unknown routing profile ID")
	}

	// Non-existent by NameKey
	if FindRoutingProfileByName(store, "ghost-key") != nil {
		t.Error("expected nil for unknown routing profile NameKey")
	}

	// GetActiveRoutingProfile — none active initially
	if GetActiveRoutingProfile(store) != nil {
		t.Error("expected nil when no active routing profile is set")
	}

	// Set active and verify
	store.Routing.ActiveProfileID = "rp-1"
	active := GetActiveRoutingProfile(store)
	if active == nil {
		t.Fatal("GetActiveRoutingProfile returned nil after setting active")
	}
	if active.ID != "rp-1" {
		t.Errorf("active routing profile ID: got %q, want %q", active.ID, "rp-1")
	}
}

func TestStoreSummary(t *testing.T) {
	store := DefaultStore()

	// Start: 1 profile (manual), 0 nodes, 0 subscriptions
	summary := StoreSummary(store)
	if summary["profiles"] != 1 {
		t.Errorf("initial profiles: got %d, want 1", summary["profiles"])
	}
	if summary["nodes"] != 0 {
		t.Errorf("initial nodes: got %d, want 0", summary["nodes"])
	}
	if summary["subscriptions"] != 0 {
		t.Errorf("initial subscriptions: got %d, want 0", summary["subscriptions"])
	}

	// Add nodes to manual profile
	addTestNode(store, "manual", "n1", "N1", "vless")
	addTestNode(store, "manual", "n2", "N2", "vmess")
	addTestNode(store, "manual", "n3", "N3", "trojan")

	summary = StoreSummary(store)
	if summary["profiles"] != 1 {
		t.Errorf("profiles after nodes: got %d, want 1", summary["profiles"])
	}
	if summary["nodes"] != 3 {
		t.Errorf("nodes: got %d, want 3", summary["nodes"])
	}

	// Add subscription (adds 1 profile + 1 subscription)
	AddSubscription(store, "Sub", "https://example.com/sub")

	summary = StoreSummary(store)
	if summary["profiles"] != 2 {
		t.Errorf("profiles after sub: got %d, want 2", summary["profiles"])
	}
	if summary["subscriptions"] != 1 {
		t.Errorf("subscriptions: got %d, want 1", summary["subscriptions"])
	}
	if summary["nodes"] != 3 {
		t.Errorf("nodes after sub: got %d, want 3", summary["nodes"])
	}

	// Add a node to the subscription profile
	subProfileID := store.Profiles[1].ID
	addTestNode(store, subProfileID, "sn1", "Sub Node", "vless")

	summary = StoreSummary(store)
	if summary["nodes"] != 4 {
		t.Errorf("nodes after sub node: got %d, want 4", summary["nodes"])
	}
}

func TestRandHex(t *testing.T) {
	// RandHex(16) returns a 32-character hex string (16 bytes * 2 hex chars per byte)
	result := RandHex(16)
	if len(result) != 32 {
		t.Errorf("RandHex(16) length: got %d, want 32", len(result))
	}

	// All characters should be valid hex
	hexChars := "0123456789abcdefABCDEF"
	for i, c := range result {
		if !strings.ContainsRune(hexChars, c) {
			t.Errorf("RandHex(16) contains non-hex char %q at position %d", c, i)
		}
	}

	// Multiple calls produce different values (probabilistic, extremely unlikely to fail)
	r2 := RandHex(16)
	if r2 == result {
		t.Error("two consecutive RandHex(16) calls produced identical values")
	}

	// Zero length produces empty string
	if r := RandHex(0); r != "" {
		t.Errorf("RandHex(0): got %q, want empty", r)
	}

	// Different lengths
	if r := RandHex(1); len(r) != 2 {
		t.Errorf("RandHex(1) length: got %d, want 2", len(r))
	}
	if r := RandHex(8); len(r) != 16 {
		t.Errorf("RandHex(8) length: got %d, want 16", len(r))
	}
}
