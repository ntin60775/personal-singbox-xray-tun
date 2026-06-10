package domain

import (
	"encoding/json"
	"time"
)

// NodeAddress represents connection endpoint info for a parsed proxy node.
type NodeAddress struct {
	Protocol string `json:"protocol"`
	Address  string `json:"address"`
	Port     int    `json:"port"`
	// Protocol-specific fields
	UUID      string `json:"uuid,omitempty"`
	Password  string `json:"password,omitempty"`
	Method    string `json:"method,omitempty"`
	Flow          string   `json:"flow,omitempty"`
	Encryption    string   `json:"encryption,omitempty"`
	AlterID       int      `json:"alter_id,omitempty"`
	Cipher        string   `json:"cipher,omitempty"`
	XhttpExtra    json.RawMessage `json:"xhttp_extra,omitempty"`
	// Stream settings
	Network      string   `json:"network,omitempty"`
	Security     string   `json:"security,omitempty"`
	Host         string   `json:"host,omitempty"`
	Path         string   `json:"path,omitempty"`
	ServerName   string   `json:"server_name,omitempty"`
	ServiceName  string   `json:"service_name,omitempty"`
	GRPCAuthority string  `json:"grpc_authority,omitempty"`
	Fingerprint  string   `json:"fingerprint,omitempty"`
	PublicKey    string   `json:"public_key,omitempty"`
	ShortID      string   `json:"short_id,omitempty"`
	SpiderX      string   `json:"spider_x,omitempty"`
	Mode         string   `json:"mode,omitempty"`
	ALPN         []string `json:"alpn,omitempty"`
	AllowInsecure bool    `json:"allow_insecure,omitempty"`
	DisplayName  string   `json:"display_name,omitempty"`
	RawURI       string   `json:"raw_uri,omitempty"`
}

// TransportHint specifies network interface and fwmark for outbound traffic.
type TransportHint struct {
	DefaultInterface string `json:"default_interface,omitempty"`
	DefaultMark      int    `json:"default_mark,omitempty"`
}

// NodeOrigin describes where a node came from.
type NodeOrigin struct {
	Kind           string `json:"kind"`
	SubscriptionID string `json:"subscription_id,omitempty"`
}

// Node is a single proxy endpoint parsed from a URI.
type Node struct {
	ID           string            `json:"id"`
	Fingerprint  string            `json:"fingerprint"`
	Name         string            `json:"name"`
	Protocol     string            `json:"protocol"`
	RawURI       string            `json:"raw_uri"`
	Origin       NodeOrigin        `json:"origin"`
	Enabled      bool              `json:"enabled"`
	UserRenamed  bool              `json:"user_renamed"`
	ParseError   string            `json:"parse_error"`
	Normalized   NodeAddress       `json:"normalized"`
	TransportHint *TransportHint   `json:"transport_hint,omitempty"`
	CreatedAt    string            `json:"created_at"`
	UpdatedAt    string            `json:"updated_at"`
}

// Profile is a group of nodes (manual or from a subscription).
type Profile struct {
	ID                    string `json:"id"`
	Kind                  string `json:"kind"`
	Name                  string `json:"name"`
	Enabled               bool   `json:"enabled"`
	SourceSubscriptionID  string `json:"source_subscription_id,omitempty"`
	Nodes                 []Node `json:"nodes"`
}

// Subscription represents a remote subscription endpoint.
type Subscription struct {
	ID               string `json:"id"`
	URL              string `json:"url"`
	Name             string `json:"name"`
	Enabled          bool   `json:"enabled"`
	ETag             string `json:"etag,omitempty"`
	LastModified     string `json:"last_modified,omitempty"`
	LastSuccessAt    string `json:"last_success_at,omitempty"`
	LastStatus       string `json:"last_status,omitempty"`
	LastError        string `json:"last_error,omitempty"`
	ProfileID        string `json:"profile_id"`
	ProviderID       string `json:"provider_id,omitempty"`
	ProviderIDSource string `json:"provider_id_source,omitempty"`
	RoutingProfileID string `json:"routing_profile_id,omitempty"`
	LastRoutingStatus string `json:"last_routing_status,omitempty"`
	LastRoutingError string `json:"last_routing_error,omitempty"`
}

// ActiveSelection stores the currently selected node.
type ActiveSelection struct {
	ProfileID    string `json:"profile_id,omitempty"`
	NodeID       string `json:"node_id,omitempty"`
	ActivatedAt  string `json:"activated_at,omitempty"`
	Source       string `json:"source,omitempty"`
}

