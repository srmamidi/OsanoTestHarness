# AI-GENERATED: create
# AI Technology: Claude Code (Opus 5.5, claude-opus-5-5)
# Reviewer: Sarada Mamidi, DevOps Manager - review required before merge
"""The consent choices a visitor can make, and what each one should allow."""
from __future__ import annotations

from dataclasses import dataclass, field

from . import CATEGORIES


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    # none | accept_all | deny_all | custom
    action: str
    # For custom: the categories switched ON (everything else OFF).
    granted: tuple[str, ...] = ()
    gpc: bool = False
    description: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)


SCENARIOS: dict[str, Scenario] = {s.id: s for s in (
    Scenario("no_choice", "First visit, no choice made", "none",
             description="Fresh visitor who ignores the banner. Shows what fires on arrival."),
    Scenario("accept_all", "Accept all", "accept_all",
             description="Visitor clicks Accept. Everything classified should run; checks for over-blocking."),
    Scenario("reject_all", "Reject all", "deny_all",
             description="Visitor clicks Deny/Reject. Only Essential may run."),
    Scenario("analytics_only", "Analytics only", "custom", granted=("ANALYTICS",),
             description="Visitor opens preferences and keeps only Analytics."),
    Scenario("marketing_only", "Marketing only", "custom", granted=("MARKETING",),
             description="Visitor opens preferences and keeps only Marketing."),
    Scenario("personalization_only", "Personalization only", "custom", granted=("PERSONALIZATION",),
             description="Visitor opens preferences and keeps only Personalization."),
    Scenario("gpc_signal", "Global Privacy Control on", "none", gpc=True,
             description="Browser sends the GPC 'do not sell or share' signal; no click."),
)}

DEFAULT_SCENARIOS = tuple(SCENARIOS)


def allowed_categories(scenario: Scenario, consent_model: str) -> frozenset[str]:
    """Categories that may run after this scenario's choice. consent_model: opt-in | opt-out."""
    everything = frozenset(CATEGORIES)
    if scenario.action == "accept_all":
        return everything
    if scenario.action == "deny_all":
        return frozenset({"ESSENTIAL"})
    if scenario.action == "custom":
        return frozenset({"ESSENTIAL", *scenario.granted})
    # No click: what the visitor gets by default.
    default = frozenset({"ESSENTIAL"}) if consent_model == "opt-in" else everything
    if scenario.gpc:
        # GPC is an opt-out of sale/share: marketing and opt-out categories must stop.
        default = default - {"MARKETING", "OPT-OUT"}
    return default


def default_allowed(consent_model: str) -> frozenset[str]:
    """What may run before the visitor has chosen anything."""
    return allowed_categories(SCENARIOS["no_choice"], consent_model)


# OPT-OUT is left out on purpose: its ACCEPT/DENY meaning is inverted in some Osano setups,
# so verifying it would raise false alarms. GPC is checked through MARKETING instead.
VERIFIED_CATEGORIES = ("ANALYTICS", "MARKETING", "PERSONALIZATION")


def intended_consent(scenario: Scenario) -> dict[str, str] | None:
    """What Osano.cm.getConsent() should report after the click; None when there is no click."""
    if scenario.action == "accept_all":
        return {c: "ACCEPT" for c in VERIFIED_CATEGORIES}
    if scenario.action == "deny_all":
        return {c: "DENY" for c in VERIFIED_CATEGORIES}
    if scenario.action == "custom":
        return {c: ("ACCEPT" if c in scenario.granted else "DENY") for c in VERIFIED_CATEGORIES}
    return None


def expected_gcs(scenario: Scenario, consent_model: str) -> str:
    """Google Consent Mode gcs value (G1<ads><analytics>) this scenario should produce.
    Osano maps MARKETING -> ad_storage and ANALYTICS -> analytics_storage."""
    allowed = allowed_categories(scenario, consent_model)
    ads = "1" if "MARKETING" in allowed else "0"
    analytics = "1" if "ANALYTICS" in allowed else "0"
    return f"G1{ads}{analytics}"
