package rpc

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"github.com/subvost/xray-tun/backend/internal/domain"
	"github.com/subvost/xray-tun/backend/internal/network"
	"github.com/subvost/xray-tun/backend/internal/parser"
	"github.com/subvost/xray-tun/backend/internal/routing"
	"github.com/subvost/xray-tun/backend/internal/runtime"
	"github.com/subvost/xray-tun/backend/internal/shell"
	"github.com/subvost/xray-tun/backend/internal/store"
)

// ---------------------------------------------------------------------------
// Runtime handlers
// ---------------------------------------------------------------------------

// hStatus returns the current system status.
func (s *Server) hStatus(params json.RawMessage) (interface{}, error) {
	s.reloadStore()

	var xrayAlive bool
	var xrayPID int
	var tunExists bool
	var trafficRx, trafficTx uint64

	state := runtime.ReadStateFile(s.paths.StateFile)
	if state != nil {
		if pidStr, ok := state["XRAY_PID"]; ok {
			fmt.Sscanf(pidStr, "%d", &xrayPID)
			xrayAlive = xrayPID > 0 && runtime.IsXrayAlive(xrayPID)
		}
		if tunName, ok := state["TUN_NAME"]; ok && tunName != "" {
			tunExists = runtime.CheckTunExists(tunName)
			if tunExists {
				trafficRx, trafficTx, _ = network.ReadTrafficCounters(tunName)
			}
		}
	}

	nameservers, _ := network.ReadResolvConfNameservers()
	ifaces, _ := network.ListInterfaceAddresses()

	profile, node := store.GetActiveNode(s.store)
	var activeNode map[string]interface{}
	if node != nil {
		activeNode = map[string]interface{}{
			"profile_id":   profile.ID,
			"profile_name": profile.Name,
			"node_id":      node.ID,
			"node_name":    node.Name,
			"protocol":     node.Protocol,
			"address":      node.Normalized.Address,
			"port":         node.Normalized.Port,
		}
	}

	summary := store.StoreSummary(s.store)

	routingEnabled := s.store.Routing.Enabled
	activeRouting := store.GetActiveRoutingProfile(s.store)
	var activeRoutingName string
	if activeRouting != nil {
		activeRoutingName = activeRouting.Name
	}

	return map[string]interface{}{
		"xray_alive":          xrayAlive,
		"xray_pid":            xrayPID,
		"tun_exists":          tunExists,
		"traffic_rx":          trafficRx,
		"traffic_tx":          trafficTx,
		"active_node":         activeNode,
		"nameservers":         nameservers,
		"interfaces":          ifaces,
		"profiles_count":      summary["profiles"],
		"nodes_count":         summary["nodes"],
		"subscriptions_count": summary["subscriptions"],
		"routing_enabled":     routingEnabled,
		"active_routing":      activeRoutingName,
		"geodata_ready":       s.store.Routing.Geodata.Ready,
		"geodata_status":      s.store.Routing.Geodata.Status,
	}, nil
}

