"""
AI layer behaviour.

The deterministic engine owns the verdict, so what matters here is that the
AI layer targets a real model, survives a flaky API, and degrades into a
predictable payload instead of taking the app down.
"""

import os

import pytest

from shipguard import ai_service, config


@pytest.fixture(autouse=True)
def reset_model_cache(monkeypatch):
    """
    The resolved-model cache is process-wide; clear it between tests.
    """

    monkeypatch.setattr(ai_service, "_resolved_model", None)
    monkeypatch.delenv(config.GEMINI_MODEL_ENV_VAR, raising=False)


class FakeModels:
    def __init__(self, working_model=None, error=None):
        self.working_model = working_model
        self.error = error
        self.tried = []

    def generate_content(self, model, contents):
        self.tried.append(model)

        if self.error is not None:
            raise self.error

        if self.working_model is not None and model != self.working_model:
            raise RuntimeError("404 NOT_FOUND: model not found")

        return type("Response", (), {"text": '{"ok": true}'})()


class FakeClient:
    def __init__(self, working_model=None, error=None):
        self.models = FakeModels(working_model, error)


# =============================================================
# MODEL SELECTION
# =============================================================


def test_the_model_is_not_hardcoded_in_the_ai_layer():
    """
    config is the single source of truth for the model. A module-level
    constant in ai_service would bypass both the env override and the
    fallback chain.
    """

    assert not hasattr(ai_service, "MODEL")
    assert config.MODEL_CANDIDATES
    assert config.DEFAULT_GEMINI_MODEL == config.MODEL_CANDIDATES[0]


def test_retired_model_is_not_the_default():
    """
    gemini-2.5-flash-lite still appears in models.list() but answers 404 for
    new API keys: "no longer available to new users. Please update your code
    to use models/gemini-3.5-flash-lite". Leading with it would cost a failed
    round trip on every cold start.
    """

    assert config.MODEL_CANDIDATES[0] != "gemini-2.5-flash-lite"


def test_default_candidates_are_tried_when_nothing_is_pinned():
    assert ai_service.candidate_models() == list(config.MODEL_CANDIDATES)


def test_environment_override_pins_a_single_model(monkeypatch):
    monkeypatch.setenv(config.GEMINI_MODEL_ENV_VAR, "gemini-custom-x")

    assert config.get_model_override() == "gemini-custom-x"
    assert ai_service.candidate_models() == ["gemini-custom-x"]


def test_blank_override_is_ignored(monkeypatch):
    monkeypatch.setenv(config.GEMINI_MODEL_ENV_VAR, "   ")

    assert config.get_model_override() is None


def test_override_is_read_at_call_time(monkeypatch):
    assert ai_service.candidate_models() == list(config.MODEL_CANDIDATES)

    monkeypatch.setenv(config.GEMINI_MODEL_ENV_VAR, "gemini-late-binding")

    assert ai_service.candidate_models() == ["gemini-late-binding"]


# =============================================================
# CANDIDATE FALLBACK
# =============================================================


def test_unavailable_model_falls_through_to_the_next_candidate():
    working = config.MODEL_CANDIDATES[2]
    client = FakeClient(working_model=working)

    response = ai_service.generate_with_retry(client, "prompt")

    assert response.text == '{"ok": true}'
    assert client.models.tried == list(config.MODEL_CANDIDATES[:3])


def test_a_working_model_is_reused_for_later_calls():
    working = config.MODEL_CANDIDATES[1]
    client = FakeClient(working_model=working)

    ai_service.generate_with_retry(client, "prompt")

    assert ai_service.candidate_models() == [working]


def test_a_pinned_model_is_not_replaced_by_fallback(monkeypatch):
    monkeypatch.setenv(config.GEMINI_MODEL_ENV_VAR, "gemini-pinned")

    client = FakeClient(working_model="something-else")

    with pytest.raises(RuntimeError):
        ai_service.generate_with_retry(client, "prompt")

    assert client.models.tried == ["gemini-pinned"]


def test_transient_errors_are_retried_then_raised(monkeypatch):
    monkeypatch.setattr(ai_service.time, "sleep", lambda seconds: None)

    client = FakeClient(error=RuntimeError("503 UNAVAILABLE"))

    with pytest.raises(RuntimeError):
        ai_service.generate_with_retry(client, "prompt", attempts=3)

    # Same model retried three times rather than skipped as unavailable.
    assert client.models.tried == [config.MODEL_CANDIDATES[0]] * 3


def test_unexpected_errors_are_raised_immediately():
    client = FakeClient(error=RuntimeError("400 INVALID_ARGUMENT"))

    with pytest.raises(RuntimeError):
        ai_service.generate_with_retry(client, "prompt")

    assert client.models.tried == [config.MODEL_CANDIDATES[0]]


@pytest.mark.parametrize(
    "text, temporary",
    [
        ("503 Service Unavailable", True),
        ("UNAVAILABLE", True),
        ("The model is overloaded due to high demand", True),
        ("404 NOT_FOUND", False),
        ("400 INVALID_ARGUMENT", False),
    ],
)
def test_temporary_error_detection(text, temporary):
    assert ai_service.is_temporary_error(text) is temporary


@pytest.mark.parametrize(
    "text, missing",
    [
        ("404 NOT_FOUND", True),
        ("models/foo is not found for API version v1beta", True),
        ("503 UNAVAILABLE", False),
    ],
)
def test_model_not_found_detection(text, missing):
    assert ai_service.is_model_not_found_error(text) is missing


