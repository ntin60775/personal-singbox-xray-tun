package parser

import (
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"net/url"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"unicode"
)

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

var SUPPORTED_SCHEMES = map[string]bool{
	"vless":  true,
	"vmess":  true,
	"trojan": true,
	"ss":     true,
}

var supportedLinkNetworks = map[string]bool{
	"tcp":   true,
	"ws":    true,
	"grpc":  true,
	"xhttp": true,
}

var supportedLinkSecurities = map[string]bool{
	"none":    true,
	"tls":     true,
	"reality": true,
}

var supportedVMessNetworks = map[string]bool{
	"tcp":  true,
	"ws":   true,
	"grpc": true,
}

var supportedVMessSecurities = map[string]bool{
	"none": true,
	"tls":  true,
}

var SUPPORTED_SS_METHODS = map[string]bool{
	"aes-128-gcm":                  true,
	"aes-256-gcm":                  true,
	"chacha20-ietf-poly1305":       true,
	"2022-blake3-aes-128-gcm":      true,
	"2022-blake3-aes-256-gcm":      true,
	"2022-blake3-chacha20-poly1305": true,
}

const ZERO_UUID = "00000000-0000-0000-0000-000000000000"

var PLACEHOLDER_MARKERS = []string{
	"0.0.0.0",
	"example.com",
	"test.com",
	"localhost",
	"127.0.0.1",
}

// From Python: text markers that indicate a provider placeholder stub.
var placeholderTextMarkers = []string{
	"не поддерж",
	"поддерживаетя",
	"обратись к",
	"@provider_support",
	"not support",
}

const happRoutingPrefix = "happ://routing/"

var providerIDCommentRE = regexp.MustCompile(`(?i)^#\s*providerid\b[:=\s]*(.+)$`)

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

// ParsedNode holds the result of parsing a single proxy URI.
type ParsedNode struct {
	Protocol      string   `json:"protocol"`
	Address       string   `json:"address"`
	Port          int      `json:"port"`
	UUID          string   `json:"uuid,omitempty"`
	Password      string   `json:"password,omitempty"`
	Method        string   `json:"method,omitempty"`
	Flow          string   `json:"flow,omitempty"`
	Encryption    string   `json:"encryption,omitempty"`
	Network       string   `json:"network,omitempty"`
	Security      string   `json:"security,omitempty"`
	Host          string   `json:"host,omitempty"`
	Path          string   `json:"path,omitempty"`
	ServerName    string   `json:"server_name,omitempty"`
	ServiceName   string   `json:"service_name,omitempty"`
	GRPCAuthority string   `json:"grpc_authority,omitempty"`
	Fingerprint   string   `json:"fingerprint,omitempty"`
	PublicKey     string   `json:"public_key,omitempty"`
	ShortID       string   `json:"short_id,omitempty"`
	SpiderX       string   `json:"spider_x,omitempty"`
	Mode          string   `json:"mode,omitempty"`
	ALPN          []string `json:"alpn,omitempty"`
	AllowInsecure bool     `json:"allow_insecure,omitempty"`
	DisplayName   string   `json:"display_name,omitempty"`
	RawURI        string   `json:"raw_uri,omitempty"`
}

// ParseError signals a parsing failure with a human-readable message.
type ParseError struct {
	Message string
}

func (e *ParseError) Error() string {
	return e.Message
}

func newParseError(msg string) error {
	return &ParseError{Message: msg}
}

func newParseErrorf(format string, args ...interface{}) error {
	return &ParseError{Message: fmt.Sprintf(format, args...)}
}

// ---------------------------------------------------------------------------
// Fingerprint
// ---------------------------------------------------------------------------

// FingerprintPayload computes a SHA-256 hex fingerprint from the canonical
// JSON representation of the normalized map, excluding display metadata.
func FingerprintPayload(normalized map[string]interface{}) string {
	payload := make(map[string]interface{}, len(normalized))
	excluded := map[string]bool{
		"display_name": true,
		"raw_uri":      true,
		"origin_uri":   true,
	}
	for k, v := range normalized {
		if excluded[k] {
			continue
		}
		payload[k] = v
	}
	canonical, err := json.Marshal(payload)
	if err != nil {
		return strings.Repeat("0", 64)
	}
	sum := sha256.Sum256(canonical)
	return hex.EncodeToString(sum[:])
}



// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

// singleValueQuery parses a raw query string and returns the last value for each key.
func singleValueQuery(rawQuery string) map[string]string {
	values, _ := url.ParseQuery(rawQuery)
	result := make(map[string]string, len(values))
	for k, vs := range values {
		if len(vs) > 0 {
			result[k] = vs[len(vs)-1]
		}
	}
	return result
}

