package routing

import (
	"crypto/rand"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"

	"github.com/subvost/xray-tun/backend/internal/domain"
)

// Default geodata URLs
const (
	DefaultGeoIPURL   = "https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geoip.dat"
	DefaultGeositeURL = "https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geosite.dat"
)

// Supported domain strategies for Xray routing.
var SupportedDomainStrategies = map[string]bool{
	"AsIs":         true,
	"IPIfNonMatch": true,
	"IPOnDemand":   true,
	"UseIP":        true,
}

var happURIPrefixes = []string{"happ://routing/add/", "happ://routing/onadd/"}

var happActivationMode = map[string]string{
	"happ://routing/add/":   "add",
	"happ://routing/onadd/": "onadd",
}

var knownImportKeys = map[string]bool{
	"name":             true,
	"globalproxy":      true,
	"domainstrategy":   true,
	"geoipurl":         true,
	"geositeurl":       true,
	"directsites":      true,
	"directip":         true,
	"proxysites":       true,
	"proxyip":          true,
	"blocksites":       true,
	"blockip":          true,
	"dnshosts":         true,
	"domesticdnsdomain": true,
	"domesticdnsip":    true,
	"domesticdnstype":  true,
	"remotednsdomain":  true,
	"remotednsip":      true,
	"remotednstype":    true,
	"fakedns":          true,
	"routeorder":       true,
	"lastupdated":      true,
}

var storedOnlyFields = map[string]bool{
	"dns_hosts":          true,
	"domestic_dns_domain": true,
	"domestic_dns_ip":    true,
	"domestic_dns_type":  true,
	"remote_dns_domain":  true,
	"remote_dns_ip":      true,
	"remote_dns_type":    true,
	"fake_dns":           true,
	"last_updated":       true,
}

// reNonAlpha splits on non-alpha characters for route order parsing.
var reNonAlpha = regexp.MustCompile(`[^a-z]+`)

// ImportRoutingProfile parses a routing profile input string (hap:// URI, JSON,
// or base64-encoded JSON) and adds or updates it in the store.
// Returns the profile, whether it was created (true) or updated (false), and any error.
func ImportRoutingProfile(store *domain.Store, input string) (*domain.RoutingProfile, bool, error) {
	profile, err := parseRoutingProfileInput(input)
	if err != nil {
		return nil, false, err
	}

	// Check if a profile with this name_key already exists.
	existing := findRoutingProfileByNameKey(store, profile.NameKey)
	if existing != nil {
		// Update existing profile fields while preserving ID and auto-managed state.
		existing.Name = profile.Name
		existing.NameKey = profile.NameKey
		existing.Enabled = profile.Enabled
		existing.SourceKind = profile.SourceKind
		existing.SourceFormat = profile.SourceFormat
		existing.ActivationMode = profile.ActivationMode
		existing.RawPayload = profile.RawPayload
		existing.GlobalProxy = profile.GlobalProxy
		existing.DomainStrategy = profile.DomainStrategy
		existing.GeoIPURL = profile.GeoIPURL
		existing.GeositeURL = profile.GeositeURL
		existing.DirectSites = profile.DirectSites
		existing.DirectIP = profile.DirectIP
		existing.ProxySites = profile.ProxySites
		existing.ProxyIP = profile.ProxyIP
		existing.BlockSites = profile.BlockSites
		existing.BlockIP = profile.BlockIP
		existing.DNSHosts = profile.DNSHosts
		existing.DomesticDNSDomain = profile.DomesticDNSDomain
		existing.DomesticDNSIP = profile.DomesticDNSIP
		existing.DomesticDNSType = profile.DomesticDNSType
		existing.RemoteDNSDomain = profile.RemoteDNSDomain
		existing.RemoteDNSIP = profile.RemoteDNSIP
		existing.RemoteDNSType = profile.RemoteDNSType
		existing.FakeDNS = profile.FakeDNS
		existing.RouteOrder = profile.RouteOrder
		existing.LastUpdated = profile.LastUpdated
		existing.SupportedEntryCount = profile.SupportedEntryCount
		existing.StoredOnlyFields = profile.StoredOnlyFields
		existing.IgnoredFields = profile.IgnoredFields
		existing.UnknownFields = profile.UnknownFields
		existing.UpdatedAt = domain.ISONow()
		return existing, false, nil
	}

	// New profile.
	profile.ID = "rp-" + randHex(8)
	profile.CreatedAt = domain.ISONow()
	profile.UpdatedAt = profile.CreatedAt
	store.Routing.Profiles = append(store.Routing.Profiles, *profile)
	return &store.Routing.Profiles[len(store.Routing.Profiles)-1], true, nil
}