# =============================================================
# GRACEFUL DEGRADATION
# =============================================================


def test_email_analysis_degrades_to_an_error_payload(monkeypatch):
    monkeypatch.setattr(ai_service, "get_client", lambda: FakeClient())
    monkeypatch.setattr(
        ai_service,
        "generate_with_retry",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    result = ai_service.analyze_shipping_email("subject", "body")

    assert result["category"] == "ERROR"
    assert result["confidence"] == 0.0
    assert "summary" in result


def test_invalid_json_from_the_model_degrades_cleanly(monkeypatch):
    monkeypatch.setattr(ai_service, "get_client", lambda: FakeClient())

    class BadResponse:
        text = "this is not json"

    monkeypatch.setattr(
        ai_service,
        "generate_with_retry",
        lambda *args, **kwargs: BadResponse(),
    )

    result = ai_service.analyze_shipping_email("subject", "body")

    assert result["category"] == "ERROR"


def test_discrepancy_explanation_degrades_cleanly(monkeypatch):
    monkeypatch.setattr(ai_service, "get_client", lambda: FakeClient())
    monkeypatch.setattr(
        ai_service,
        "generate_with_retry",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    result = ai_service.analyze_document_discrepancies(
        subject="s",
        body="b",
        comparison_rows=[
            {
                "field": "port_of_loading",
                "si": "SINGAPORE",
                "bl": "PORT KLANG",
                "result": "MISMATCH",
            }
        ],
        status="MISMATCH",
    )

    assert result["discrepancies"] == []
    assert "headline" in result
    assert "recommendation" in result


def test_a_missing_api_key_reports_a_clear_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(ai_service, "get_gemini_api_key", lambda: None)

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        ai_service.get_client()


# =============================================================
# RESPONSE CLEANING
# =============================================================


@pytest.mark.parametrize(
    "raw",
    [
        '{"category": "GENERAL"}',
        '```json\n{"category": "GENERAL"}\n```',
        '```\n{"category": "GENERAL"}\n```',
    ],
)
def test_markdown_fences_are_stripped(raw):
    import json

    cleaned = ai_service.clean_json_response(raw)

    assert json.loads(cleaned) == {"category": "GENERAL"}


# =============================================================
# MODEL DISCOVERY
# =============================================================


def test_discover_models_lists_generate_content_models():
    class Model:
        def __init__(self, name, actions):
            self.name = name
            self.supported_actions = actions

    class ListingModels:
        def list(self):
            return [
                Model("models/gemini-a", ["generateContent"]),
                Model("models/embedding-b", ["embedContent"]),
            ]

    class ListingClient:
        models = ListingModels()

    available = ai_service.discover_models(ListingClient())

    assert available == ["gemini-a"]


# =============================================================
# LIVE API (skipped without credentials)
# =============================================================


@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY is not set; skipping live Gemini call",
)
def test_live_model_is_reachable():
    """
    Confirms the configured model actually exists for this API key.
    """

    available = ai_service.discover_models()

    assert available

    chosen = config.get_model_override() or config.DEFAULT_GEMINI_MODEL

    assert any(chosen in model for model in available), (
        f"{chosen} is not available; choose one of {available}"
    )


@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY is not set; skipping live Gemini call",
)
def test_live_email_classification_returns_a_known_category():
    from shipguard.classifier import CATEGORIES

    result = ai_service.analyze_shipping_email(
        "TO CONFIRM DOCS _ 5RSG-00133",
        "Attached are the SI and draft BL. Please check and confirm.",
    )

    assert result["category"] in list(CATEGORIES) + ["ERROR"]


@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY is not set; skipping live Gemini call",
)
def test_live_discrepancy_explanation_has_the_expected_shape():
    """
    The explanation layer must describe the verdict it was given without
    being asked to decide anything.
    """

    result = ai_service.analyze_document_discrepancies(
        subject="Draft BL - amend BL 055",
        body="Please verify and confirm the draft bill of lading.",
        comparison_rows=[
            {
                "field": "port_of_loading",
                "si": "PORT KLANG (WESTPORT), MALAYSIA",
                "bl": "RUGAO/NANTONG/SHANGHAI, CHINA",
                "result": "MISMATCH",
            },
            {
                "field": "shipper",
                "si": "ASIA PACIFIC PAPERBOARD TRADING PTE LTD",
                "bl": "ASIA PACIFIC PAPERBOARD TRADING PTE LTD",
                "result": "MATCH",
            },
        ],
        status="MISMATCH",
    )

    assert {"headline", "summary", "discrepancies", "recommendation"} <= set(
        result
    )
    assert isinstance(result["discrepancies"], list)


# =============================================================
# .env LOADING
# =============================================================


def test_env_file_is_actually_loaded(tmp_path, monkeypatch):
    """
    python-dotenv being installed is not enough — something has to call it.
    Credentials are read through os.getenv, which knows nothing about files,
    so a .env sitting in the repo would otherwise be silently ignored.
    """

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=from-the-env-file\n", encoding="utf-8")

    assert config.load_env_file(env_file) is True
    assert os.getenv("GEMINI_API_KEY") == "from-the-env-file"


def test_real_environment_wins_over_the_env_file(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "from-the-real-environment")

    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=from-the-env-file\n", encoding="utf-8")

    config.load_env_file(env_file)

    assert os.getenv("GEMINI_API_KEY") == "from-the-real-environment"


def test_missing_env_file_is_not_an_error(tmp_path):
    assert config.load_env_file(tmp_path / "nope.env") is False