// splitCSV splits a comma-separated string, trimming whitespace and dropping blanks.
func splitCSV(value string) []string {
	value = strings.TrimSpace(value)
	if value == "" {
		return nil
	}
	parts := strings.Split(value, ",")
	result := make([]string, 0, len(parts))
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p != "" {
			result = append(result, p)
		}
	}
	return result
}

// boolValue interprets query-style booleans.
func boolValue(value string) bool {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case "1", "true", "yes", "on":
		return true
	}
	return false
}

// defaultName returns a display name: the fragment if non-empty, otherwise "PROTO ADDR:PORT".
func defaultName(fragment, protocol, address string, port int) string {
	fragment = strings.TrimSpace(fragment)
	if fragment != "" {
		return fragment
	}
	return fmt.Sprintf("%s %s:%d", strings.ToUpper(protocol), address, port)
}

// decodeBase64 decodes a URL-safe base64 string, with whitespace cleaning and
// automatic padding correction.
func decodeBase64(value string) ([]byte, error) {
	cleaned := strings.Map(func(r rune) rune {
		if unicode.IsSpace(r) {
			return -1
		}
		return r
	}, value)
	padding := (4 - len(cleaned)%4) % 4
	cleaned += strings.Repeat("=", padding)
	decoded, err := base64.URLEncoding.DecodeString(cleaned)
	if err != nil {
		return nil, newParseErrorf("Не удалось декодировать base64-фрагмент.")
	}
	return decoded, nil
}

// decodeBase64Text decodes URL-safe base64 into a UTF-8 string.
func decodeBase64Text(value string) (string, error) {
	raw, err := decodeBase64(value)
	if err != nil {
		return "", err
	}
	return string(raw), nil
}

// ---------------------------------------------------------------------------
// Placeholder detection
// ---------------------------------------------------------------------------

// isPlaceholderAddress returns true if the address looks like a stub endpoint.
func isPlaceholderAddress(address string) bool {
	lower := strings.ToLower(strings.TrimSpace(address))
	return lower == "0.0.0.0" || lower == "::" || lower == "[::]"
}

// isPlaceholderPort returns true if the port indicates a stub (0 or 1).
func isPlaceholderPort(port int) bool {
	return port == 0 || port == 1
}

// hasPlaceholderText checks combined text against known placeholder markers.
func hasPlaceholderText(displayName, rawURI string) bool {
	combined := (displayName + " " + rawURI)
	lower := strings.ToLower(combined)
	for _, marker := range placeholderTextMarkers {
		if strings.Contains(lower, marker) {
			return true
		}
	}
	for _, marker := range PLACEHOLDER_MARKERS {
		if strings.Contains(lower, marker) {
			return true
		}
	}
	return false
}

// checkPlaceholder raises ParseError if the node appears to be a provider stub.
func checkPlaceholder(n *ParsedNode) error {
	looksLikeStubEndpoint := isPlaceholderAddress(n.Address) && isPlaceholderPort(n.Port)
	hasStubText := hasPlaceholderText(n.DisplayName, n.RawURI)
	hasStubIdentity := strings.ToLower(strings.TrimSpace(n.UUID)) == ZERO_UUID

	if looksLikeStubEndpoint && (hasStubText || hasStubIdentity) {
		dn := strings.TrimSpace(n.DisplayName)
		if dn != "" {
			suffix := ""
			if !strings.HasSuffix(dn, ".") && !strings.HasSuffix(dn, "!") && !strings.HasSuffix(dn, "?") {
				suffix = "."
			}
			return newParseErrorf("Провайдер вернул заглушку: %s%s", dn, suffix)
		}
		return newParseError(
			"Провайдер вернул заглушку вместо рабочего узла. " +
				"Вероятно, эту подписку нужно запрашивать через xray-совместимый клиент.",
		)
	}
	return nil
}

// ---------------------------------------------------------------------------
// Stream settings parsing (shared by VLESS, Trojan)
// ---------------------------------------------------------------------------

type streamSettings struct {
	Network       string
	Security      string
	Host          string
	Path          string
	ServerName    string
	ServiceName   string
	GRPCAuthority string
	Fingerprint   string
	PublicKey     string
	ShortID       string
	SpiderX       string
	Mode          string
	XHTTPExtra    map[string]interface{}
	ALPN          []string
	AllowInsecure bool
}

