package store

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"github.com/subvost/xray-tun/backend/internal/domain"
)

// AppPaths holds all relevant paths for the application.
type AppPaths struct {
	ConfigHome                  string
	StoreDir                    string
	StoreFile                   string
	GeneratedXrayConfigFile     string
	ActiveRuntimeXrayConfigFile string
	GUISettingsFile             string
	XrayAssetDir                string
	GeoIPAssetFile              string
	GeositeAssetFile            string
	StateFile                   string
	ResolvBackup                string
	LogDir                      string
}

// BuildAppPaths builds AppPaths from config home.
func BuildAppPaths(configHome string) AppPaths {
	storeDir := filepath.Join(configHome, "subvost-xray-tun")
	return AppPaths{
		ConfigHome:                  configHome,
		StoreDir:                    storeDir,
		StoreFile:                   filepath.Join(storeDir, "store.json"),
		GeneratedXrayConfigFile:     filepath.Join(storeDir, "generated-xray-config.json"),
		ActiveRuntimeXrayConfigFile: filepath.Join(storeDir, "active-runtime-xray-config.json"),
		GUISettingsFile:             filepath.Join(storeDir, "gui-settings.json"),
		XrayAssetDir:                filepath.Join(storeDir, "xray-assets"),
		GeoIPAssetFile:              filepath.Join(storeDir, "xray-assets", "geoip.dat"),
		GeositeAssetFile:            filepath.Join(storeDir, "xray-assets", "geosite.dat"),
		StateFile:                   filepath.Join(storeDir, "subvost.state"),
		ResolvBackup:                filepath.Join(storeDir, "resolv.conf.subvost-backup"),
		LogDir:                      filepath.Join(storeDir, "logs"),
	}
}

// LoadStore reads and parses store.json.
func LoadStore(paths AppPaths) (*domain.Store, error) {
	data, err := os.ReadFile(paths.StoreFile)
	if err != nil {
		return nil, fmt.Errorf("read store: %w", err)
	}
	var store domain.Store
	if err := json.Unmarshal(data, &store); err != nil {
		return nil, fmt.Errorf("parse store: %w", err)
	}
	normalizeStore(&store)
	return &store, nil
}

// SaveStore atomically writes store to disk.
func SaveStore(paths AppPaths, store *domain.Store) error {
	ensureStoreDir(paths)
	normalizeStore(store)
	data, err := json.MarshalIndent(store, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal store: %w", err)
	}
	tmpFile := filepath.Join(paths.StoreDir, ".store.tmp")
	if err := os.WriteFile(tmpFile, data, 0644); err != nil {
		return fmt.Errorf("write tmp store: %w", err)
	}
	if err := os.Rename(tmpFile, paths.StoreFile); err != nil {
		os.Remove(tmpFile)
		return fmt.Errorf("rename store: %w", err)
	}
	return nil
}

// EnsureStoreInitialized loads existing store or creates default.
func EnsureStoreInitialized(paths AppPaths) (*domain.Store, error) {
	ensureStoreDir(paths)
	if _, err := os.Stat(paths.StoreFile); os.IsNotExist(err) {
		store := DefaultStore()
		if err := SaveStore(paths, store); err != nil {
			return nil, fmt.Errorf("create default store: %w", err)
		}
		return store, nil
	}
	return LoadStore(paths)
}

// DefaultStore returns a fresh default store.
func DefaultStore() *domain.Store {
	return &domain.Store{
		Version:       3,
		Profiles:      []domain.Profile{defaultManualProfile()},
		Subscriptions: []domain.Subscription{},
		ActiveSelection: domain.ActiveSelection{},
		Routing: domain.RoutingState{
			Enabled:  false,
			Profiles: []domain.RoutingProfile{},
			Geodata:  defaultGeodataState(),
		},
		Meta: domain.StoreMeta{InitializedAt: domain.ISONow()},
	}
}

func defaultManualProfile() domain.Profile {
	return domain.Profile{
		ID: "manual", Kind: "manual", Name: "Локальные ссылки",
		Enabled: true, Nodes: []domain.Node{},
	}
}

func defaultGeodataState() domain.RoutingGeodataState {
	return domain.RoutingGeodataState{Status: "pending"}
}

func normalizeStore(store *domain.Store) {
	if store.Version == 0 {
		store.Version = 3
	}
	if len(store.Profiles) == 0 {
		store.Profiles = []domain.Profile{defaultManualProfile()}
	}
	for i := range store.Profiles {
		if store.Profiles[i].Nodes == nil {
			store.Profiles[i].Nodes = []domain.Node{}
		}
	}
	if store.Routing.Geodata.Status == "" {
		store.Routing.Geodata = defaultGeodataState()
	}
	if store.Meta.InitializedAt == "" {
		store.Meta.InitializedAt = domain.ISONow()
	}
}

