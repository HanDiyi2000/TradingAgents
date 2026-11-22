from tradingagents.agents.debate_progress import NO_PROGRESS
from tradingagents.agents.state import AgentState


class ConditionalLogic:
    """Handles conditional logic for determining graph flow."""

    def __init__(self, max_debate_rounds=1, max_risk_discuss_rounds=1):
        """Initialize with configuration parameters."""
        self.max_debate_rounds = max_debate_rounds
        self.max_risk_discuss_rounds = max_risk_discuss_rounds

    def should_continue_debate(self, state: AgentState) -> str:
        """Determine if debate should continue.

        The round cap is checked first and always wins. The opening round always
        lets both researchers speak. From round two, a completed pair whose
        persisted judgement (written by the bear node) is NO_PROGRESS for this
        round ends the debate; the router never re-judges.
        """
        debate = state["investment_debate_state"]
        count = debate["count"]

        # Cap takes priority over any progress verdict.
        if count >= 2 * self.max_debate_rounds:
            return "Research Manager"

        bull_spoke = debate.get("current_response", "").startswith("Bull")

        # An incomplete round gives the other side its turn (order preserved).
        if count % 2 != 0:
            return "Bear Researcher" if bull_spoke else "Bull Researcher"
        if bull_spoke:
            return "Bear Researcher"

        # Completed pair: stop only on a confirmed NO_PROGRESS for this round.
        if (
            debate.get("progress_outcome") == NO_PROGRESS
            and debate.get("progress_round") == count // 2
        ):
            return "Research Manager"

        return "Bull Researcher"

    def should_continue_risk_analysis(self, state: AgentState) -> str:
        """Determine if risk analysis should continue."""
        if (
            state["risk_debate_state"]["count"] >= 3 * self.max_risk_discuss_rounds
        ):  # max_risk_discuss_rounds turns each for the three risk analysts
            return "Portfolio Manager"
        if state["risk_debate_state"]["latest_speaker"].startswith("Aggressive"):
            return "Conservative Analyst"
        if state["risk_debate_state"]["latest_speaker"].startswith("Conservative"):
            return "Neutral Analyst"
        return "Aggressive Analyst"
