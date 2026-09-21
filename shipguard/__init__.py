"""
ShipGuard — AI-assisted shipping document verification.

The deterministic engine in this package owns every verdict. The AI layer
(:mod:`shipguard.ai_service`) only classifies email intent and explains
results in natural language; it never decides whether documents match.
"""

__all__ = [
    "ai_service",
    "classifier",
    "comparator",
    "config",
    "document_reader",
    "extractor",
    "loader",
    "pipeline",
]
