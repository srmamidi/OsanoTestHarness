# AI-GENERATED: create
# AI Technology: Claude Code (Opus 5.5, claude-opus-5-5)
# Reviewer: Sarada Mamidi, DevOps Manager - review required before merge
"""Osano consent test harness: measure what a site really does under each consent choice,
save it as a snapshot, and compare a "before" snapshot with an "after" one."""

__version__ = "1.0.0"

# Osano's consent categories (CMP JavaScript API names).
CATEGORIES = ("ESSENTIAL", "ANALYTICS", "MARKETING", "PERSONALIZATION", "OPT-OUT")
NON_ESSENTIAL = ("ANALYTICS", "MARKETING", "PERSONALIZATION", "OPT-OUT")
# Seen on the page but known to neither the vendor catalog nor the Osano config.
UNCLASSIFIED = "UNCLASSIFIED"