// parseStreamCommon extracts stream/transport settings from url query params.
func parseStreamCommon(query map[string]string, protocol string) (*streamSettings, error) {
	network := strings.ToLower(strings.TrimSpace(query["type"]))
	if network == "" {
		network = "tcp"
	}
	if !supportedLinkNetworks[network] {
		return nil, newParseErrorf("Неподдерживаемый transport '%s' для %s.", network, protocol)
	}

	security := strings.ToLower(strings.TrimSpace(query["security"]))
	if security == "" {
		security = "none"
	}
	if !supportedLinkSecurities[security] {
		return nil, newParseErrorf("Неподдерживаемая security '%s' для %s.", security, protocol)
	}

	host := strings.TrimSpace(query["host"])
	path := strings.TrimSpace(query["path"])
	serverName := strings.TrimSpace(query["sni"])
	if serverName == "" {
		serverName = strings.TrimSpace(query["serverName"])
	}
	serviceName := strings.TrimSpace(query["serviceName"])
	if serviceName == "" {
		serviceName = strings.TrimSpace(query["service_name"])
	}
	grpcAuthority := strings.TrimSpace(query["authority"])
	fingerprint := strings.TrimSpace(query["fp"])
	if fingerprint == "" {
		fingerprint = strings.TrimSpace(query["fingerprint"])
	}
	publicKey := strings.TrimSpace(query["pbk"])
	if publicKey == "" {
		publicKey = strings.TrimSpace(query["publicKey"])
	}
	shortID := strings.TrimSpace(query["sid"])
	if shortID == "" {
		shortID = strings.TrimSpace(query["shortId"])
	}
	spiderX := strings.TrimSpace(query["spx"])
	if spiderX == "" {
		spiderX = strings.TrimSpace(query["spiderX"])
	}
	if spiderX == "" {
		spiderX = "/"
	}
	mode := strings.TrimSpace(query["mode"])
	if mode == "" {
		mode = "auto"
	}
	alpn := splitCSV(query["alpn"])
	allowInsecure := boolValue(query["allowInsecure"])
	if !allowInsecure {
		allowInsecure = boolValue(query["insecure"])
	}

	var xhttpExtra map[string]interface{}
	extraValue := strings.TrimSpace(query["extra"])
	if extraValue != "" {
		if err := json.Unmarshal([]byte(extraValue), &xhttpExtra); err != nil {
			return nil, newParseError("Параметр extra должен быть JSON-объектом.")
		}
	}

	// Defaults for path based on network
	if (network == "ws" || network == "xhttp") && path == "" {
		path = "/"
	}
	if network == "grpc" && serviceName == "" && path != "" {
		serviceName = strings.TrimPrefix(path, "/")
	}
	if network == "grpc" && serviceName == "" {
		return nil, newParseError("Для gRPC-ссылки обязателен serviceName.")
	}

	// Security validations
	if security == "tls" && serverName == "" {
		return nil, newParseError("Для TLS-ссылки обязателен sni/serverName.")
	}
	if security == "reality" {
		if serverName == "" {
			return nil, newParseError("Для REALITY-ссылки обязателен sni/serverName.")
		}
		if publicKey == "" {
			return nil, newParseError("Для REALITY-ссылки обязателен publicKey/pbk.")
		}
		if shortID == "" {
			return nil, newParseError("Для REALITY-ссылки обязателен shortId/sid.")
		}
		if fingerprint == "" {
			return nil, newParseError("Для REALITY-ссылки обязателен fingerprint/fp.")
		}
	}

	return &streamSettings{
		Network:       network,
		Security:      security,
		Host:          host,
		Path:          path,
		ServerName:    serverName,
		ServiceName:   serviceName,
		GRPCAuthority: grpcAuthority,
		Fingerprint:   fingerprint,
		PublicKey:     publicKey,
		ShortID:       shortID,
		SpiderX:       spiderX,
		Mode:          mode,
		XHTTPExtra:    xhttpExtra,
		ALPN:          alpn,
		AllowInsecure: allowInsecure,
	}, nil
}

// applyStreamSettings sets stream-related fields on a ParsedNode from streamSettings.
func applyStreamSettings(n *ParsedNode, s *streamSettings) {
	n.Network = s.Network
	n.Security = s.Security
	n.Host = s.Host
	n.Path = s.Path
	n.ServerName = s.ServerName
	n.ServiceName = s.ServiceName
	n.GRPCAuthority = s.GRPCAuthority
	n.Fingerprint = s.Fingerprint
	n.PublicKey = s.PublicKey
	n.ShortID = s.ShortID
	n.SpiderX = s.SpiderX
	n.Mode = s.Mode
	n.ALPN = s.ALPN
	n.AllowInsecure = s.AllowInsecure
}