func findRoutingProfileByNameKey(store *domain.Store, nameKey string) *domain.RoutingProfile {
	for i := range store.Routing.Profiles {
		if store.Routing.Profiles[i].NameKey == nameKey {
			return &store.Routing.Profiles[i]
		}
	}
	return nil
}

// parseRoutingProfileInput parses a raw input string into a RoutingProfile.
func parseRoutingProfileInput(rawText string) (*domain.RoutingProfile, error) {
	text := strings.TrimSpace(rawText)
	if text == "" {
		return nil, fmt.Errorf("routing profile input is empty")
	}

	sourceFormat := "json"
	activationMode := "manual"
	payload, err := parsePayload(text, &sourceFormat, &activationMode)
	if err != nil {
		return nil, err
	}

	keyMap := payloadKeyMap(payload)
	name := strings.TrimSpace(coerceString(keyMap["name"], payload["Name"]))
	if name == "" {
		return nil, fmt.Errorf("routing profile must contain a non-empty 'name' field")
	}

	directSites := stringList(keyMap["directsites"])
	directIP := stringList(keyMap["directip"])
	proxySites := stringList(keyMap["proxysites"])
	proxyIP := stringList(keyMap["proxyip"])
	blockSites := stringList(keyMap["blocksites"])
	blockIP := stringList(keyMap["blockip"])

	supportedEntries := len(directSites) + len(directIP) + len(proxySites) + len(proxyIP) + len(blockSites) + len(blockIP)

	unknownFields := make([]string, 0)
	for k := range keyMap {
		if !knownImportKeys[k] {
			unknownFields = append(unknownFields, k)
		}
	}
	sort.Strings(unknownFields)

	storedOnlyPresence := map[string]bool{
		"dns_hosts":           keyMap["dnshosts"] != nil,
		"domestic_dns_domain": keyMap["domesticdnsdomain"] != nil,
		"domestic_dns_ip":    keyMap["domesticdnsip"] != nil,
		"domestic_dns_type":  keyMap["domesticdnstype"] != nil,
		"remote_dns_domain":  keyMap["remotednsdomain"] != nil,
		"remote_dns_ip":      keyMap["remotednsip"] != nil,
		"remote_dns_type":    keyMap["remotednstype"] != nil,
		"fake_dns":           keyMap["fakedns"] != nil,
		"last_updated":       keyMap["lastupdated"] != nil,
	}

	storedOnlyFieldsList := make([]string, 0)
	for field, present := range storedOnlyPresence {
		if present && storedOnlyFields[field] {
			storedOnlyFieldsList = append(storedOnlyFieldsList, field)
		}
	}
	sort.Strings(storedOnlyFieldsList)

	geoipURL := strings.TrimSpace(coerceString(keyMap["geoipurl"]))
	if geoipURL == "" {
		geoipURL = DefaultGeoIPURL
	}
	geositeURL := strings.TrimSpace(coerceString(keyMap["geositeurl"]))
	if geositeURL == "" {
		geositeURL = DefaultGeositeURL
	}

	return &domain.RoutingProfile{
		Name:                name,
		NameKey:             strings.ToLower(name),
		Enabled:             true,
		AutoManaged:         false,
		SourceKind:          "",
		SourceFormat:        sourceFormat,
		ActivationMode:      activationMode,
		RawPayload:          payload,
		GlobalProxy:         coerceBool(keyMap["globalproxy"]),
		DomainStrategy:      normalizeDomainStrategy(keyMap["domainstrategy"]),
		GeoIPURL:            geoipURL,
		GeositeURL:          geositeURL,
		DirectSites:         directSites,
		DirectIP:            directIP,
		ProxySites:          proxySites,
		ProxyIP:             proxyIP,
		BlockSites:          blockSites,
		BlockIP:             blockIP,
		DNSHosts:            stringMap(keyMap["dnshosts"]),
		DomesticDNSDomain:   strings.TrimSpace(coerceString(keyMap["domesticdnsdomain"])),
		DomesticDNSIP:       strings.TrimSpace(coerceString(keyMap["domesticdnsip"])),
		DomesticDNSType:     strings.TrimSpace(coerceString(keyMap["domesticdnstype"])),
		RemoteDNSDomain:     strings.TrimSpace(coerceString(keyMap["remotednsdomain"])),
		RemoteDNSIP:         strings.TrimSpace(coerceString(keyMap["remotednsip"])),
		RemoteDNSType:       strings.TrimSpace(coerceString(keyMap["remotednstype"])),
		FakeDNS:             coerceBool(keyMap["fakedns"]),
		RouteOrder:          normalizeRouteOrder(keyMap["routeorder"]),
		LastUpdated:         strings.TrimSpace(coerceString(keyMap["lastupdated"])),
		SupportedEntryCount: supportedEntries,
		StoredOnlyFields:    storedOnlyFieldsList,
		IgnoredFields:       []string{},
		UnknownFields:       unknownFields,
	}, nil
}

