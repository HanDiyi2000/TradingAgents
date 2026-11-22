from tradingagents.agents.citations import (
    build_report_paragraphs,
    render_annotated_turn,
    render_for_prompt,
    reports_from_state,
    resolve_turn,
)
from tradingagents.agents.context import (
    get_instrument_context_from_state,
    get_language_instruction,
    opponent_argument_or_opening,
    report_or_absent,
)


def create_bull_researcher(llm):
    def bull_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bull_history = investment_debate_state.get("bull_history", "")

        current_response = opponent_argument_or_opening(
            investment_debate_state.get("current_response", ""), "bear analyst"
        )
        # FEAT-05: number the reports before the model is called, once per run.
        paragraphs = investment_debate_state.get("report_paragraphs")
        if paragraphs is None:
            paragraphs = build_report_paragraphs(reports_from_state(state))
        reports = render_for_prompt(state, paragraphs)
        market_research_report = report_or_absent(reports["market_report"], "market")
        sentiment_report = report_or_absent(reports["sentiment_report"], "sentiment")
        news_report = report_or_absent(reports["news_report"], "news")
        fundamentals_report = report_or_absent(reports["fundamentals_report"], "fundamentals")
        options_report = report_or_absent(reports["options_report"], "options")
        instrument_context = get_instrument_context_from_state(state)
        asset_type = state.get("asset_type", "stock")
        target_label = "stock" if asset_type == "stock" else "asset"
        fundamentals_label = (
            "Company fundamentals report"
            if asset_type == "stock"
            else "Asset fundamentals report (may be unavailable for crypto)"
        )

        prompt = f"""You are a Bull Analyst advocating for investing in the {target_label}. Your task is to build a strong, evidence-based case emphasizing growth potential, competitive advantages, and positive market indicators. Leverage the provided research and data to address concerns and counter bearish arguments effectively.

Key points to focus on:
- Growth Potential: Highlight the company's market opportunities, revenue projections, and scalability.
- Competitive Advantages: Emphasize factors like unique products, strong branding, or dominant market positioning.
- Positive Indicators: Use financial health, industry trends, and recent positive news as evidence.
- Bear Counterpoints: Critically analyze the bear argument with specific data and sound reasoning, addressing concerns thoroughly and showing why the bull perspective holds stronger merit.
- Engagement: Present your argument in a conversational style, engaging directly with the bear analyst's points and debating effectively rather than just listing data.
- Evidence pointing: Each report paragraph below is labelled with a source ID in square brackets (three letters, a hyphen, two or more digits — the same form as the report prefixes, e.g. MKT, SEN, NWS, FUN, OPT). When an argument rests on a report, cite that paragraph's ID in square brackets beside the argument it supports. A claim that no supplied report supports should not take a report citation; do not invent an ID.

Resources available:
{instrument_context}
Market research report: {market_research_report}
Social media sentiment report: {sentiment_report}
Latest world affairs news: {news_report}
{fundamentals_label}: {fundamentals_report}
Options market report: {options_report}
Conversation history of the debate: {history}
Last bear argument: {current_response}
Use this information to deliver a compelling bull argument, refute the bear's concerns, and engage in a dynamic debate that demonstrates the strengths of the bull position.
""" + get_language_instruction()

        response = llm.invoke(prompt)

        # FEAT-05: annotate against this run's map; the record keeps the raw text.
        # Each speaker numbers its own utterances, so the bull's first turn is 1
        # and the bear's first turn is also 1, independently.
        turn_number = 1 + sum(1 for e in investment_debate_state.get("turn_citations", [])
                              if e.get("speaker") == "bull")
        entry = resolve_turn("bull", turn_number, response.content, paragraphs)
        argument = "Bull Analyst: " + render_annotated_turn(entry)

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bull_history": bull_history + "\n" + argument,
            "bear_history": investment_debate_state.get("bear_history", ""),
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
            "report_paragraphs": paragraphs,
            "turn_citations": [*investment_debate_state.get("turn_citations", []), entry],
            # FEAT-02: carry the persisted progress decision; only the bear node
            # judges a pair, so it must survive the bull's rewrite.
            "progress_outcome": investment_debate_state.get("progress_outcome", ""),
            "progress_round": investment_debate_state.get("progress_round", 0),
            "progress_reason": investment_debate_state.get("progress_reason", ""),
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bull_node