// ensureSupportedQueryKeys checks that non-empty query keys are in the allowed set.
func ensureSupportedQueryKeys(query map[string]string, allowedKeys map[string]bool) error {
	var unexpected []string
	for key, value := range query {
		if value != "" && !allowedKeys[key] {
			unexpected = append(unexpected, key)
		}
	}
	if len(unexpected) > 0 {
		sort.Strings(unexpected)
		return newParseErrorf("Неподдерживаемые параметры ссылки: %s.", strings.Join(unexpected, ", "))
	}
	return nil
}

// ---------------------------------------------------------------------------
// Dispatcher
// ---------------------------------------------------------------------------

// ParseProxyURI detects the scheme and delegates to the specific parser.
func ParseProxyURI(rawURI string) (*ParsedNode, error) {
	value := strings.TrimSpace(rawURI)
	if value == "" {
		return nil, newParseError("Пустая строка не является ссылкой конфигурации.")
	}

	u, err := url.Parse(value)
	if err != nil || u.Scheme == "" {
		return nil, newParseError("Строка не является корректным URI.")
	}

	scheme := strings.ToLower(u.Scheme)
	if !SUPPORTED_SCHEMES[scheme] {
		return nil, newParseErrorf("Неподдерживаемая схема '%s'.", scheme)
	}

	var node *ParsedNode
	switch scheme {
	case "vless":
		node, err = ParseVLESS(value)
	case "vmess":
		node, err = ParseVMess(value)
	case "trojan":
		node, err = ParseTrojan(value)
	case "ss":
		node, err = ParseShadowsocks(value)
	}

	if err != nil {
		return nil, err
	}

	// Check for provider placeholder stubs
	if err := checkPlaceholder(node); err != nil {
		return nil, err
	}

	return node, nil
}

// ---------------------------------------------------------------------------
// PreviewLinks
// ---------------------------------------------------------------------------

// PreviewLinks parses each non-empty line of text and returns only successful results.
func PreviewLinks(rawText string) []ParsedNode {
	var results []ParsedNode
	for _, rawLine := range strings.Split(rawText, "\n") {
		line := strings.TrimSpace(rawLine)
		if line == "" {
			continue
		}
		node, err := ParseProxyURI(line)
		if err != nil {
			continue
		}
		results = append(results, *node)
	}
	return results
}

// ---------------------------------------------------------------------------
// Subscription payload parsing
// ---------------------------------------------------------------------------

// payloadTextVariants returns (lines, format) pairs from raw payload bytes.
// Tries plain text first, then base64-decoded text.
func payloadTextVariants(payload []byte) [][2]interface{} {
	text := strings.TrimSpace(string(payload))
	if text == "" {
		return nil
	}

	var variants [][2]interface{}

	// Plain text variant
	plainLines := splitNonEmpty(text)
	if len(plainLines) > 0 {
		variants = append(variants, [2]interface{}{plainLines, "plain_text"})
	}

	// Base64 variant
	decodedText, err := decodeBase64Text(text)
	if err == nil {
		decodedText = strings.TrimSpace(decodedText)
		if decodedText != "" {
			b64Lines := splitNonEmpty(decodedText)
			if len(b64Lines) > 0 {
				variants = append(variants, [2]interface{}{b64Lines, "base64"})
			}
		}
	}

	return variants
}

func splitNonEmpty(s string) []string {
	raw := strings.Split(s, "\n")
	var result []string
	for _, line := range raw {
		line = strings.TrimSpace(line)
		if line != "" {
			result = append(result, line)
		}
	}
	return result
}

// splitSubscriptionLines categorizes lines into proxy, routing, provider-ids, comments, unknown.
type subscriptionParts struct {
	proxyLines  []string
	routingLines []string
	providerIDs []string
	commentLines []string
	unknownLines []string
}

func splitSubscriptionLines(lines []string) subscriptionParts {
	var parts subscriptionParts
	for _, line := range lines {
		stripped := strings.TrimSpace(line)
		if stripped == "" {
			continue
		}
		u, err := url.Parse(stripped)
		if err == nil && SUPPORTED_SCHEMES[strings.ToLower(u.Scheme)] {
			parts.proxyLines = append(parts.proxyLines, stripped)
			continue
		}
		if isRoutingMetadataLine(stripped) {
			parts.routingLines = append(parts.routingLines, stripped)
			continue
		}
		providerID := parseProviderIDComment(stripped)
		if providerID != "" {
			parts.providerIDs = append(parts.providerIDs, providerID)
			continue
		}
		if strings.HasPrefix(stripped, "#") {
			parts.commentLines = append(parts.commentLines, stripped)
			continue
		}
		parts.unknownLines = append(parts.unknownLines, stripped)
	}
	return parts
}