// hStart launches the VPN tunnel.
func (s *Server) hStart(params json.RawMessage) (interface{}, error) {
	s.reloadStore()

	// Get active node
	_, node := store.GetActiveNode(s.store)
	if node == nil {
		return nil, fmt.Errorf("no active node selected")
	}

	// Find xray binary
	xrayBinary := runtime.FindXrayBinary(s.projectRoot)
	if xrayBinary == "" {
		return nil, fmt.Errorf("xray binary not found")
	}

	// Generate xray config
	templatePath := filepath.Join(s.paths.StoreDir, "xray-config-template.json")
	template, err := os.ReadFile(templatePath)
	if err != nil {
		return nil, fmt.Errorf("read xray config template: %w", err)
	}

	config, err := runtime.RenderRuntimeConfig(template, node, nil)
	if err != nil {
		return nil, fmt.Errorf("render config: %w", err)
	}

	// Apply routing profile overlay if active
	if s.store.Routing.Enabled {
		activeRP := store.GetActiveRoutingProfile(s.store)
		if activeRP != nil {
			config, err = routing.ApplyRoutingProfileToConfig(config, activeRP)
			if err != nil {
				return nil, fmt.Errorf("apply routing profile: %w", err)
			}
		}
	}

	// Always apply transport hints with the correct fwmark matching policy routing.
	// The template has placeholder interface/mark values that MUST be overridden
	// at runtime. Without this, Xray's outbound traffic would use a wrong mark
	// (or none) and loop back through the TUN device, killing internet access.
	fwmark := 0x7073
	table := 7073
	defaultIface, _, _ := runtime.DetectDefaultInterface()
	hint := &domain.TransportHint{
		DefaultMark:      fwmark,
		DefaultInterface: defaultIface,
	}
	if node.TransportHint != nil && node.TransportHint.DefaultInterface != "" {
		hint.DefaultInterface = node.TransportHint.DefaultInterface
	}
	config, err = runtime.ApplyTransportHints(config, hint)
	if err != nil {
		return nil, fmt.Errorf("apply transport hints: %w", err)
	}

	// Write config
	if err := os.WriteFile(s.paths.ActiveRuntimeXrayConfigFile, config, 0644); err != nil {
		return nil, fmt.Errorf("write xray config: %w", err)
	}

	// Start xray
	pid, err := runtime.StartXray(s.paths.ActiveRuntimeXrayConfigFile)
	if err != nil {
		return nil, fmt.Errorf("start xray: %w", err)
	}

	// Create TUN device
	tunName := "tun0"


	if err := runtime.CreateTun(tunName, 1500); err != nil {
		runtime.StopXray(pid)
		return nil, fmt.Errorf("create tun: %w", err)
	}

	// Setup policy routing
	if err := runtime.SetupPolicyRouting(tunName, fwmark, table); err != nil {
		runtime.TeardownTun(tunName, table, fwmark)
		runtime.StopXray(pid)
		return nil, fmt.Errorf("setup routing: %w", err)
	}

	// Apply DNS
	nameservers, _ := runtime.ResolveSystemDNS()
	if len(nameservers) == 0 {
		nameservers = []string{"1.1.1.1", "8.8.8.8"}
	}
	if err := runtime.BackupResolvConf(s.paths.ResolvBackup); err != nil {
		runtime.TeardownTun(tunName, table, fwmark)
		runtime.StopXray(pid)
		return nil, fmt.Errorf("backup resolv: %w", err)
	}
	if err := runtime.WriteTunResolvConf("/etc/resolv.conf", nameservers); err != nil {
		runtime.RestoreResolvConf(s.paths.ResolvBackup)
		runtime.TeardownTun(tunName, table, fwmark)
		runtime.StopXray(pid)
		return nil, fmt.Errorf("write tun resolv: %w", err)
	}

	// Write state file
	stateMap := map[string]string{
		"XRAY_PID":           fmt.Sprint(pid),
		"TUN_INTERFACE":      tunName,
		"PROFILE_ID":         s.store.ActiveSelection.ProfileID,
		"NODE_ID":            s.store.ActiveSelection.NodeID,
		"FWMARK":             fmt.Sprintf("%d", fwmark),
		"TABLE":              fmt.Sprintf("%d", table),
		"RUNTIME_IMPL":       "xray",
		"STARTED_AT":         domain.ISONow(),
	}
	if err := runtime.WriteStateFile(s.paths.StateFile, stateMap); err != nil {
		runtime.RestoreResolvConf(s.paths.ResolvBackup)
		runtime.TeardownTun(tunName, table, fwmark)
		runtime.StopXray(pid)
		return nil, fmt.Errorf("write state: %w", err)
	}

	return map[string]interface{}{
		"ok":  true,
		"pid": pid,
	}, nil
}

// hStop tears down the VPN tunnel.
func (s *Server) hStop(params json.RawMessage) (interface{}, error) {
	state := runtime.ReadStateFile(s.paths.StateFile)
	if state == nil {
		return map[string]bool{"ok": true}, nil
	}

	// Stop xray
	if pidStr, ok := state["XRAY_PID"]; ok {
		var pid int
		fmt.Sscanf(pidStr, "%d", &pid)
		if pid > 0 {
			runtime.StopXray(pid)
		}
	}

	// Teardown TUN
	tunName := "tun0"
	if tn, ok := state["TUN_INTERFACE"]; ok && tn != "" {
		tunName = tn
	}
	table := 7073
	if tbl, ok := state["TABLE"]; ok && tbl != "" {
		fmt.Sscanf(tbl, "%d", &table)
	}
	fwmark := 0x7073
	if fm, ok := state["FWMARK"]; ok && fm != "" {
		fmt.Sscanf(fm, "%d", &fwmark)
	}
	runtime.TeardownTun(tunName, table, fwmark)

	// Restore DNS
	runtime.RestoreResolvConf(s.paths.ResolvBackup)

	// Clear state file
	runtime.WriteStateFile(s.paths.StateFile, map[string]string{})

	return map[string]bool{"ok": true}, nil
}

