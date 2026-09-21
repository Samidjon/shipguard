"""
Central configuration for ShipGuard.

Single source of truth for anything that would otherwise be duplicated
across modules or hardcoded in several places.
"""

import os
from pathlib import Path


# =============================================================
# PATHS
# =============================================================

# shipguard/config.py -> shipguard/ -> repository root
REPO_ROOT = Path(__file__).resolve().parents[1]


# =============================================================
# .env LOADING
# =============================================================


def load_env_file(env_path=None):
    """
    Load a .env file, if present. Returns True when a file was read.

    Without this a local .env is silently ignored: everything reads
    credentials through os.getenv, which does not know about files. The path
    is explicit rather than discovered from the working directory, and real
    environment variables take precedence over the file.
    """

    try:
        from dotenv import load_dotenv
    except ImportError:
        # python-dotenv is optional; environment variables still work.
        return False

    path = Path(env_path) if env_path else REPO_ROOT / ".env"

    if not path.is_file():
        return False

    load_dotenv(path, override=False)

    return True


load_env_file()

DATA_SOURCE_ENV_VAR = "SHIPGUARD_DATA"

DEFAULT_DATA_SOURCE = REPO_ROOT / "sdoc-hackathon-bundle"


def get_data_source():
    """
    Location of the email inbox and attachments.

    Anchored to the repository root so the pipeline behaves the same from
    any working directory. Override with the SHIPGUARD_DATA environment
    variable to point at another bundle or an HTTP server URL.
    """

    value = os.getenv(DATA_SOURCE_ENV_VAR)

    if value and value.strip():
        return value.strip()

    return DEFAULT_DATA_SOURCE


# Output artifacts always land next to the repository root, never in the
# current working directory.
RESULTS_PATH = REPO_ROOT / "results.json"
SUBMISSION_PATH = REPO_ROOT / "submission.json"


# =============================================================
# COMPARED FIELDS
# =============================================================

# The seven fields compared between a Shipping Instruction and a draft
# Bill of Lading. Order matters for display and for the comparison
# report, so keep this list as the only definition.
FIELDS = [
    "shipper",
    "consignee",
    "notify_party",
    "port_of_loading",
    "port_of_discharge",
    "container_count",
    "gross_weight_kg",
]


# =============================================================
# GEMINI MODEL
# =============================================================

GEMINI_MODEL_ENV_VAR = "GEMINI_MODEL"

# Candidate models tried in order, cheapest/fastest first.
#
# The AI layer walks this list and advances to the next entry only when
# the API reports the model does not exist, so a stale first entry cannot
# break the app. Set the GEMINI_MODEL environment variable to pin one
# model explicitly and skip the fallback logic entirely.
# Verified against a live key by actually calling each model, not merely by
# listing them: models.list() also returns models that answer 404 on
# generateContent. gemini-2.5-flash-lite is one of those — the API replies
# "no longer available to new users. Please update your code to use
# models/gemini-3.5-flash-lite", so that recommendation leads here.
#
# The "-latest" aliases follow as fallbacks: they track whatever Google
# currently ships, which keeps the app alive when a pinned version is retired.
MODEL_CANDIDATES = (
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash",
    "gemini-flash-latest",
)

DEFAULT_GEMINI_MODEL = MODEL_CANDIDATES[0]


def get_model_override():
    """
    Return the model pinned via the GEMINI_MODEL environment variable,
    or None when no override is configured.

    Read at call time (not import time) so the environment can change
    between calls, which also keeps it testable.
    """

    value = os.getenv(GEMINI_MODEL_ENV_VAR)

    if value and value.strip():
        return value.strip()

    return None
