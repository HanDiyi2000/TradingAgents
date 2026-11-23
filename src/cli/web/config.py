"""FEAT-06: the configuration form's options, reused from the CLI's own sources.

The page offers the same choices the CLI asks for, with the same defaults, so a
value the user sees in the browser is a value the CLI would have accepted. This
module reads those choices from ``cli.prompts`` and ``tradingagents`` rather than
restating them.
"""

from __future__ import annotations

from cli.models import AnalystType, AssetType
from cli.prompts import _llm_provider_table, filter_analysts_for_asset_type
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.llm_clients.model_catalog import get_model_options

# The research-depth values the CLI menu offers.
DEPTH_OPTIONS = [
    {"value": 1, "label": "Shallow"},
    {"value": 3, "label": "Medium"},
    {"value": 5, "label": "Deep"},
]

# The user-facing analyst labels, matching the CLI's checkbox text.
ANALYST_LABELS = {
    "market": "Market Analyst",
    "social": "Sentiment Analyst",
    "news": "News Analyst",
    "fundamentals": "Fundamentals Analyst",
    "options": "Options Analyst",
}


def default_analysts(asset_type: AssetType = AssetType.STOCK) -> list[str]:
    """Every analyst the asset type allows, in canonical order (options for stocks)."""
    allowed = filter_analysts_for_asset_type(list(AnalystType), asset_type)
    order = ["market", "social", "news", "fundamentals", "options"]
    values = {a.value for a in allowed}
    return [key for key in order if key in values]


def _catalog_models(provider: str) -> dict:
    """The catalog's (label, model_id) tuples as page options for one provider.

    ``MODEL_OPTIONS[provider][mode]`` is a list of ``(label, value)`` tuples, not
    objects, so each pair is unpacked positionally.
    """
    out = {}
    for mode in ("quick", "deep"):
        try:
            pairs = get_model_options(provider, mode)
        except KeyError:
            pairs = []
        out[mode] = [{"label": label, "value": value} for label, value in pairs]
    return out


def _custom_entry() -> dict:
    return {"label": "Custom model ID", "value": "custom"}


def models_for(provider: str) -> dict:
    """Quick/deep model options for ``provider``, as the page's model boxes need.

    ChatGPT (a subscription, not an API key) lists the signed-in plan's models
    through ``chatgpt_auth.list_models()``; a signed-out or unreachable plan
    keeps the manual model-ID entry and reports why. Other providers use the
    shared catalog. Read live so switching provider refreshes both boxes.
    """
    provider = (provider or "").lower()
    if provider == "chatgpt":
        return _chatgpt_models()
    return _catalog_models(provider)


def _chatgpt_models() -> dict:
    from tradingagents.llm_clients import chatgpt_auth

    try:
        listed = chatgpt_auth.list_models()
    except chatgpt_auth.ChatGPTAuthError as exc:
        needs_login = "login chatgpt" in str(exc)
        options = [_custom_entry()]
        return {
            "quick": list(options),
            "deep": list(options),
            "needs_login": needs_login,
            "error": str(exc) or chatgpt_auth.LOGIN_HINT,
        }
    except Exception as exc:  # a listing failure keeps manual entry and says why
        options = [_custom_entry()]
        return {
            "quick": list(options),
            "deep": list(options),
            "error": f"Could not list your ChatGPT plan's models: {exc}",
        }
    options = [{"label": name, "value": mid} for name, mid in listed]
    options.append(_custom_entry())
    return {"quick": list(options), "deep": list(options)}


def _models(provider: str) -> dict:
    return models_for(provider)


def form_config() -> dict:
    """Everything the form needs to render, with CLI-equivalent defaults."""
    provider = str(DEFAULT_CONFIG.get("llm_provider") or "openai").lower()
    providers = [{"value": key, "label": name} for name, key, _url in _llm_provider_table()]
    allowed = default_analysts()
    return {
        "providers": providers,
        "default_provider": provider,
        "models": _models(provider),
        "default_quick_think_llm": DEFAULT_CONFIG.get("quick_think_llm"),
        "default_deep_think_llm": DEFAULT_CONFIG.get("deep_think_llm"),
        "analysts": [
            {"value": key, "label": ANALYST_LABELS[key], "default": True} for key in allowed
        ],
        # The page reads `analysts_default` for the pre-checked set (FR-OPT-01).
        "analysts_default": allowed,
        "all_analysts": [
            {"value": key, "label": ANALYST_LABELS[key], "stock_only": key == "options"}
            for key in ANALYST_LABELS
        ],
        "depth_options": DEPTH_OPTIONS,
        "default_depth": DEFAULT_CONFIG.get("max_debate_rounds", 1),
        "default_output_language": DEFAULT_CONFIG.get("output_language", "English"),
        "asset_types": ["stock", "crypto"],
        "default_asset_type": "stock",
    }
