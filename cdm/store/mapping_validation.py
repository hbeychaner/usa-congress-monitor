"""Audit transformed documents against their declared OpenSearch mappings."""

from __future__ import annotations

from cdm.store.index_manager import load_definitions
from cdm.store.opensearch import resource_target

_INTERNAL_FIELDS = {"_resource", "_raw"}


def _properties(resource: str) -> tuple[str, dict]:
    target, _ = resource_target(resource)
    definition = load_definitions().get(target)
    if definition is None:
        raise ValueError(f"No OpenSearch mapping defined for {target}")
    return target, definition.get("mappings", {}).get("properties", {})


def audit_document(document: dict, resource: str) -> dict:
    """Return mapping drift information without rejecting sparse extra fields."""
    target, properties = _properties(resource)
    unmapped_fields = sorted(
        key for key in document if key not in properties and key not in _INTERNAL_FIELDS
    )
    _, discriminators = resource_target(resource)
    discriminator_errors = {
        key: {"expected": expected, "actual": document.get(key)}
        for key, expected in discriminators.items()
        if document.get(key) != expected
    }
    return {
        "resource": resource,
        "target": target,
        "unmapped_fields": unmapped_fields,
        "discriminator_errors": discriminator_errors,
        "valid": bool(document.get("id")) and not discriminator_errors,
    }


def validate_document(document: dict, resource: str) -> dict:
    """Validate identity and target discriminators, returning the audit result."""
    audit = audit_document(document, resource)
    if not audit["valid"]:
        raise ValueError(
            f"Invalid {resource} document for {audit['target']}: "
            f"missing id or discriminator errors={audit['discriminator_errors']}"
        )
    return audit