func ensureStoreDir(paths AppPaths) {
	os.MkdirAll(paths.StoreDir, 0700)
}

// RandHex generates a random hex string of given byte length.
func RandHex(length int) string {
	b := make([]byte, length)
	rand.Read(b)
	return hex.EncodeToString(b)
}

// ---------------------------------------------------------------------------
// Node operations
// ---------------------------------------------------------------------------

func GetActiveNode(store *domain.Store) (*domain.Profile, *domain.Node) {
	sel := store.ActiveSelection
	if sel.ProfileID == "" || sel.NodeID == "" {
		return nil, nil
	}
	for i := range store.Profiles {
		p := &store.Profiles[i]
		if p.ID == sel.ProfileID {
			for j := range p.Nodes {
				if p.Nodes[j].ID == sel.NodeID {
					return p, &p.Nodes[j]
				}
			}
			return p, nil
		}
	}
	return nil, nil
}

func FindNode(store *domain.Store, profileID, nodeID string) (*domain.Profile, *domain.Node) {
	for i := range store.Profiles {
		p := &store.Profiles[i]
		if p.ID == profileID {
			for j := range p.Nodes {
				if p.Nodes[j].ID == nodeID {
					return p, &p.Nodes[j]
				}
			}
			return p, nil
		}
	}
	return nil, nil
}

func ActivateNode(store *domain.Store, profileID, nodeID, source string) {
	store.ActiveSelection = domain.ActiveSelection{
		ProfileID: profileID, NodeID: nodeID,
		ActivatedAt: domain.ISONow(), Source: source,
	}
}

func DeleteNode(store *domain.Store, profileID, nodeID string) error {
	for i := range store.Profiles {
		if store.Profiles[i].ID != profileID {
			continue
		}
		nodes := store.Profiles[i].Nodes
		for j, n := range nodes {
			if n.ID == nodeID {
				store.Profiles[i].Nodes = append(nodes[:j], nodes[j+1:]...)
				if store.ActiveSelection.NodeID == nodeID {
					store.ActiveSelection = domain.ActiveSelection{}
					ensureActiveSelection(store)
				}
				return nil
			}
		}
		return fmt.Errorf("node %s not found in profile %s", nodeID, profileID)
	}
	return fmt.Errorf("profile %s not found", profileID)
}

func UpdateNodeFields(store *domain.Store, profileID, nodeID string, name *string, enabled *bool) (*domain.Node, error) {
	_, node := FindNode(store, profileID, nodeID)
	if node == nil {
		return nil, fmt.Errorf("node %s not found", nodeID)
	}
	if name != nil {
		node.Name = *name
		node.UserRenamed = true
	}
	if enabled != nil {
		node.Enabled = *enabled
	}
	node.UpdatedAt = domain.ISONow()
	return node, nil
}

// ---------------------------------------------------------------------------
// Profile operations
// ---------------------------------------------------------------------------

func FindProfile(store *domain.Store, profileID string) *domain.Profile {
	for i := range store.Profiles {
		if store.Profiles[i].ID == profileID {
			return &store.Profiles[i]
		}
	}
	return nil
}

func UpdateProfileFields(store *domain.Store, profileID string, name *string, enabled *bool) (*domain.Profile, error) {
	p := FindProfile(store, profileID)
	if p == nil {
		return nil, fmt.Errorf("profile %s not found", profileID)
	}
	if name != nil {
		p.Name = *name
	}
	if enabled != nil {
		p.Enabled = *enabled
	}
	return p, nil
}

func DeleteProfile(store *domain.Store, profileID string) error {
	if profileID == "manual" {
		return fmt.Errorf("нельзя удалить ручной профиль")
	}
	for i, p := range store.Profiles {
		if p.ID == profileID {
			store.Profiles = append(store.Profiles[:i], store.Profiles[i+1:]...)
			// Remove associated subscription
			for j, sub := range store.Subscriptions {
				if sub.ProfileID == profileID {
					store.Subscriptions = append(store.Subscriptions[:j], store.Subscriptions[j+1:]...)
					break
				}
			}
			if store.ActiveSelection.ProfileID == profileID {
				store.ActiveSelection = domain.ActiveSelection{}
				ensureActiveSelection(store)
			}
			return nil
		}
	}
	return fmt.Errorf("profile %s not found", profileID)
}

// ---------------------------------------------------------------------------
// Subscription operations
// ---------------------------------------------------------------------------