// hDiagnosticsCapture runs the capture-xray-tun-state.sh script.
func (s *Server) hDiagnosticsCapture(params json.RawMessage) (interface{}, error) {
	scriptPath := filepath.Join(s.projectRoot, "libexec", "capture-xray-tun-state.sh")

	output, err := shell.Run("bash", scriptPath)
	if err != nil {
		// Non-zero exit is acceptable for diagnostics
		return map[string]interface{}{
			"output": output,
			"ok":     false,
			"error":  err.Error(),
		}, nil
	}

	return map[string]interface{}{
		"output": output,
		"ok":     true,
	}, nil
}

// ---------------------------------------------------------------------------
// Node handlers
// ---------------------------------------------------------------------------

type nodesListResult struct {
	Profiles []domain.Profile `json:"profiles"`
}

func (s *Server) hNodesList(params json.RawMessage) (interface{}, error) {
	s.reloadStore()
	return nodesListResult{Profiles: s.store.Profiles}, nil
}

type nodesActivateParams struct {
	ProfileID string `json:"profile_id"`
	NodeID    string `json:"node_id"`
	Source    string `json:"source,omitempty"`
}

func (s *Server) hNodesActivate(params json.RawMessage) (interface{}, error) {
	var p nodesActivateParams
	if err := json.Unmarshal(params, &p); err != nil {
		return nil, fmt.Errorf("invalid params: %w", err)
	}
	if p.ProfileID == "" {
		return nil, fmt.Errorf("profile_id is required")
	}
	if p.NodeID == "" {
		return nil, fmt.Errorf("node_id is required")
	}
	if p.Source == "" {
		p.Source = "manual"
	}

	s.reloadStore()
	_, node := store.FindNode(s.store, p.ProfileID, p.NodeID)
	if node == nil {
		return nil, fmt.Errorf("node %s not found in profile %s", p.NodeID, p.ProfileID)
	}

	store.ActivateNode(s.store, p.ProfileID, p.NodeID, p.Source)
	if err := store.SaveStore(s.paths, s.store); err != nil {
		return nil, fmt.Errorf("save store: %w", err)
	}

	return map[string]bool{"ok": true}, nil
}

type nodesDeleteParams struct {
	ProfileID string `json:"profile_id"`
	NodeID    string `json:"node_id"`
}

func (s *Server) hNodesDelete(params json.RawMessage) (interface{}, error) {
	var p nodesDeleteParams
	if err := json.Unmarshal(params, &p); err != nil {
		return nil, fmt.Errorf("invalid params: %w", err)
	}

	s.reloadStore()
	if err := store.DeleteNode(s.store, p.ProfileID, p.NodeID); err != nil {
		return nil, err
	}
	if err := store.SaveStore(s.paths, s.store); err != nil {
		return nil, fmt.Errorf("save store: %w", err)
	}

	return map[string]bool{"ok": true}, nil
}

// ---------------------------------------------------------------------------
// Subscription handlers
// ---------------------------------------------------------------------------

type subscriptionsListResult struct {
	Subscriptions []domain.Subscription `json:"subscriptions"`
}

func (s *Server) hSubscriptionsList(params json.RawMessage) (interface{}, error) {
	s.reloadStore()
	return subscriptionsListResult{Subscriptions: s.store.Subscriptions}, nil
}

type subscriptionsAddParams struct {
	Name string `json:"name"`
	URL  string `json:"url"`
}