// parsePayload attempts to extract a JSON payload from the input text.
// It mutates sourceFormat and activationMode to reflect the detected input type.
func parsePayload(text string, sourceFormat *string, activationMode *string) (map[string]interface{}, error) {
	for _, prefix := range happURIPrefixes {
		if strings.HasPrefix(text, prefix) {
			data := text[len(prefix):]
			*sourceFormat = "happ_uri"
			*activationMode = happActivationMode[prefix]
			return decodeBase64JSON(data)
		}
	}

	// Check if any line starts with hap:// prefix
	lines := strings.Split(text, "\n")
	var happLines []string
	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if trimmed == "" {
			continue
		}
		for _, prefix := range happURIPrefixes {
			if strings.HasPrefix(trimmed, prefix) {
				happLines = append(happLines, trimmed)
				break
			}
		}
	}
	if len(happLines) == 1 {
		return parsePayload(happLines[0], sourceFormat, activationMode)
	}
	if len(happLines) > 1 {
		return nil, fmt.Errorf("multiple hap://routing URIs found; supply exactly one")
	}

	// Try plain JSON first.
	payload, jsonErr := parseJSONPayload(text)
	if jsonErr == nil {
		*sourceFormat = "json"
		*activationMode = "manual"
		return payload, nil
	}

	// Try base64-encoded JSON.
	payload, b64Err := decodeBase64JSON(text)
	if b64Err == nil {
		*sourceFormat = "base64_json"
		*activationMode = "manual"
		return payload, nil
	}

	return nil, fmt.Errorf("routing profile must be valid JSON or base64-encoded JSON")
}

// parseJSONPayload parses a JSON string and validates it's an object.
func parseJSONPayload(text string) (map[string]interface{}, error) {
	var payload map[string]interface{}
	if err := json.Unmarshal([]byte(text), &payload); err != nil {
		return nil, fmt.Errorf("routing profile is not valid JSON")
	}
	if payload == nil {
		return nil, fmt.Errorf("routing profile must be a JSON object")
	}
	return payload, nil
}

// decodeBase64JSON decodes a base64-encoded (possibly URL-safe) string and parses it as JSON.
func decodeBase64JSON(value string) (map[string]interface{}, error) {
	cleaned := strings.Map(func(r rune) rune {
		if r == ' ' || r == '\n' || r == '\r' || r == '\t' {
			return -1
		}
		return r
	}, value)

	// Add padding if needed.
	if remainder := len(cleaned) % 4; remainder != 0 {
		cleaned += strings.Repeat("=", 4-remainder)
	}

	// Try standard base64 first, then URL-safe.
	decoded, err := base64.StdEncoding.DecodeString(cleaned)
	if err != nil {
		decoded, err = base64.URLEncoding.DecodeString(cleaned)
		if err != nil {
			decoded, err = base64.RawStdEncoding.DecodeString(cleaned)
			if err != nil {
				decoded, err = base64.RawURLEncoding.DecodeString(cleaned)
				if err != nil {
					return nil, fmt.Errorf("failed to decode base64 routing profile")
				}
			}
		}
	}

	return parseJSONPayload(string(decoded))
}