func FindSubscription(store *domain.Store, subID string) *domain.Subscription {
	for i := range store.Subscriptions {
		if store.Subscriptions[i].ID == subID {
			return &store.Subscriptions[i]
		}
	}
	return nil
}

func AddSubscription(store *domain.Store, name, url string) {
	subID := "sub-" + RandHex(16)
	profileID := "profile-" + RandHex(16)
	store.Subscriptions = append(store.Subscriptions, domain.Subscription{
		ID: subID, URL: url, Name: name, Enabled: true,
		ProfileID: profileID,
	})
	store.Profiles = append(store.Profiles, domain.Profile{
		ID: profileID, Kind: "subscription", Name: name, Enabled: true,
		SourceSubscriptionID: subID, Nodes: []domain.Node{},
	})
}

func AddSubscriptionFull(store *domain.Store, sub domain.Subscription) {
	store.Subscriptions = append(store.Subscriptions, sub)
	store.Profiles = append(store.Profiles, domain.Profile{
		ID: sub.ProfileID, Kind: "subscription", Name: sub.Name, Enabled: true,
		SourceSubscriptionID: sub.ID, Nodes: []domain.Node{},
	})
}

func UpdateSubscriptionFields(store *domain.Store, subID string, name *string, enabled *bool) (*domain.Subscription, error) {
	sub := FindSubscription(store, subID)
	if sub == nil {
		return nil, fmt.Errorf("subscription %s not found", subID)
	}
	if name != nil {
		sub.Name = *name
	}
	if enabled != nil {
		sub.Enabled = *enabled
	}
	return sub, nil
}

func DeleteSubscription(store *domain.Store, subID string) error {
	sub := FindSubscription(store, subID)
	if sub == nil {
		return fmt.Errorf("subscription %s not found", subID)
	}
	// Remove associated routing profiles
	var kept []domain.RoutingProfile
	for _, rp := range store.Routing.Profiles {
		if rp.SourceSubscriptionID != subID {
			kept = append(kept, rp)
		}
	}
	store.Routing.Profiles = kept

	// Remove profile
	for i, p := range store.Profiles {
		if p.SourceSubscriptionID == subID {
			store.Profiles = append(store.Profiles[:i], store.Profiles[i+1:]...)
			break
		}
	}
	// Remove subscription
	for i, s := range store.Subscriptions {
		if s.ID == subID {
			store.Subscriptions = append(store.Subscriptions[:i], store.Subscriptions[i+1:]...)
			break
		}
	}
	if store.ActiveSelection.ProfileID == "" {
		ensureActiveSelection(store)
	} else {
		// Check if the active selection's profile still exists
		found := false
		for _, p := range store.Profiles {
			if p.ID == store.ActiveSelection.ProfileID {
				found = true
				break
			}
		}
		if !found {
			store.ActiveSelection = domain.ActiveSelection{}
			ensureActiveSelection(store)
		}
	}
	return nil
}

// ---------------------------------------------------------------------------
// Routing operations
// ---------------------------------------------------------------------------

func FindRoutingProfile(store *domain.Store, profileID string) *domain.RoutingProfile {
	for i := range store.Routing.Profiles {
		if store.Routing.Profiles[i].ID == profileID {
			return &store.Routing.Profiles[i]
		}
	}
	return nil
}

func FindRoutingProfileByName(store *domain.Store, nameKey string) *domain.RoutingProfile {
	for i := range store.Routing.Profiles {
		if store.Routing.Profiles[i].NameKey == nameKey {
			return &store.Routing.Profiles[i]
		}
	}
	return nil
}

func GetActiveRoutingProfile(store *domain.Store) *domain.RoutingProfile {
	if store.Routing.ActiveProfileID == "" {
		return nil
	}
	return FindRoutingProfile(store, store.Routing.ActiveProfileID)
}

func ensureActiveSelection(store *domain.Store) {
	if store.ActiveSelection.ProfileID != "" {
		_, node := GetActiveNode(store)
		if node != nil {
			return
		}
	}
	for _, p := range store.Profiles {
		if p.Enabled && len(p.Nodes) > 0 {
			store.ActiveSelection = domain.ActiveSelection{
				ProfileID: p.ID, NodeID: p.Nodes[0].ID,
				ActivatedAt: domain.ISONow(), Source: "auto",
			}
			return
		}
	}
	store.ActiveSelection = domain.ActiveSelection{}
}

// StoreSummary returns node/profile/sub counts for display.
func StoreSummary(store *domain.Store) map[string]int {
	totalNodes := 0
	for _, p := range store.Profiles {
		totalNodes += len(p.Nodes)
	}
	return map[string]int{
		"profiles":      len(store.Profiles),
		"nodes":         totalNodes,
		"subscriptions": len(store.Subscriptions),
	}
}