func (s *Server) hSubscriptionsAdd(params json.RawMessage) (interface{}, error) {
	var p subscriptionsAddParams
	if err := json.Unmarshal(params, &p); err != nil {
		return nil, fmt.Errorf("invalid params: %w", err)
	}
	if p.URL == "" {
		return nil, fmt.Errorf("url is required")
	}
	if p.Name == "" {
		p.Name = p.URL
	}

	s.reloadStore()
	store.AddSubscription(s.store, p.Name, p.URL)
	if err := store.SaveStore(s.paths, s.store); err != nil {
		return nil, fmt.Errorf("save store: %w", err)
	}

	// Find the newly added subscription (last one)
	sub := &s.store.Subscriptions[len(s.store.Subscriptions)-1]
	profile := store.FindProfile(s.store, sub.ProfileID)

	return map[string]interface{}{
		"ok":              true,
		"subscription_id": sub.ID,
		"profile_id":      sub.ProfileID,
		"node_count":      len(profile.Nodes),
	}, nil
}

type subscriptionsRefreshParams struct {
	SubscriptionID string `json:"subscription_id"`
}

func (s *Server) hSubscriptionsRefresh(params json.RawMessage) (interface{}, error) {
	var p subscriptionsRefreshParams
	if err := json.Unmarshal(params, &p); err != nil {
		return nil, fmt.Errorf("invalid params: %w", err)
	}
	if p.SubscriptionID == "" {
		return nil, fmt.Errorf("subscription_id is required")
	}

	s.reloadStore()
	sub := store.FindSubscription(s.store, p.SubscriptionID)
	if sub == nil {
		return nil, fmt.Errorf("subscription %s not found", p.SubscriptionID)
	}

	nodes, fetchErr := fetchAndParseSubscription(sub.URL)
	if fetchErr != nil {
		sub.LastError = fetchErr.Error()
		sub.LastStatus = "error"
		store.SaveStore(s.paths, s.store)
		return nil, fetchErr
	}

	profile := store.FindProfile(s.store, sub.ProfileID)
	if profile == nil {
		return nil, fmt.Errorf("profile %s not found", sub.ProfileID)
	}

	// Replace nodes for this profile
	now := domain.ISONow()
	for i := range nodes {
		nodes[i].Origin = domain.NodeOrigin{Kind: "subscription", SubscriptionID: sub.ID}
		if nodes[i].CreatedAt == "" {
			nodes[i].CreatedAt = now
		}
		nodes[i].UpdatedAt = now
		nodes[i].Enabled = true
	}
	profile.Nodes = nodes

	sub.LastSuccessAt = now
	sub.LastStatus = "ok"
	sub.LastError = ""

	if err := store.SaveStore(s.paths, s.store); err != nil {
		return nil, fmt.Errorf("save store: %w", err)
	}

	return map[string]interface{}{
		"ok":         true,
		"node_count": len(nodes),
	}, nil
}

type subscriptionsRefreshAllResult struct {
	Results []subscriptionRefreshResult `json:"results"`
}

type subscriptionRefreshResult struct {
	SubscriptionID string `json:"subscription_id"`
	Ok             bool   `json:"ok"`
	Error          string `json:"error,omitempty"`
	NodeCount      int    `json:"node_count,omitempty"`
}

func (s *Server) hSubscriptionsRefreshAll(params json.RawMessage) (interface{}, error) {
	s.reloadStore()

	results := make([]subscriptionRefreshResult, 0, len(s.store.Subscriptions))
	for i := range s.store.Subscriptions {
		sub := &s.store.Subscriptions[i]
		nodes, err := fetchAndParseSubscription(sub.URL)
		if err != nil {
			sub.LastError = err.Error()
			sub.LastStatus = "error"
			results = append(results, subscriptionRefreshResult{
				SubscriptionID: sub.ID,
				Ok:             false,
				Error:          err.Error(),
			})
			continue
		}

		profile := store.FindProfile(s.store, sub.ProfileID)
		if profile == nil {
			continue
		}

		now := domain.ISONow()
		for i := range nodes {
			nodes[i].Origin = domain.NodeOrigin{Kind: "subscription", SubscriptionID: sub.ID}
			if nodes[i].CreatedAt == "" {
				nodes[i].CreatedAt = now
			}
			nodes[i].UpdatedAt = now
			nodes[i].Enabled = true
		}
		profile.Nodes = nodes

		sub.LastSuccessAt = now
		sub.LastStatus = "ok"
		sub.LastError = ""

		results = append(results, subscriptionRefreshResult{
			SubscriptionID: sub.ID,
			Ok:             true,
			NodeCount:      len(nodes),
		})
	}

	if err := store.SaveStore(s.paths, s.store); err != nil {
		return nil, fmt.Errorf("save store: %w", err)
	}

	return subscriptionsRefreshAllResult{Results: results}, nil
}

