from __future__ import annotations

from .profile_manager import (
    DEFAULT_GEOIP_URL,
    DEFAULT_GEOSITE_URL,
    SUPPORTED_DOMAIN_STRATEGIES,
    ROUTING_URI_PREFIXES,
    ROUTING_URI_ACTIVATION_MODE,
    STORED_ONLY_FIELDS,
    KNOWN_IMPORT_KEYS,
    RoutingProfileError,
    annotate_direct_report_conflicts,
    build_direct_routes_report,
    build_geodata_status,
    download_routing_geodata,
    extract_direct_rules_from_routing_profile,
    extract_direct_rules_from_xray_config,
    get_existing_geodata_status,
    parse_routing_profile_input,
    routing_profile_rule_count,
)

from .config_rewriter import (
    apply_routing_profile_to_config,
)