// payloadKeyMap lowercases all keys in a payload map.
func payloadKeyMap(payload map[string]interface{}) map[string]interface{} {
	result := make(map[string]interface{}, len(payload))
	for k, v := range payload {
		result[strings.ToLower(strings.TrimSpace(k))] = v
	}
	return result
}

// coerceBool converts a value to bool. Recognizes "1", "true", "yes", "on" (case-insensitive).
func coerceBool(value interface{}) bool {
	if b, ok := value.(bool); ok {
		return b
	}
	s := strings.TrimSpace(strings.ToLower(coerceString(value)))
	return s == "1" || s == "true" || s == "yes" || s == "on"
}

// coerceString converts a value to string, returning the first non-empty from variadic args.
func coerceString(values ...interface{}) string {
	for _, v := range values {
		if v == nil {
			continue
		}
		if s, ok := v.(string); ok {
			return s
		}
		return fmt.Sprintf("%v", v)
	}
	return ""
}

// stringList extracts a list of non-empty trimmed strings from a JSON array value.
func stringList(value interface{}) []string {
	arr, ok := value.([]interface{})
	if !ok {
		return []string{}
	}
	result := make([]string, 0, len(arr))
	for _, item := range arr {
		if s, ok := item.(string); ok {
			trimmed := strings.TrimSpace(s)
			if trimmed != "" {
				result = append(result, trimmed)
			}
		}
	}
	return result
}

// stringMap extracts a map of string→string from a JSON object value.
func stringMap(value interface{}) map[string]string {
	m, ok := value.(map[string]interface{})
	if !ok {
		return map[string]string{}
	}
	result := make(map[string]string, len(m))
	for k, v := range m {
		vs, okv := v.(string)
		if okv {
			keyTrimmed := strings.TrimSpace(k)
			valTrimmed := strings.TrimSpace(vs)
			if keyTrimmed != "" && valTrimmed != "" {
				result[keyTrimmed] = valTrimmed
			}
		}
	}
	return result
}

// normalizeDomainStrategy validates and returns the domain strategy or "AsIs".
func normalizeDomainStrategy(value interface{}) string {
	raw := strings.TrimSpace(coerceString(value))
	if SupportedDomainStrategies[raw] {
		return raw
	}
	return "AsIs"
}

// normalizeRouteOrder parses a route order string into a list of priorities.
// Defaults to ["block", "direct", "proxy"].
func normalizeRouteOrder(value interface{}) []string {
	raw := strings.TrimSpace(strings.ToLower(coerceString(value)))
	parts := reNonAlpha.Split(raw, -1)
	var cleaned []string
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p == "" {
			continue
		}
		cleaned = append(cleaned, p)
	}

	allowed := map[string]bool{"block": true, "direct": true, "proxy": true}
	var ordered []string
	seen := map[string]bool{}
	for _, part := range cleaned {
		if allowed[part] && !seen[part] {
			ordered = append(ordered, part)
			seen[part] = true
		}
	}
	if len(seen) == 3 {
		return ordered
	}
	return []string{"block", "direct", "proxy"}
}

// DownloadGeodata downloads geoip.dat and geosite.dat from given URLs to assetsDir.
func DownloadGeodata(geoipURL, geositeURL, assetsDir string) error {
	if geoipURL == "" {
		geoipURL = DefaultGeoIPURL
	}
	if geositeURL == "" {
		geositeURL = DefaultGeositeURL
	}

	if !isURLCandidate(geoipURL) {
		return fmt.Errorf("invalid geoip.dat URL: %s", geoipURL)
	}
	if !isURLCandidate(geositeURL) {
		return fmt.Errorf("invalid geosite.dat URL: %s", geositeURL)
	}

	if err := os.MkdirAll(assetsDir, 0700); err != nil {
		return fmt.Errorf("failed to create assets directory: %w", err)
	}

	geoipPath := filepath.Join(assetsDir, "geoip.dat")
	geositePath := filepath.Join(assetsDir, "geosite.dat")

	data, err := downloadFile(geoipURL)
	if err != nil {
		return fmt.Errorf("failed to download geoip.dat: %w", err)
	}
	if err := atomicWriteFile(geoipPath, data); err != nil {
		return fmt.Errorf("failed to write geoip.dat: %w", err)
	}

	data, err = downloadFile(geositeURL)
	if err != nil {
		return fmt.Errorf("failed to download geosite.dat: %w", err)
	}
	if err := atomicWriteFile(geositePath, data); err != nil {
		return fmt.Errorf("failed to write geosite.dat: %w", err)
	}

	return nil
}

