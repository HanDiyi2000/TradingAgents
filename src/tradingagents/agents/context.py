"""Prompt context shared by the agents: instrument identity, output language and portfolio."""

import functools
import logging
import re
from collections.abc import Mapping
from typing import Any

from tradingagents.dataflows.date_window import is_historical
from tradingagents.dataflows.vendors.yahoo.fundamentals import get_company_profile

logger = logging.getLogger(__name__)


def get_language_instruction() -> str:
    """Return a prompt instruction for the configured output language.

    Returns empty string when English (default), so no extra tokens are used.
    Applied to every agent whose output reaches the saved report —
    analysts, researchers, debaters, research manager, trader, and
    portfolio manager — so a non-English run produces a fully localized
    report rather than a mix of languages.
    """
    from tradingagents.dataflows.config import get_config
    lang = get_config().get("output_language", "English")
    if lang.strip().lower() == "english":
        return ""
    # The labelled lines are read by the program, so they keep their English
    # label and value: a translated rating line leaves the reader prose to
    # search, where a negated rating ("not a Sell") reads as the call (#1435).
    return (
        f" Write your entire response in {lang}, except the labelled lines the format"
        f" asks for (the \"**Rating**:\" line, \"FINAL TRANSACTION PROPOSAL:\"):"
        f" keep their label and value in English, exactly as specified."
    )


def opponent_argument_or_opening(text: str, opponent: str) -> str:
    """Opponent's latest argument, or an explicit opening marker when empty.

    The first speaker in each debate round receives an empty opponent response;
    interpolating it into a "refute the opponent" prompt makes the model
    fabricate the other side's position. Returning a clear "has not spoken yet"
    marker instead lets it open with its own case (#1176).
    """
    text = (text or "").strip()
    if text:
        return text
    return f"(The {opponent} has not spoken yet — open the debate with your own case.)"


def _clean_identity_value(value: Any) -> str | None:
    """Return a trimmed string, or None for empty / placeholder-ish values."""
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned or cleaned.lower() in {"none", "n/a", "nan", "null"}:
        return None
    return cleaned


# A sentence ends at . ! or ? followed by whitespace or the end of the text. A
# decimal ("3.5") is followed by a digit, not whitespace, so it does not split.
_SENTENCE_END = re.compile(r"(?<=[.!?])(?:\s+|$)")


def first_sentences(text: str, limit: int = 2) -> str:
    """The first ``limit`` complete sentences of ``text``, unsummarised.

    The source is split at sentence boundaries and the first one or two complete
    sentences are returned verbatim; no character cap truncates a sentence, so a
    long first sentence is kept whole. Limitations: abbreviations and initials
    (e.g. ``Inc.``) may be read as sentence ends, and an unterminated final
    fragment is dropped rather than shown truncated.
    """
    text = (text or "").strip()
    if not text:
        return ""
    pieces = _SENTENCE_END.split(text)
    sentences = [piece.strip() for piece in pieces if piece.strip()]
    return " ".join(sentences[:limit])


def resolve_instrument_identity(ticker: str) -> dict:
    """Resolve deterministic identity metadata (company name, sector, …) for a ticker.

    This exists to stop the pipeline from hallucinating a *different* company
    when a chart pattern suggests a different industry than the real one
    (#814): without a ground-truth name, the market analyst would pattern-match
    the price action to a narrative and invent an identity that then cascaded
    through every downstream agent.

    Best-effort by design: if yfinance is unavailable, rate-limited, or doesn't
    recognise the ticker, we return ``{}`` and the caller falls back to
    ticker-only context rather than failing before analysis starts. An answer
    is cached for the process; a failed lookup is asked again next time.

    Identity resolves for the same instrument the price path fetches
    (``XAUUSD`` -> ``GC=F``, #983).
    """
    try:
        return _identity(ticker)
    except Exception as exc:  # noqa: BLE001 — fail open, never block the run
        logger.debug("Could not resolve instrument identity for %s: %s", ticker, exc)
        return {}


@functools.lru_cache(maxsize=256)
def _identity(ticker: str) -> dict:
    """The vendor's identity fields for ``ticker``; raises if the lookup fails."""
    info = get_company_profile(ticker)
    identity: dict[str, str] = {}
    company_name = _clean_identity_value(info.get("longName")) or _clean_identity_value(
        info.get("shortName")
    )
    if company_name:
        identity["company_name"] = company_name
    for source_key, target_key in (
        ("sector", "sector"),
        ("industry", "industry"),
        ("exchange", "exchange"),
        ("quoteType", "quote_type"),
    ):
        value = _clean_identity_value(info.get(source_key))
        if value:
            identity[target_key] = value
    # The vendor's own business summary, kept for the report's Company Background.
    # It carries no historical vintage (like name/industry), so it is only shown
    # for a current run; the exporter filters it with the same point-in-time rule.
    description = _clean_identity_value(info.get("longBusinessSummary"))
    if description:
        identity["business_description"] = description
    return identity


