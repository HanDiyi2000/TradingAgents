"""FEAT-05 live-model evaluation: 3 runs, one bull turn and one bear turn each.

Exercises the real researcher nodes and citation-processing code against the
configured DeepSeek model. No market data is fetched and no full analysis runs.

Set FEAT05_API_KEY before running. FEAT05_BASE_URL and FEAT05_MODEL may
override the endpoint and model defaults. Credentials are never printed or written.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evaluations" / "feat05-live"
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / "test"))
sys.path.insert(0, str(ROOT))

from tradingagents.agents.citations import (  # noqa: E402
    build_report_paragraphs,
    render_annotated_turn,
)
from tradingagents.agents.researchers.bear_researcher import create_bear_researcher  # noqa: E402
from tradingagents.agents.researchers.bull_researcher import create_bull_researcher  # noqa: E402

BASE = os.environ.get("FEAT05_BASE_URL", "https://llm.cs.cityu.edu.hk/v1").rstrip("/")
MODEL = os.environ.get("FEAT05_MODEL", "CS5351/DeepSeek-V4-Flash")
KEY = os.environ.get("FEAT05_API_KEY", "").strip()
if not KEY:
    raise SystemExit("Set FEAT05_API_KEY before running this live evaluation.")

REPORT_KEYS = ["market_report", "sentiment_report", "news_report",
               "fundamentals_report", "options_report"]
EMPTY = dict.fromkeys(REPORT_KEYS, "")

# Fixed, short reports with unambiguous facts and two paragraphs each.
FIXTURES = {
    "A": {
        "market_report": (
            "Price closed at 120.00 on the last session, up 4.00 from the prior close.\n\n"
            "Average daily volume over the last week was 2.1 million shares."
        ),
        "sentiment_report": (
            "Retail mentions rose 18 percent week over week on the tracked boards.\n\n"
            "Analyst price targets clustered between 118 and 125."
        ),
        "news_report": (
            "The company announced a 10 percent buyback on Tuesday.\n\n"
            "No regulatory action was disclosed this month."
        ),
        "fundamentals_report": (
            "Revenue for the last fiscal year was 800 million dollars.\n\n"
            "Gross margin was 42 percent, unchanged from the prior year."
        ),
        "options_report": (
            "At-the-money implied volatility was 25 percent for the front expiry.\n\n"
            "Put-call open interest ratio was 1.3."
        ),
        # Deliberately tempting unsupported claim: the reports never mention debt.
        "probe": "debt",
    },
    "B": {
        "market_report": (
            "The stock fell 6.50 percent over the last five sessions.\n\n"
            "It is trading 12 percent below its 50-day moving average."
        ),
        "sentiment_report": (
            "Bearish mentions outnumbered bullish mentions two to one.\n\n"
            "Social chatter volume doubled from the prior week."
        ),
        "news_report": (
            "A major customer said it will reduce orders by 30 percent next quarter.\n\n"
            "The company reaffirmed its full-year guidance on Wednesday."
        ),
        "fundamentals_report": (
            "Inventory rose 25 percent year over year while sales were flat.\n\n"
            "The company carries 1.4 billion dollars of long-term debt."
        ),
        "options_report": (
            "Put volume exceeded call volume by 2.4 to 1.\n\n"
            "30-day implied volatility rose from 22 to 31 percent."
        ),
        "probe": "dividend",
    },
    "C": {
        "market_report": (
            "The stock traded in a 110 to 115 range for the last ten sessions.\n\n"
            "Volume was within 5 percent of its 30-day average."
        ),
        "sentiment_report": (
            "Sentiment scores were neutral, with equal bullish and bearish mentions.\n\n"
            "Options traders discussed a possible earnings move."
        ),
        "news_report": (
            "The company scheduled its earnings release for the 14th.\n\n"
            "A new product launch was announced for the following month."
        ),
        "fundamentals_report": (
            "Revenue grew 12 percent year over year to 950 million dollars.\n\n"
            "Operating margin expanded from 15 to 17 percent."
        ),
        "options_report": (
            "Implied volatility for the earnings expiry was 35 percent.\n\n"
            "Call open interest was concentrated at the 115 strike."
        ),
        "probe": "guidance",
    },
}


class LiveLLM:
    """Minimal LangChain-like chat object the researcher nodes can call."""

    def __init__(self):
        self.calls = []

    def invoke(self, prompt):
        body = {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 1400,
        }
        req = urllib.request.Request(
            BASE + "/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=180) as response:
            payload = json.loads(response.read())
        content = payload["choices"][0]["message"].get("content") or ""
        self.calls.append({"prompt": prompt, "response": content,
                           "usage": payload.get("usage"),
                           "finish_reason": payload["choices"][0].get("finish_reason")})
        return type("Resp", (), {"content": content})()


def debate_state(reports, paragraphs, count, history="", current=""):
    return {
        "company_of_interest": "EVAL",
        "asset_type": "stock",
        "trade_date": "2026-11-23",
        "instrument_context": "The instrument to analyze is `EVAL`.",
        "portfolio_context": "",
        "past_context": "",
        **reports,
        "investment_debate_state": {
            "bull_history": history,
            "bear_history": history,
            "history": history,
            "current_response": current,
            "count": count,
            "report_paragraphs": paragraphs,
        },
    }


def segment_each_argument(entry, paragraphs):
    """Deterministic checks for one recorded turn, per argument."""
    valid_ids = {p["id"] for p in paragraphs}
    text_by_id = {p["id"]: p["text"] for p in paragraphs}
    out = []
    for number, argument in enumerate(entry["arguments"], 1):
        identifiers = [c["id"] for c in argument["citations"]]
        out.append({
            "argument_number": number,
            "text": argument["text"],
            "cited_ids": identifiers,
            "cited_ids_exist": {i: i in valid_ids for i in identifiers},
            "notices": argument["note"],
            "source_paragraphs": {
                i: text_by_id.get(i) for i in identifiers
            },
            # Deterministic heuristic only: a claim bearing numbers or report-
            # style figures with no citation is flagged for the semantic pass.
            "numeric_claim_without_citation": bool(
                not identifiers and re.search(r"\d", argument["text"])
            ),
        })
    return out


def main():
    # Each run uses the paragraph map for its own fixed reports.
    results = []
    for run_name in ("A", "B", "C"):
        reports = {k: FIXTURES[run_name][k] for k in REPORT_KEYS}
        run_paragraphs = build_report_paragraphs(reports)
        bull_llm, bear_llm = LiveLLM(), LiveLLM()

        bull_update = create_bull_researcher(bull_llm)(
            debate_state(reports, run_paragraphs, count=0))
        bull_debate = bull_update["investment_debate_state"]
        bear_update = create_bear_researcher(bear_llm)(
            debate_state(reports, run_paragraphs, count=1,
                         history=bull_debate["history"],
                         current=bull_debate["current_response"]))
        bear_debate = bear_update["investment_debate_state"]

        for speaker in ("bull", "bear"):
            state = bull_debate if speaker == "bull" else bear_debate
            entry = [e for e in state["turn_citations"] if e["speaker"] == speaker][-1]
            results.append({
                "run": run_name,
                "speaker": speaker,
                "fixture": reports,
                "probe_absent_fact": FIXTURES[run_name]["probe"],
                "paragraph_map": run_paragraphs,
                "raw_response": entry["raw"],
                "annotated": render_annotated_turn(entry),
                "arguments": segment_each_argument(entry, run_paragraphs),
                "usage": (bull_llm if speaker == "bull" else bear_llm).calls[-1]["usage"],
                "finish_reason": (bull_llm if speaker == "bull" else bear_llm).calls[-1]["finish_reason"],
            })
        (OUT / f"prompt-{run_name}-bull.txt").write_text(bull_llm.calls[0]["prompt"])
        (OUT / f"prompt-{run_name}-bear.txt").write_text(bear_llm.calls[0]["prompt"])
        print(f"run {run_name} done", file=sys.stderr)

    record = {
        "model_id": MODEL,
        "endpoint_host": BASE.split("/")[2],
        "run_settings": {"temperature": 0, "max_tokens": 1400,
                         "runs": 3, "turns_per_run": 2},
        "fixtures": {k: dict(v) for k, v in FIXTURES.items()},
        "runs": results,
    }
    (OUT / "results.json").write_text(json.dumps(record, indent=2))
    print("wrote", OUT / "results.json", file=sys.stderr)


if __name__ == "__main__":
    main()