// isURLCandidate checks if a value looks like a valid HTTP(S) URL.
func isURLCandidate(value string) bool {
	parsed, err := url.Parse(value)
	if err != nil {
		return false
	}
	scheme := strings.ToLower(parsed.Scheme)
	return (scheme == "http" || scheme == "https") && parsed.Host != ""
}

// downloadFile fetches content from a URL and returns the body bytes.
func downloadFile(targetURL string) ([]byte, error) {
	req, err := http.NewRequest("GET", targetURL, nil)
	if err != nil {
		return nil, fmt.Errorf("creating request: %w", err)
	}
	req.Header.Set("User-Agent", "Subvost-Xray-Tun/1.0")
	req.Header.Set("Accept", "*/*")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("HTTP request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("HTTP %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("reading response: %w", err)
	}
	if len(body) == 0 {
		return nil, fmt.Errorf("downloaded empty file")
	}
	return body, nil
}

// atomicWriteFile writes data to a temporary file then renames it to the target path.
func atomicWriteFile(path string, data []byte) error {
	dir := filepath.Dir(path)
	tmpFile, err := os.CreateTemp(dir, ".tmp-*")
	if err != nil {
		return err
	}
	tmpPath := tmpFile.Name()
	defer os.Remove(tmpPath)

	if _, err := tmpFile.Write(data); err != nil {
		tmpFile.Close()
		return err
	}
	if err := tmpFile.Close(); err != nil {
		return err
	}
	return os.Rename(tmpPath, path)
}

// ---------------------------------------------------------------------------
// Direct routes report
// ---------------------------------------------------------------------------

// BuildDirectRoutesReport constructs a report of direct routes from template config,
// active routing profile, and runtime config.
func BuildDirectRoutesReport(template []byte, activeProfile *domain.RoutingProfile, runtimeConfig []byte) (map[string]interface{}, error) {
	templateConfig := parseJSONToMap(template)
	runtimeMap := parseJSONToMap(runtimeConfig)

	templateEntries := extractDirectRulesFromXrayConfig(templateConfig, "template", "Template", 10, "Hardcoded in the application's base template.")
	profileEntries := extractDirectRulesFromRoutingProfile(activeProfile)
	runtimeEntries := extractDirectRulesFromXrayConfig(runtimeMap, "runtime", "Runtime config", 30, "Present in the active or prepared Xray config.")

	entries := annotateDirectReportConflicts(templateEntries, profileEntries, runtimeEntries, activeProfile)

	conflicts := make([]map[string]interface{}, 0)
	for _, entry := range entries {
		for _, conflict := range entry["conflicts"].([]map[string]interface{}) {
			c := map[string]interface{}{
				"entry_id": entry["id"],
				"source":   entry["source"],
				"value":    entry["value"],
				"kind":     entry["kind"],
			}
			for k, v := range conflict {
				c[k] = v
			}
			conflicts = append(conflicts, c)
		}
	}

	return map[string]interface{}{
		"title":          "Direct routes",
		"subtitle":       "Addresses and groups that go directly, bypassing VPN.",
		"priority_order": []string{"template", "profile", "catchall"},
		"priority_note":  "When conflicting, a template rule applies before an active routing profile; catch-all remains last.",
		"summary": map[string]interface{}{
			"template_count":     len(templateEntries),
			"profile_count":      len(profileEntries),
			"runtime_count":      len(runtimeEntries),
			"conflict_count":     len(conflicts),
			"runtime_available":  len(runtimeMap) > 0,
			"template_catchall":  catchallAction(templateConfig),
			"runtime_catchall":   catchallAction(runtimeMap),
		},
		"entries":   entries,
		"conflicts": conflicts,
	}, nil
}