// RoutingProfile represents a routing profile.
type RoutingProfile struct {
	ID                    string   `json:"id"`
	Name                  string   `json:"name"`
	NameKey               string   `json:"name_key,omitempty"`
	Enabled               bool     `json:"enabled"`
	AutoManaged           bool     `json:"auto_managed"`
	SourceSubscriptionID  string   `json:"source_subscription_id,omitempty"`
	ProviderID            string   `json:"provider_id,omitempty"`
	SourceKind            string   `json:"source_kind,omitempty"`
	SourceFormat          string   `json:"source_format,omitempty"`
	ActivationMode        string   `json:"activation_mode,omitempty"`
	RawPayload            map[string]any `json:"raw_payload,omitempty"`
	GlobalProxy           bool     `json:"global_proxy"`
	DomainStrategy        string   `json:"domain_strategy"`
	GeoIPURL              string   `json:"geoip_url,omitempty"`
	GeositeURL            string   `json:"geosite_url,omitempty"`
	DirectSites           []string `json:"direct_sites,omitempty"`
	DirectIP              []string `json:"direct_ip,omitempty"`
	ProxySites            []string `json:"proxy_sites,omitempty"`
	ProxyIP               []string `json:"proxy_ip,omitempty"`
	BlockSites            []string `json:"block_sites,omitempty"`
	BlockIP               []string `json:"block_ip,omitempty"`
	DNSHosts              map[string]string `json:"dns_hosts,omitempty"`
	DomesticDNSDomain     string   `json:"domestic_dns_domain,omitempty"`
	DomesticDNSIP         string   `json:"domestic_dns_ip,omitempty"`
	DomesticDNSType       string   `json:"domestic_dns_type,omitempty"`
	RemoteDNSDomain       string   `json:"remote_dns_domain,omitempty"`
	RemoteDNSIP           string   `json:"remote_dns_ip,omitempty"`
	RemoteDNSType         string   `json:"remote_dns_type,omitempty"`
	FakeDNS               bool     `json:"fake_dns"`
	RouteOrder            []string `json:"route_order,omitempty"`
	LastUpdated           string   `json:"last_updated,omitempty"`
	SupportedEntryCount   int      `json:"supported_entry_count"`
	StoredOnlyFields      []string `json:"stored_only_fields,omitempty"`
	IgnoredFields         []string `json:"ignored_fields,omitempty"`
	UnknownFields         []string `json:"unknown_fields,omitempty"`
	CreatedAt             string   `json:"created_at"`
	UpdatedAt             string   `json:"updated_at"`
}

// RoutingGeodataState holds the state of geodata assets.
type RoutingGeodataState struct {
	Status       string `json:"status"`
	Ready        bool   `json:"ready"`
	Error        string `json:"error,omitempty"`
	GeoIPURL     string `json:"geoip_url,omitempty"`
	GeositeURL   string `json:"geosite_url,omitempty"`
	GeoIPPath    string `json:"geoip_path,omitempty"`
	GeositePath  string `json:"geosite_path,omitempty"`
	AssetDir     string `json:"asset_dir,omitempty"`
	GeoIPExists  bool   `json:"geoip_exists"`
	GeositeExists bool  `json:"geosite_exists"`
}

// RoutingState is the routing section of the store.
type RoutingState struct {
	Enabled        bool                   `json:"enabled"`
	ActiveProfileID string                `json:"active_profile_id,omitempty"`
	Profiles       []RoutingProfile        `json:"profiles"`
	RuntimeReady   bool                   `json:"runtime_ready"`
	RuntimeError   string                 `json:"runtime_error,omitempty"`
	Geodata        RoutingGeodataState    `json:"geodata"`
}

// StoreMeta contains metadata about the store itself.
type StoreMeta struct {
	InitializedAt            string `json:"initialized_at"`
	MigratedFromSingleConfigAt string `json:"migrated_from_single_config_at,omitempty"`
}

// Store is the root data structure matching store.json.
type Store struct {
	Version        int              `json:"version"`
	Profiles       []Profile        `json:"profiles"`
	Subscriptions  []Subscription   `json:"subscriptions"`
	ActiveSelection ActiveSelection `json:"active_selection"`
	Routing        RoutingState     `json:"routing"`
	Meta           StoreMeta        `json:"meta"`
}

// ISO timestamp helpers
func ISONow() string {
	return time.Now().Format("2006-01-02T15:04:05-07:00")
}
