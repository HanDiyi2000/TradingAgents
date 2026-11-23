"""FEAT-06: one interpretation of a run's stream, shared by the CLI and the web.

``run_analysis`` and the web runner both consume ``graph.stream_run()``. The
CLI paints the terminal; the web repaints a page. What counts as an event — a
message, a tool call, an agent status change, a report section, a debate or risk
update — must mean the same thing in both, so it is decided here once.

The buffer is mutated exactly as the CLI always did; callers observe the changes
however they display them (the terminal's live layout, the web's event log).
"""

from __future__ import annotations

from cli.display import (
    classify_message_type,
    update_analyst_statuses,
    update_research_team_status,
)


def interpret_messages(messages, buffer) -> None:
    """Fold a stream step's messages into the buffer, dropping repeats.

    Returns nothing; the buffer's messages and tool_calls accumulate the run's
    user-visible activity.
    """
    for message in messages:
        msg_id = getattr(message, "id", None)
        if msg_id is not None:
            if msg_id in buffer._processed_message_ids:
                continue
            buffer._processed_message_ids.add(msg_id)

        msg_type, content = classify_message_type(message)
        if content and content.strip():
            buffer.add_message(msg_type, content)

        if getattr(message, "tool_calls", None):
            for tool_call in message.tool_calls:
                if isinstance(tool_call, dict):
                    buffer.add_tool_call(tool_call["name"], tool_call["args"])
                else:
                    buffer.add_tool_call(tool_call.name, tool_call.args)


def interpret_chunk(chunk, buffer, wall_time_tracker=None) -> None:
    """Fold a top-level state chunk into the buffer's statuses and report sections.

    This is the CLI's per-step interpretation, unchanged: analyst statuses, the
    research debate, the trader plan and the risk debate. A ``None`` chunk (a
    step inside an analyst's own graph) carries messages only and is skipped.
    """
    if chunk is None:
        return

    update_analyst_statuses(buffer, chunk, wall_time_tracker=wall_time_tracker)

    # Research Team - Handle Investment Debate State
    if chunk.get("investment_debate_state"):
        debate_state = chunk["investment_debate_state"]
        bull_hist = debate_state.get("bull_history", "").strip()
        bear_hist = debate_state.get("bear_history", "").strip()
        judge = (chunk.get("investment_plan") or "").strip()

        if bull_hist or bear_hist:
            update_research_team_status("in_progress")
        if bull_hist:
            buffer.update_report_section(
                "investment_plan", f"### Bull Researcher Analysis\n{bull_hist}"
            )
        if bear_hist:
            buffer.update_report_section(
                "investment_plan", f"### Bear Researcher Analysis\n{bear_hist}"
            )
        if judge:
            buffer.update_report_section(
                "investment_plan", f"### Research Manager Decision\n{judge}"
            )
            update_research_team_status("completed")
            buffer.update_agent_status("Trader", "in_progress")

    # Trading Team
    if chunk.get("trader_investment_plan"):
        buffer.update_report_section(
            "trader_investment_plan", chunk["trader_investment_plan"]
        )
        if buffer.agent_status.get("Trader") != "completed":
            buffer.update_agent_status("Trader", "completed")
            buffer.update_agent_status("Aggressive Analyst", "in_progress")

    # Risk Management Team - Handle Risk Debate State
    if chunk.get("risk_debate_state"):
        risk_state = chunk["risk_debate_state"]
        agg_hist = risk_state.get("aggressive_history", "").strip()
        con_hist = risk_state.get("conservative_history", "").strip()
        neu_hist = risk_state.get("neutral_history", "").strip()
        judge = (chunk.get("final_trade_decision") or "").strip()

        if agg_hist:
            if buffer.agent_status.get("Aggressive Analyst") != "completed":
                buffer.update_agent_status("Aggressive Analyst", "in_progress")
            buffer.update_report_section(
                "final_trade_decision", f"### Aggressive Analyst Analysis\n{agg_hist}"
            )
        if con_hist:
            if buffer.agent_status.get("Conservative Analyst") != "completed":
                buffer.update_agent_status("Conservative Analyst", "in_progress")
            buffer.update_report_section(
                "final_trade_decision", f"### Conservative Analyst Analysis\n{con_hist}"
            )
        if neu_hist:
            if buffer.agent_status.get("Neutral Analyst") != "completed":
                buffer.update_agent_status("Neutral Analyst", "in_progress")
            buffer.update_report_section(
                "final_trade_decision", f"### Neutral Analyst Analysis\n{neu_hist}"
            )
        if judge and buffer.agent_status.get("Portfolio Manager") != "completed":
            buffer.update_agent_status("Portfolio Manager", "in_progress")
            buffer.update_report_section(
                "final_trade_decision", f"### Portfolio Manager Decision\n{judge}"
            )
            buffer.update_agent_status("Aggressive Analyst", "completed")
            buffer.update_agent_status("Conservative Analyst", "completed")
            buffer.update_agent_status("Neutral Analyst", "completed")
            buffer.update_agent_status("Portfolio Manager", "completed")


def merge_trace(trace) -> dict:
    """Merge per-node stream deltas into the run's final state, as the CLI does."""
    final_state = {}
    for chunk in trace:
        final_state.update(chunk)
    return final_state