// parseJSONToMap parses JSON bytes into a map, returning nil on failure.
func parseJSONToMap(data []byte) map[string]interface{} {
	if len(data) == 0 {
		return nil
	}
	var m map[string]interface{}
	if err := json.Unmarshal(data, &m); err != nil {
		return nil
	}
	return m
}

// extractDirectRulesFromXrayConfig looks for routing rules whose outboundTag is "direct"
// (excluding catch-all rules) and returns report entries.
func extractDirectRulesFromXrayConfig(config map[string]interface{}, source, sourceLabel string, priority int, reason string) []map[string]interface{} {
	if config == nil {
		return nil
	}

	routing, _ := config["routing"].(map[string]interface{})
	if routing == nil {
		return nil
	}

	rulesRaw, _ := routing["rules"].([]interface{})
	if rulesRaw == nil {
		return nil
	}

	var entries []map[string]interface{}
	earlierNonDirect := make([]struct{ kind, value string }, 0)

	for index, ruleRaw := range rulesRaw {
		rule, ok := ruleRaw.(map[string]interface{})
		if !ok {
			continue
		}
		outboundTag := strings.TrimSpace(coerceString(rule["outboundTag"]))

		if outboundTag != "direct" {
			if outboundTag != "" && !isTunCatchallRule(rule) {
				for _, kv := range []struct{ kind, field string }{
					{"domain", "domain"}, {"ip", "ip"}, {"process", "process"},
				} {
					for _, val := range ruleValues(rule, kv.field) {
						earlierNonDirect = append(earlierNonDirect, struct{ kind, value string }{kv.kind, val})
					}
				}
			}
			continue
		}
		if isTunCatchallRule(rule) {
			continue
		}

		for _, kv := range []struct{ kind, field string }{
			{"domain", "domain"}, {"ip", "ip"}, {"process", "process"},
		} {
			for _, val := range ruleValues(rule, kv.field) {
				// Skip if an earlier non-direct rule covers this value.
				covered := false
				for _, earlier := range earlierNonDirect {
					if earlier.kind == kv.kind && valuesOverlap(earlier.value, val, kv.kind) {
						covered = true
						break
					}
				}
				if covered {
					continue
				}
				entries = append(entries, makeDirectReportEntry(
					source, sourceLabel, kv.kind, val, priority, reason, &index,
				))
			}
		}
	}
	return entries
}

// extractDirectRulesFromRoutingProfile returns report entries from a routing profile's direct_sites and direct_ip.
func extractDirectRulesFromRoutingProfile(profile *domain.RoutingProfile) []map[string]interface{} {
	if profile == nil {
		return nil
	}
	profileName := strings.TrimSpace(profile.Name)
	if profileName == "" {
		profileName = "active profile"
	}

	var entries []map[string]interface{}

	for _, val := range profile.DirectSites {
		if trimmed := strings.TrimSpace(val); trimmed != "" {
			entries = append(entries, makeDirectReportEntry(
				"profile", "Active profile", "domain", trimmed, 20,
				fmt.Sprintf("Came from routing profile «%s».", profileName),
				nil,
			))
		}
	}
	for _, val := range profile.DirectIP {
		if trimmed := strings.TrimSpace(val); trimmed != "" {
			entries = append(entries, makeDirectReportEntry(
				"profile", "Active profile", "ip", trimmed, 20,
				fmt.Sprintf("Came from routing profile «%s».", profileName),
				nil,
			))
		}
	}
	return entries
}

// ruleValues extracts string values from a rule field (supports both single string and array).
func ruleValues(rule map[string]interface{}, fieldName string) []string {
	value := rule[fieldName]
	if arr, ok := value.([]interface{}); ok {
		result := make([]string, 0, len(arr))
		for _, item := range arr {
			if s, ok := item.(string); ok {
				if trimmed := strings.TrimSpace(s); trimmed != "" {
					result = append(result, trimmed)
				}
			}
		}
		return result
	}
	if s, ok := value.(string); ok {
		if trimmed := strings.TrimSpace(s); trimmed != "" {
			return []string{trimmed}
		}
	}
	return nil
}