type subscriptionsDeleteParams struct {
	SubscriptionID string `json:"subscription_id"`
}

func (s *Server) hSubscriptionsDelete(params json.RawMessage) (interface{}, error) {
	var p subscriptionsDeleteParams
	if err := json.Unmarshal(params, &p); err != nil {
		return nil, fmt.Errorf("invalid params: %w", err)
	}

	s.reloadStore()
	if err := store.DeleteSubscription(s.store, p.SubscriptionID); err != nil {
		return nil, err
	}
	if err := store.SaveStore(s.paths, s.store); err != nil {
		return nil, fmt.Errorf("save store: %w", err)
	}

	return map[string]bool{"ok": true}, nil
}

// ---------------------------------------------------------------------------
// Profile handlers
// ---------------------------------------------------------------------------

type profilesListResult struct {
	Profiles []domain.Profile `json:"profiles"`
}

func (s *Server) hProfilesList(params json.RawMessage) (interface{}, error) {
	s.reloadStore()
	return profilesListResult{Profiles: s.store.Profiles}, nil
}

type profilesDeleteParams struct {
	ProfileID string `json:"profile_id"`
}

func (s *Server) hProfilesDelete(params json.RawMessage) (interface{}, error) {
	var p profilesDeleteParams
	if err := json.Unmarshal(params, &p); err != nil {
		return nil, fmt.Errorf("invalid params: %w", err)
	}

	s.reloadStore()
	if err := store.DeleteProfile(s.store, p.ProfileID); err != nil {
		return nil, err
	}
	if err := store.SaveStore(s.paths, s.store); err != nil {
		return nil, fmt.Errorf("save store: %w", err)
	}

	return map[string]bool{"ok": true}, nil
}

// ---------------------------------------------------------------------------
// Routing profile handlers
// ---------------------------------------------------------------------------

type routingProfilesListResult struct {
	Enabled         bool                       `json:"enabled"`
	ActiveProfileID string                     `json:"active_profile_id,omitempty"`
	Profiles        []domain.RoutingProfile    `json:"profiles"`
	Geodata         domain.RoutingGeodataState `json:"geodata"`
}

func (s *Server) hRoutingProfilesList(params json.RawMessage) (interface{}, error) {
	s.reloadStore()
	return routingProfilesListResult{
		Enabled:         s.store.Routing.Enabled,
		ActiveProfileID: s.store.Routing.ActiveProfileID,
		Profiles:        s.store.Routing.Profiles,
		Geodata:         s.store.Routing.Geodata,
	}, nil
}

type routingProfilesImportParams struct {
	Payload        string `json:"payload"`
	SubscriptionID string `json:"subscription_id,omitempty"`
	ProviderID     string `json:"provider_id,omitempty"`
}

func (s *Server) hRoutingProfilesImport(params json.RawMessage) (interface{}, error) {
	var p routingProfilesImportParams
	if err := json.Unmarshal(params, &p); err != nil {
		return nil, fmt.Errorf("invalid params: %w", err)
	}
	if p.Payload == "" {
		return nil, fmt.Errorf("payload is required")
	}

	s.reloadStore()

	rp, _, err := routing.ImportRoutingProfile(s.store, p.Payload)
	if err != nil {
		return nil, fmt.Errorf("import routing profile: %w", err)
	}

	if err := store.SaveStore(s.paths, s.store); err != nil {
		return nil, fmt.Errorf("save store: %w", err)
	}

	return map[string]interface{}{
		"ok":                 true,
		"routing_profile_id": rp.ID,
		"name":               rp.Name,
	}, nil
}

type routingProfilesActivateParams struct {
	ProfileID string `json:"profile_id"`
}

