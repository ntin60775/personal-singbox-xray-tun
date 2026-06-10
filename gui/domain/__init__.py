"""Доменный слой Subvost Xray TUN.

Содержит сущности, value objects, агрегаты и фабрики
для преобразования между доменными типами и dict-представлением store.
"""
from .entities import Node, Profile, RoutingProfile, Subscription, RoutingRule
from .factories import (
    node_from_store_dict,
    node_to_store_dict,
    profile_from_store_dict,
    profile_to_store_dict,
    subscription_from_store_dict,
    subscription_to_store_dict,
    routing_profile_from_store_dict,
)
from .value_objects import NodeAddress, ProtocolConfig, TransportHint

__all__ = [
    # Entities
    "Node",
    "Profile",
    "RoutingProfile",
    "RoutingRule",
    "Subscription",
    # Value objects
    "NodeAddress",
    "ProtocolConfig",
    "TransportHint",
    # Factories
    "node_from_store_dict",
    "node_to_store_dict",
    "profile_from_store_dict",
    "profile_to_store_dict",
    "subscription_from_store_dict",
    "subscription_to_store_dict",
    "routing_profile_from_store_dict",
]