// isTunCatchallRule checks if a rule is the TUN catch-all (network="tcp,udp", inboundTag includes "tun-in").
func isTunCatchallRule(rule map[string]interface{}) bool {
	inboundTag, ok := rule["inboundTag"].([]interface{})
	if !ok {
		return false
	}
	hasTunIn := false
	for _, tag := range inboundTag {
		if s, ok := tag.(string); ok && s == "tun-in" {
			hasTunIn = true
			break
		}
	}
	if !hasTunIn {
		return false
	}
	network := strings.ToLower(strings.TrimSpace(coerceString(rule["network"])))
	return network == "tcp,udp"
}

// makeDirectReportEntry creates a standardized report entry for a direct route.
func makeDirectReportEntry(source, sourceLabel, kind, value string, priority int, reason string, ruleIndex *int) map[string]interface{} {
	id := fmt.Sprintf("%s:%s:%s", source, kind, value)
	kindLabel := map[string]string{
		"domain":  "Domain",
		"ip":      "IP",
		"process": "Process",
		"rule":    "Rule",
	}[kind]
	if kindLabel == "" {
		kindLabel = "Rule"
	}

	entry := map[string]interface{}{
		"id":           id,
		"source":       source,
		"source_label": sourceLabel,
		"kind":         kind,
		"kind_label":   kindLabel,
		"value":        value,
		"action":       "direct",
		"action_label": "Direct",
		"priority":     priority,
		"reason":       reason,
		"rule_index":   ruleIndex,
		"active":       true,
		"conflicts":    []map[string]interface{}{},
		"covered_by":   []map[string]interface{}{},
		"wins_over":    []map[string]interface{}{},
	}
	return entry
}

// annotateDirectReportConflicts annotates entries with conflicts, covered_by, and wins_over between template and profile entries.
func annotateDirectReportConflicts(templateEntries, profileEntries, runtimeEntries []map[string]interface{}, activeProfile *domain.RoutingProfile) []map[string]interface{} {
	// Deep-copy all entries.
	entries := make([]map[string]interface{}, 0, len(templateEntries)+len(profileEntries)+len(runtimeEntries))
	for _, e := range templateEntries {
		entries = append(entries, deepCopyMap(e))
	}
	for _, e := range profileEntries {
		entries = append(entries, deepCopyMap(e))
	}
	for _, e := range runtimeEntries {
		entries = append(entries, deepCopyMap(e))
	}

	// Collect profile policy entries.
	policyEntries := profilePolicyEntries(activeProfile)

	// Annotate template entries against profile policies.
	for _, entry := range entries {
		if coerceString(entry["source"]) != "template" {
			continue
		}
		entryKind := coerceString(entry["kind"])
		entryValue := coerceString(entry["value"])
		for _, pe := range policyEntries {
			if entryKind != pe["kind"] {
				continue
			}
			if !valuesOverlap(entryValue, pe["value"], pe["kind"]) {
				continue
			}
			if pe["policy"] == "direct" {
				wins := entry["wins_over"].([]map[string]interface{})
				wins = append(wins, map[string]interface{}{
					"source":  "profile",
					"policy":  "direct",
					"value":   pe["value"],
					"message": "Profile also routes this value directly; the template rule retains higher priority.",
				})
				entry["wins_over"] = wins
				continue
			}
			conflicts := entry["conflicts"].([]map[string]interface{})
			policyLabel := map[string]string{"direct": "direct", "proxy": "via VPN", "block": "block"}[pe["policy"]]
			if policyLabel == "" {
				policyLabel = pe["policy"]
			}
			conflicts = append(conflicts, map[string]interface{}{
				"source":       "profile",
				"policy":       pe["policy"],
				"policy_label": policyLabel,
				"value":        pe["value"],
				"message": fmt.Sprintf(
					"The template rule sends this value directly before the profile can apply the «%s» action.",
					policyLabel,
				),
			})
			entry["conflicts"] = conflicts
		}
	}

	// Annotate profile entries covered by template entries.
	for _, entry := range entries {
		if coerceString(entry["source"]) != "profile" {
			continue
		}
		entryKind := coerceString(entry["kind"])
		entryValue := coerceString(entry["value"])
		for _, tmpl := range templateEntries {
			if coerceString(tmpl["kind"]) != entryKind {
				continue
			}
			if !valuesOverlap(entryValue, coerceString(tmpl["value"]), entryKind) {
				continue
			}
			covered := entry["covered_by"].([]map[string]interface{})
			covered = append(covered, map[string]interface{}{
				"source":  "template",
				"value":   coerceString(tmpl["value"]),
				"message": "Value is already covered by a higher-priority template rule.",
			})
			entry["covered_by"] = covered
		}
	}

	return entries
}

