package rpc

// registerHandlers populates the handler map.
// Each key is the JSON-RPC "method" string.
func (s *Server) registerHandlers() {
	s.handlers = map[string]HandlerFunc{
		// Runtime
		"status":              s.hStatus,
		"start":               s.hStart,
		"stop":                s.hStop,
		"diagnostics.capture": s.hDiagnosticsCapture,

		// Nodes
		"nodes.list":     s.hNodesList,
		"nodes.activate": s.hNodesActivate,
		"nodes.delete":   s.hNodesDelete,

		// Subscriptions
		"subscriptions.list":       s.hSubscriptionsList,
		"subscriptions.add":        s.hSubscriptionsAdd,
		"subscriptions.refresh":    s.hSubscriptionsRefresh,
		"subscriptions.refresh_all": s.hSubscriptionsRefreshAll,
		"subscriptions.delete":     s.hSubscriptionsDelete,

		// Profiles
		"profiles.list":   s.hProfilesList,
		"profiles.delete": s.hProfilesDelete,

		// Routing
		"routing.profiles.list":    s.hRoutingProfilesList,
		"routing.profiles.import":  s.hRoutingProfilesImport,
		"routing.profiles.activate": s.hRoutingProfilesActivate,
		"routing.profiles.clear":   s.hRoutingProfilesClear,
		"routing.enabled.set":      s.hRoutingEnabledSet,
		"routing.geodata.prepare":  s.hRoutingGeodataPrepare,

		// Links
		"links.import": s.hLinksImport,

		// Ping
		"ping": s.hPing,

		// Settings
		"settings.get":  s.hSettingsGet,
		"settings.save": s.hSettingsSave,

		// Artifacts
		"artifacts.cleanup": s.hArtifactsCleanup,
		"artifacts.audit":   s.hArtifactsAudit,

		// System
		"shutdown":       s.hShutdown,
		"store.snapshot": s.hStoreSnapshot,
	}
}
