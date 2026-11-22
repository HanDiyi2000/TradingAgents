from tradingagents.agents.context import (
    get_instrument_context_from_state,
    get_language_instruction,
    opponent_argument_or_opening,
    report_or_absent,
)
from tradingagents.agents.debate_progress import (
    EARLY_STOP_REASON,
    NO_PROGRESS,
    evaluate_pair,
)
from tradingagents.dataflows.config import get_config


def create_bear_researcher(llm, judge=None):
    def bear_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bear_history = investment_debate_state.get("bear_history", "")

        current_response = opponent_argument_or_opening(
            investment_debate_state.get("current_response", ""), "bull analyst"
        )
        market_research_report = report_or_absent(state["market_report"], "market")
        sentiment_report = report_or_absent(state["sentiment_report"], "sentiment")
        news_report = report_or_absent(state["news_report"], "news")
        fundamentals_report = report_or_absent(state["fundamentals_report"], "fundamentals")
        options_report = report_or_absent(state.get("options_report", ""), "options")
        instrument_context = get_instrument_context_from_state(state)
        asset_type = state.get("asset_type", "stock")
        target_label = "stock" if asset_type == "stock" else "asset"
        fundamentals_label = (
            "Company fundamentals report"
            if asset_type == "stock"
            else "Asset fundamentals report (may be unavailable for crypto)"
        )

        prompt = f"""You are a Bear Analyst making the case against investing in the {target_label}. Your goal is to present a well-reasoned argument emphasizing risks, challenges, and negative indicators. Leverage the provided research and data to highlight potential downsides and counter bullish arguments effectively.

Key points to focus on:

- Risks and Challenges: Highlight factors like market saturation, financial instability, or macroeconomic threats that could hinder the stock's performance.
- Competitive Weaknesses: Emphasize vulnerabilities such as weaker market positioning, declining innovation, or threats from competitors.
- Negative Indicators: Use evidence from financial data, market trends, or recent adverse news to support your position.
- Bull Counterpoints: Critically analyze the bull argument with specific data and sound reasoning, exposing weaknesses or over-optimistic assumptions.
- Engagement: Present your argument in a conversational style, directly engaging with the bull analyst's points and debating effectively rather than simply listing facts.

Resources available:

{instrument_context}
Market research report: {market_research_report}
Social media sentiment report: {sentiment_report}
Latest world affairs news: {news_report}
{fundamentals_label}: {fundamentals_report}
Options market report: {options_report}
Conversation history of the debate: {history}
Last bull argument: {current_response}
Use this information to deliver a compelling bear argument, refute the bull's claims, and engage in a dynamic debate that demonstrates the risks and weaknesses of investing in the {target_label}.
""" + get_language_instruction()

        response = llm.invoke(prompt)

        argument = f"Bear Analyst: {response.content}"

        new_history = history + "\n" + argument
        new_count = investment_debate_state["count"] + 1
        new_investment_debate_state = {
            "history": new_history,
            "bear_history": bear_history + "\n" + argument,
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": argument,
            "count": new_count,
            # Carry any earlier decision forward; a fresh judgement may replace it.
            "progress_outcome": investment_debate_state.get("progress_outcome", ""),
            "progress_round": investment_debate_state.get("progress_round", 0),
            "progress_reason": investment_debate_state.get("progress_reason", ""),
        }

        # FEAT-02: judge only a completed pair between round two and the cap, i.e.
        # an even new count with 4 <= count < 2*cap. The cap and the opening pair
        # never invoke the judge.
        if judge is not None and _is_eligible_pair(new_count):
            round_number = new_count // 2
            previous_bull = investment_debate_state.get("bull_history", "")
            bull_turn = _latest_bull_turn(previous_bull)
            result = evaluate_pair(judge, history, bull_turn, argument, round_number)
            new_investment_debate_state["progress_outcome"] = result.outcome
            new_investment_debate_state["progress_round"] = result.evaluated_round
            new_investment_debate_state["progress_reason"] = (
                EARLY_STOP_REASON if result.outcome == NO_PROGRESS else ""
            )

        return {"investment_debate_state": new_investment_debate_state}

    return bear_node


def _is_eligible_pair(new_count: int) -> bool:
    """A completed pair that sits between round two and the configured cap."""
    if new_count % 2 != 0:
        return False
    cap = int(get_config().get("max_debate_rounds", 1))
    return 4 <= new_count < 2 * cap


def _latest_bull_turn(bull_history: str) -> str:
    """The most recent bull turn from the accumulated bull history."""
    lines = [line for line in (bull_history or "").splitlines() if line.strip()]
    return lines[-1] if lines else ""