// profilePolicyEntries extracts (policy, kind, value) triples from a routing profile.
func profilePolicyEntries(profile *domain.RoutingProfile) []map[string]string {
	if profile == nil {
		return nil
	}
	var result []map[string]string

	for _, policy := range []string{"direct", "proxy", "block"} {
		var kinds map[string][]string
		switch policy {
		case "direct":
			kinds = map[string][]string{"domain": profile.DirectSites, "ip": profile.DirectIP}
		case "proxy":
			kinds = map[string][]string{"domain": profile.ProxySites, "ip": profile.ProxyIP}
		case "block":
			kinds = map[string][]string{"domain": profile.BlockSites, "ip": profile.BlockIP}
		}
		for kind, values := range kinds {
			for _, val := range values {
				trimmed := strings.TrimSpace(val)
				if trimmed != "" {
					result = append(result, map[string]string{
						"policy": policy,
						"kind":   kind,
						"value":  trimmed,
					})
				}
			}
		}
	}
	return result
}

// valuesOverlap checks if two values overlap. For domains, case-insensitive equality.
// For IPs, also checks CIDR overlap.
func valuesOverlap(left, right, kind string) bool {
	if strings.EqualFold(left, right) {
		return true
	}
	if kind != "ip" {
		return false
	}
	ln := parseIPNetwork(left)
	rn := parseIPNetwork(right)
	return ipNetworksOverlap(ln, rn)
}

// parseIPNetwork parses an IP network string (CIDR notation).
// Returns nil for invalid or geoip: prefixed values.
func parseIPNetwork(value string) *net.IPNet {
	trimmed := strings.TrimSpace(value)
	if trimmed == "" || strings.HasPrefix(strings.ToLower(trimmed), "geoip:") {
		return nil
	}
	_, nw, err := net.ParseCIDR(trimmed)
	if err != nil {
		return nil
	}
	return nw
}

// ipNetworksOverlap returns true if two IP networks overlap.
func ipNetworksOverlap(a, b *net.IPNet) bool {
	if a == nil || b == nil {
		return false
	}
	return a.Contains(b.IP) || b.Contains(a.IP)
}

// catchallAction returns the outboundTag of the catchall rule from a config, or empty string.
func catchallAction(config map[string]interface{}) string {
	if config == nil {
		return ""
	}
	routing, _ := config["routing"].(map[string]interface{})
	if routing == nil {
		return ""
	}
	rulesRaw, _ := routing["rules"].([]interface{})
	for i := len(rulesRaw) - 1; i >= 0; i-- {
		rule, ok := rulesRaw[i].(map[string]interface{})
		if !ok {
			continue
		}
		if isTunCatchallRule(rule) {
			return strings.TrimSpace(coerceString(rule["outboundTag"]))
		}
	}
	return ""
}

// deepCopyMap performs a shallow copy of a map (sufficient for our structures).
func deepCopyMap(m map[string]interface{}) map[string]interface{} {
	cpy := make(map[string]interface{}, len(m))
	for k, v := range m {
		cpy[k] = v
	}
	return cpy
}

// randHex generates a random hex string of the given length (in hex digits).
func randHex(length int) string {
	b := make([]byte, (length+1)/2)
	if _, err := rand.Read(b); err != nil {
		// Fallback deterministic; should not happen in practice.
		return "00000000"[:length]
	}
	return hex.EncodeToString(b)[:length]
}