func (s *Server) hRoutingProfilesActivate(params json.RawMessage) (interface{}, error) {
	var p routingProfilesActivateParams
	if err := json.Unmarshal(params, &p); err != nil {
		return nil, fmt.Errorf("invalid params: %w", err)
	}

	s.reloadStore()
	rp := store.FindRoutingProfile(s.store, p.ProfileID)
	if rp == nil {
		return nil, fmt.Errorf("routing profile %s not found", p.ProfileID)
	}

	s.store.Routing.ActiveProfileID = p.ProfileID
	s.store.Routing.Enabled = true

	if err := store.SaveStore(s.paths, s.store); err != nil {
		return nil, fmt.Errorf("save store: %w", err)
	}

	return map[string]bool{"ok": true}, nil
}

func (s *Server) hRoutingProfilesClear(params json.RawMessage) (interface{}, error) {
	s.reloadStore()
	s.store.Routing.ActiveProfileID = ""
	s.store.Routing.Enabled = false

	if err := store.SaveStore(s.paths, s.store); err != nil {
		return nil, fmt.Errorf("save store: %w", err)
	}

	return map[string]bool{"ok": true}, nil
}

type routingEnabledSetParams struct {
	Enabled bool `json:"enabled"`
}

func (s *Server) hRoutingEnabledSet(params json.RawMessage) (interface{}, error) {
	var p routingEnabledSetParams
	if err := json.Unmarshal(params, &p); err != nil {
		return nil, fmt.Errorf("invalid params: %w", err)
	}

	s.reloadStore()
	s.store.Routing.Enabled = p.Enabled

	if err := store.SaveStore(s.paths, s.store); err != nil {
		return nil, fmt.Errorf("save store: %w", err)
	}

	return map[string]bool{"ok": true}, nil
}

func (s *Server) hRoutingGeodataPrepare(params json.RawMessage) (interface{}, error) {
	s.reloadStore()

	geoipURL := routing.DefaultGeoIPURL
	geositeURL := routing.DefaultGeositeURL

	activeRP := store.GetActiveRoutingProfile(s.store)
	if activeRP != nil {
		if activeRP.GeoIPURL != "" {
			geoipURL = activeRP.GeoIPURL
		}
		if activeRP.GeositeURL != "" {
			geositeURL = activeRP.GeositeURL
		}
	}

	s.store.Routing.Geodata.GeoIPURL = geoipURL
	s.store.Routing.Geodata.GeositeURL = geositeURL
	s.store.Routing.Geodata.GeoIPPath = s.paths.GeoIPAssetFile
	s.store.Routing.Geodata.GeositePath = s.paths.GeositeAssetFile
	s.store.Routing.Geodata.AssetDir = s.paths.XrayAssetDir

	if err := routing.DownloadGeodata(geoipURL, geositeURL, s.paths.XrayAssetDir); err != nil {
		s.store.Routing.Geodata.Status = "error"
		s.store.Routing.Geodata.Error = err.Error()
		s.store.Routing.Geodata.Ready = false
		store.SaveStore(s.paths, s.store)
		return nil, fmt.Errorf("download geodata: %w", err)
	}

	s.store.Routing.Geodata.Status = "ready"
	s.store.Routing.Geodata.Ready = true
	s.store.Routing.Geodata.Error = ""
	s.store.Routing.Geodata.GeoIPExists = fileExists(s.paths.GeoIPAssetFile)
	s.store.Routing.Geodata.GeositeExists = fileExists(s.paths.GeositeAssetFile)

	if err := store.SaveStore(s.paths, s.store); err != nil {
		return nil, fmt.Errorf("save store: %w", err)
	}

	return map[string]bool{"ok": true}, nil
}

// ---------------------------------------------------------------------------
// Links import handler
// ---------------------------------------------------------------------------

type linksImportParams struct {
	URIs      []string `json:"uris"`
	ProfileID string   `json:"profile_id,omitempty"`
}