def build_instrument_context(
    ticker: str,
    asset_type: str = "stock",
    identity: Mapping[str, str] | None = None,
    trade_date: str | None = None,
) -> str:
    """Describe the exact instrument so agents preserve identity and ticker.

    When ``identity`` is provided (resolved deterministically via
    :func:`resolve_instrument_identity`), the company name and business
    classification are injected so agents anchor to the real company rather
    than pattern-matching the price chart to a wrong one (#814).

    That profile carries no historical vintage: it describes the company today.
    A run dated earlier gets the current name alone, as a way to tell the
    company apart from others rather than as what it was called then; a sector,
    industry or exchange it holds today is not given, since it may not have held
    on the analysis date.
    """
    is_crypto = asset_type == "crypto"
    instrument_label = "asset" if is_crypto else "instrument"
    context = (
        f"The {instrument_label} to analyze is `{ticker}`. "
        "The tools serve this instrument; refer to it by this exact ticker in every report and recommendation, "
        "preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`, `-USD`)."
    )

    identity = identity or {}
    name = identity.get("company_name") or identity.get("name")
    label = "Name" if is_crypto else "Company"
    details = []
    if is_historical(trade_date):
        if name:
            details.append(
                f"{label}: {name} (its current name, given only to identify it; "
                f"on {trade_date} it may have been named differently)"
            )
    else:
        if name:
            details.append(f"{label}: {name}")
        sector, industry = identity.get("sector"), identity.get("industry")
        if sector and industry:
            details.append(f"Business classification: {sector} / {industry}")
        elif sector:
            details.append(f"Sector: {sector}")
        elif industry:
            details.append(f"Industry: {industry}")
        if identity.get("exchange"):
            details.append(f"Exchange: {identity['exchange']}")

    if details:
        context += (
            f" Resolved identity: {'; '.join(details)}. "
            "Do not substitute a different company or ticker unless a tool "
            "result explicitly disproves this resolved identity."
        )

    if is_crypto:
        context += (
            " Treat it as a crypto asset rather than a company, and do not "
            "assume company fundamentals are available."
        )
    return context


def get_instrument_context_from_state(state: Mapping[str, Any]) -> str:
    """Return the instrument context for the current run.

    Prefers the identity-resolved context computed once at run start and
    stored on the state (see ``TradingAgentsGraph.resolve_instrument_context``).
    Falls back to a ticker-only context — with no network lookup — when the
    state was constructed without it (bare programmatic states, tests), so a
    consumer is never forced to make a yfinance call mid-graph.
    """
    context = state.get("instrument_context")
    if isinstance(context, str) and context.strip():
        return context
    return build_instrument_context(
        str(state["company_of_interest"]),
        state.get("asset_type", "stock"),
    )


def report_or_absent(text: str, source: str) -> str:
    """An analyst's report, or a marker saying it was never produced.

    A report is empty when its analyst was not selected, refused, or returned
    nothing. Interpolating that into a labelled section presents an absence as a
    blank finding, and the reading agent fills it in from nothing, the same way
    an empty opponent argument used to invite an invented rebuttal (#1176).
    """
    text = (text or "").strip()
    if text:
        return text
    return f"(No {source} report in this run: it is not available, not an empty finding.)"


def get_portfolio_context_from_state(state: Mapping[str, Any]) -> str:
    """Return the caller's portfolio block, or a notice that none was given.

    A run without portfolio context must not read as a flat book: the agents
    would otherwise size as if the caller held nothing, which is a claim about
    an account we were never told about.
    """
    context = state.get("portfolio_context")
    if isinstance(context, str) and context.strip():
        return context
    return (
        "Portfolio context: not provided. You do not know the caller's current "
        "holdings or cash, so do not assume a flat book; give direction and "
        "sizing guidance in terms the caller can apply to their own position."
    )


# The company profile retained for the report, keyed on the run state. It holds
# only the cleaned fields the Company Background shows.
_COMPANY_IDENTITY_FIELDS = ("company_name", "industry", "business_description")


def retained_company_identity(identity: Mapping[str, str] | None) -> dict[str, str]:
    """The cleaned profile to keep on a run: name, industry and description only.

    A run retains this once at initialization from the identity already resolved
    for the instrument context, so export never looks the profile up again. Only
    non-empty cleaned fields are kept; a profile with none is empty.
    """
    identity = identity or {}
    kept: dict[str, str] = {}
    for key in _COMPANY_IDENTITY_FIELDS:
        value = _clean_identity_value(identity.get(key))
        if value:
            kept[key] = value
    return kept


def company_profile_view(identity: Mapping[str, str] | None, trade_date: str | None) -> dict:
    """What the report may show of a run's profile, filtered for the analysis date.

    For a current run (analysis date today, the default) the name, industry and
    a one- or two-sentence slice of the source business description are shown. For
    a historical run the vendor's profile carries no vintage, so only the name is
    shown, marked as today's; undated industry and description are withheld. Empty
    fields are omitted. The returned view is ``{name, name_is_current, industry,
    business_description}``; every value not shown is None.
    """
    view = {"name": None, "name_is_current": False,
            "industry": None, "business_description": None}
    identity = identity or {}
    name = _clean_identity_value(identity.get("company_name"))
    if is_historical(trade_date):
        if name:
            view["name"] = name
            view["name_is_current"] = True
        return view
    if name:
        view["name"] = name
    industry = _clean_identity_value(identity.get("industry"))
    if industry:
        view["industry"] = industry
    description = first_sentences(_clean_identity_value(identity.get("business_description")) or "")
    if description:
        view["business_description"] = description
    return view


def build_company_background(final_state: Mapping[str, Any]) -> dict:
    """The run's prepared Company Background, from stored state only.

    Reads the retained ``company_identity`` and the analysis ``trade_date`` from
    ``final_state`` and returns the filtered view. It performs no lookup, reads no
    cache and makes no model call, so export is a pure function of the run. An
    old state without ``company_identity`` yields an all-None view (the exporter
    then shows the unavailable notice).
    """
    identity = final_state.get("company_identity") or {}
    if not isinstance(identity, Mapping):
        identity = {}
    return company_profile_view(identity, final_state.get("trade_date"))