func isRoutingMetadataLine(line string) bool {
	return strings.HasPrefix(strings.TrimSpace(line), happRoutingPrefix)
}

func parseProviderIDComment(line string) string {
	match := providerIDCommentRE.FindStringSubmatch(strings.TrimSpace(line))
	if len(match) >= 2 {
		return strings.TrimSpace(match[1])
	}
	return ""
}

// ParseSubscriptionPayload decodes a subscription payload (plain text or base64)
// and returns the list of recognized proxy URIs along with the payload format.
func ParseSubscriptionPayload(payload []byte) ([]string, string, error) {
	variants := payloadTextVariants(payload)
	if len(variants) == 0 {
		return nil, "", newParseError("Подписка вернула пустой ответ.")
	}

	for _, variant := range variants {
		lines := variant[0].([]string)
		payloadFormat := variant[1].(string)
		parts := splitSubscriptionLines(lines)
		recognizedCount := len(parts.proxyLines) + len(parts.routingLines) +
			len(parts.providerIDs) + len(parts.commentLines)
		if len(parts.proxyLines) > 0 && recognizedCount == len(lines) {
			return parts.proxyLines, payloadFormat, nil
		}
	}

	return nil, "", newParseError(
		"Формат подписки не распознан: ожидался plain-text или base64-список ссылок.",
	)
}

// ---------------------------------------------------------------------------
// Subscription metadata extraction
// ---------------------------------------------------------------------------

func headerValue(headers map[string]string, name string) string {
	if headers == nil {
		return ""
	}
	// Lowercase match
	lowerName := strings.ToLower(name)
	for k, v := range headers {
		if strings.ToLower(k) == lowerName {
			return strings.TrimSpace(v)
		}
	}
	return ""
}

func providerIDFromURL(sourceURL string) (string, string) {
	if sourceURL == "" {
		return "", ""
	}
	u, err := url.Parse(sourceURL)
	if err != nil {
		return "", ""
	}
	fragment := u.Fragment
	if fragment == "" {
		return "", ""
	}
	query := singleValueQuery(fragment)
	pid := strings.TrimSpace(query["providerid"])
	if pid != "" {
		return pid, "url_fragment"
	}
	return "", ""
}

// ExtractSubscriptionMetadata extracts metadata from a subscription response.
// It reads provider ID and routing text from response headers, the payload body,
// and the source URL, with headers taking highest priority.
func ExtractSubscriptionMetadata(payload []byte, headers map[string]string, sourceURL string) map[string]string {
	providerID := headerValue(headers, "providerid")
	providerIDSource := ""
	if providerID != "" {
		providerIDSource = "response_header"
	}

	routingText := headerValue(headers, "routing")
	routingSource := ""
	if routingText != "" {
		routingSource = "response_header"
	}

	payloadFormat := ""

	variants := payloadTextVariants(payload)
	for _, variant := range variants {
		lines := variant[0].([]string)
		candidateFormat := variant[1].(string)
		parts := splitSubscriptionLines(lines)
		recognizedCount := len(parts.proxyLines) + len(parts.routingLines) +
			len(parts.providerIDs) + len(parts.commentLines)
		if len(parts.proxyLines) == 0 || recognizedCount != len(lines) {
			continue
		}
		payloadFormat = candidateFormat
		if providerID == "" && len(parts.providerIDs) > 0 {
			providerID = parts.providerIDs[0]
			providerIDSource = "body_" + candidateFormat
		}
		if routingText == "" && len(parts.routingLines) > 0 {
			routingText = parts.routingLines[0]
			routingSource = "body_" + candidateFormat
		}
		break
	}

	if providerID == "" {
		providerID, providerIDSource = providerIDFromURL(sourceURL)
	}

	return map[string]string{
		"provider_id":        providerID,
		"provider_id_source": providerIDSource,
		"routing_text":       routingText,
		"routing_source":     routingSource,
		"payload_format":     payloadFormat,
	}
}

// ---------------------------------------------------------------------------
// Validation helpers
// ---------------------------------------------------------------------------

// isValidPort checks that a port string is a valid integer in range 1-65535.
func isValidPort(raw string) (int, bool) {
	port, err := strconv.Atoi(strings.TrimSpace(raw))
	if err != nil || port < 1 || port > math.MaxUint16 {
		return 0, false
	}
	return port, true
}