func (s *Server) hLinksImport(params json.RawMessage) (interface{}, error) {
	var p linksImportParams
	if err := json.Unmarshal(params, &p); err != nil {
		return nil, fmt.Errorf("invalid params: %w", err)
	}
	if len(p.URIs) == 0 {
		return nil, fmt.Errorf("uris is required")
	}

	s.reloadStore()

	targetProfileID := p.ProfileID
	if targetProfileID == "" {
		targetProfileID = "manual"
	}

	profile := store.FindProfile(s.store, targetProfileID)
	if profile == nil {
		return nil, fmt.Errorf("profile %s not found", targetProfileID)
	}

	imported := 0
	now := domain.ISONow()
	for _, uri := range p.URIs {
		if uri == "" {
			continue
		}
		parsed, err := parser.ParseProxyURI(uri)
		if err != nil {
			continue
		}
		node := parsedNodeToDomain(parsed)
		if node.ID == "" {
			node.ID = "node-" + store.RandHex(16)
		}
		node.RawURI = uri
		node.Origin = domain.NodeOrigin{Kind: "manual"}
		node.Enabled = true
		node.CreatedAt = now
		node.UpdatedAt = now
		profile.Nodes = append(profile.Nodes, *node)
		imported++
	}

	if err := store.SaveStore(s.paths, s.store); err != nil {
		return nil, fmt.Errorf("save store: %w", err)
	}

	return map[string]interface{}{
		"ok":       true,
		"imported": imported,
	}, nil
}

// ---------------------------------------------------------------------------
// Ping handler
// ---------------------------------------------------------------------------

type pingParams struct {
	ProfileID string `json:"profile_id"`
	NodeID    string `json:"node_id"`
}

func (s *Server) hPing(params json.RawMessage) (interface{}, error) {
	var p pingParams
	if err := json.Unmarshal(params, &p); err != nil {
		return nil, fmt.Errorf("invalid params: %w", err)
	}

	s.reloadStore()
	_, node := store.FindNode(s.store, p.ProfileID, p.NodeID)
	if node == nil {
		return nil, fmt.Errorf("node %s not found in profile %s", p.NodeID, p.ProfileID)
	}

	latency, err := network.PingNode(node, 5*time.Second)
	if err != nil {
		return map[string]interface{}{
			"ok":    false,
			"error": err.Error(),
		}, nil
	}

	return map[string]interface{}{
		"ok":         true,
		"latency_ms": latency,
	}, nil
}

// ---------------------------------------------------------------------------
// Settings handlers
// ---------------------------------------------------------------------------

func (s *Server) hSettingsGet(params json.RawMessage) (interface{}, error) {
	data, err := os.ReadFile(s.paths.GUISettingsFile)
	if err != nil {
		if os.IsNotExist(err) {
			return map[string]interface{}{}, nil
		}
		return nil, fmt.Errorf("read settings: %w", err)
	}

	var settings map[string]interface{}
	if err := json.Unmarshal(data, &settings); err != nil {
		return nil, fmt.Errorf("parse settings: %w", err)
	}

	return settings, nil
}

type settingsSaveParams struct {
	Settings map[string]interface{} `json:"settings"`
}

func (s *Server) hSettingsSave(params json.RawMessage) (interface{}, error) {
	var p settingsSaveParams
	if err := json.Unmarshal(params, &p); err != nil {
		return nil, fmt.Errorf("invalid params: %w", err)
	}

	data, err := json.MarshalIndent(p.Settings, "", "  ")
	if err != nil {
		return nil, fmt.Errorf("marshal settings: %w", err)
	}

	if err := os.WriteFile(s.paths.GUISettingsFile, data, 0644); err != nil {
		return nil, fmt.Errorf("write settings: %w", err)
	}

	return map[string]bool{"ok": true}, nil
}

// ---------------------------------------------------------------------------
// Artifacts handlers
// ---------------------------------------------------------------------------

func (s *Server) hArtifactsCleanup(params json.RawMessage) (interface{}, error) {
	entries, err := os.ReadDir(s.paths.StoreDir)
	if err != nil {
		return nil, fmt.Errorf("read store dir: %w", err)
	}

	removed := 0
	for _, entry := range entries {
		name := entry.Name()
		// Remove old generated config files (not the active one)
		if name == "generated-xray-config.json" {
			os.Remove(filepath.Join(s.paths.StoreDir, name))
			removed++
		}
		// Remove tmp files
		if filepath.Ext(name) == ".tmp" {
			os.Remove(filepath.Join(s.paths.StoreDir, name))
			removed++
		}
	}

	return map[string]interface{}{
		"ok":      true,
		"removed": removed,
	}, nil
}

type artifactEntry struct {
	Name  string `json:"name"`
	Size  int64  `json:"size"`
	IsDir bool   `json:"is_dir"`
}

