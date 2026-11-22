from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.context import get_instrument_context_from_state, get_language_instruction
from tradingagents.agents.structured import NO_EXTERNAL_TOOLS
from tradingagents.dataflows.options import (
    load_eligible_option_chain,
    render_option_chain,
    unavailable_options_notice,
)


def create_options_analyst(llm):
    def options_analyst_node(state):
        ticker = state["company_of_interest"]
        trade_date = state["trade_date"]
        evidence = load_eligible_option_chain(ticker, trade_date)
        if not evidence.usable:
            notice = unavailable_options_notice(ticker, trade_date)
            return {
                "messages": [AIMessage(content=notice)],
                "options_report": notice,
            }

        instrument_context = get_instrument_context_from_state(state)
        evidence_text = render_option_chain(evidence)
        system_message = (
            "You are the Options Analyst. Explain what the eligible stock-option "
            "evidence implies about risk for this stock on the analysis date. "
            "Use only the supplied option-chain observations and deterministic "
            "summary. Do not invent strikes, expiries, quotes, implied "
            "volatilities, open interest, or volume. Do not recommend specific "
            "option contracts or strategies, and do not analyze the underlying "
            "stock's price or volume; the Market Analyst owns that report. "
            "Discuss ATM implied volatility, put/call open-interest and volume "
            "ratios, total open interest and volume, ATM bid-ask spread, term "
            "structure, open-interest concentration, and max pain only where "
            "the supplied evidence supports them. State clearly when a metric "
            "is unavailable. Finish with a Markdown table of the indicators you "
            "interpreted and the evidence behind them."
            + NO_EXTERNAL_TOOLS
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant collaborating with other "
                    "assistants. Today's date is {current_date}; treat it as "
                    "'now'. {instrument_context}\n{system_message}\n\n"
                    "<option_chain_evidence>\n{evidence_text}\n</option_chain_evidence>",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )
        prompt = prompt.partial(
            current_date=trade_date,
            instrument_context=instrument_context,
            system_message=system_message,
            evidence_text=evidence_text,
        )

        formatted_messages = prompt.format_messages(messages=state["messages"])
        result = llm.invoke(formatted_messages)
        report = result.content if isinstance(result.content, str) else str(result.content)
        if not report.strip():
            report = evidence_text
            result = AIMessage(content=report)
        return {
            "messages": [result],
            "options_report": report,
        }

    return options_analyst_node