func (s *Server) hArtifactsAudit(params json.RawMessage) (interface{}, error) {
	entries, err := os.ReadDir(s.paths.StoreDir)
	if err != nil {
		return nil, fmt.Errorf("read store dir: %w", err)
	}

	files := make([]artifactEntry, 0, len(entries))
	for _, entry := range entries {
		info, _ := entry.Info()
		size := int64(0)
		if info != nil {
			size = info.Size()
		}
		files = append(files, artifactEntry{
			Name:  entry.Name(),
			Size:  size,
			IsDir: entry.IsDir(),
		})
	}

	return map[string]interface{}{
		"dir":   s.paths.StoreDir,
		"files": files,
	}, nil
}

// ---------------------------------------------------------------------------
// System handlers
// ---------------------------------------------------------------------------

func (s *Server) hShutdown(params json.RawMessage) (interface{}, error) {
	return map[string]bool{"ok": true}, nil
}

func (s *Server) hStoreSnapshot(params json.RawMessage) (interface{}, error) {
	s.reloadStore()
	summary := store.StoreSummary(s.store)
	return map[string]interface{}{
		"version":           s.store.Version,
		"profiles":          summary["profiles"],
		"nodes":             summary["nodes"],
		"subscriptions":     summary["subscriptions"],
		"routing_profiles":  len(s.store.Routing.Profiles),
		"routing_enabled":   s.store.Routing.Enabled,
		"active_node":       s.store.ActiveSelection.NodeID,
	}, nil
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// reloadStore re-reads the store from disk to ensure fresh state.
func (s *Server) reloadStore() {
	st, err := store.LoadStore(s.paths)
	if err != nil {
		// Keep existing in-memory store if reload fails
		return
	}
	s.store = st
}

// fetchAndParseSubscription downloads and parses a subscription URL.
// Returns parsed domain.Node list.
func fetchAndParseSubscription(url string) ([]domain.Node, error) {
	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Get(url)
	if err != nil {
		return nil, fmt.Errorf("fetch subscription: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("subscription returned status %d", resp.StatusCode)
	}

	body, err := io.ReadAll(io.LimitReader(resp.Body, 10*1024*1024)) // 10 MB limit
	if err != nil {
		return nil, fmt.Errorf("read subscription body: %w", err)
	}

	rawURIs, _, err := parser.ParseSubscriptionPayload(body)
	if err != nil {
		return nil, fmt.Errorf("parse subscription payload: %w", err)
	}

	nodes := make([]domain.Node, 0, len(rawURIs))
	for _, rawURI := range rawURIs {
		parsed, err := parser.ParseProxyURI(rawURI)
		if err != nil {
			// Skip unparseable URIs
			continue
		}
		node := parsedNodeToDomain(parsed)
		node.RawURI = rawURI
		nodes = append(nodes, *node)
	}

	return nodes, nil
}

// parsedNodeToDomain converts a parser.ParsedNode to a domain.Node.
func parsedNodeToDomain(p *parser.ParsedNode) *domain.Node {
	node := &domain.Node{
		Protocol: p.Protocol,
		RawURI:   p.RawURI,
		Name:     p.DisplayName,
		Normalized: domain.NodeAddress{
			Protocol:      p.Protocol,
			Address:       p.Address,
			Port:          p.Port,
			UUID:          p.UUID,
			Password:      p.Password,
			Method:        p.Method,
			Flow:          p.Flow,
			Encryption:    p.Encryption,
			Network:       p.Network,
			Security:      p.Security,
			Host:          p.Host,
			Path:          p.Path,
			ServerName:    p.ServerName,
			ServiceName:   p.ServiceName,
			GRPCAuthority: p.GRPCAuthority,
			Fingerprint:   p.Fingerprint,
			PublicKey:     p.PublicKey,
			ShortID:       p.ShortID,
			SpiderX:       p.SpiderX,
			Mode:          p.Mode,
			ALPN:          p.ALPN,
			AllowInsecure: p.AllowInsecure,
			DisplayName:   p.DisplayName,
			RawURI:        p.RawURI,
		},
	}
	if p.DisplayName != "" {
		node.Name = p.DisplayName
	} else {
		node.Name = fmt.Sprintf("%s://%s:%d", p.Protocol, p.Address, p.Port)
	}
	return node
}

// fileExists checks if a file exists.
func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}
