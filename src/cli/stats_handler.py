import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import LLMResult

from tradingagents.default_config import DEFAULT_TOKEN_WARNING_THRESHOLD

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TokenWarning:
    """FR-TOK-01: exact measured usage when a run first crosses its threshold."""

    total_tokens: int
    threshold: int


class StatsCallbackHandler(BaseCallbackHandler):
    """Callback handler that tracks LLM calls, tool calls, and token usage."""

    def __init__(
        self,
        *,
        warning_threshold: int = DEFAULT_TOKEN_WARNING_THRESHOLD,
        on_token_warning: Callable[[TokenWarning], None] | None = None,
    ) -> None:
        super().__init__()
        if (
            not isinstance(warning_threshold, int)
            or isinstance(warning_threshold, bool)
            or warning_threshold <= 0
        ):
            raise ValueError("warning_threshold must be a positive integer")
        self._lock = threading.Lock()
        self._warning_threshold = warning_threshold
        self._on_token_warning = on_token_warning
        self._token_warning: TokenWarning | None = None
        self.llm_calls = 0
        self.tool_calls = 0
        self.tokens_in = 0
        self.tokens_out = 0

    @property
    def token_warning(self) -> TokenWarning | None:
        """Read the first crossing snapshot, if one has occurred in this run."""
        with self._lock:
            return self._token_warning

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        """Increment LLM call counter when an LLM starts."""
        with self._lock:
            self.llm_calls += 1

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        **kwargs: Any,
    ) -> None:
        """Increment LLM call counter when a chat model starts."""
        with self._lock:
            self.llm_calls += 1

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Extract token usage from LLM response."""
        try:
            generation = response.generations[0][0]
        except (IndexError, TypeError):
            return

        usage_metadata = None
        if hasattr(generation, "message"):
            message = generation.message
            if isinstance(message, AIMessage) and hasattr(message, "usage_metadata"):
                usage_metadata = message.usage_metadata

        if not usage_metadata:
            return

        warning = None
        with self._lock:
            self.tokens_in += usage_metadata.get("input_tokens", 0)
            self.tokens_out += usage_metadata.get("output_tokens", 0)
            total = self.tokens_in + self.tokens_out
            if self._token_warning is None and total > self._warning_threshold:
                warning = self._token_warning = TokenWarning(total, self._warning_threshold)

        # Receivers can inspect stats or forward the event to another thread.
        if warning is not None and self._on_token_warning is not None:
            try:
                self._on_token_warning(warning)
            except Exception:
                logger.exception("Could not deliver the token warning")

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        """Increment tool call counter when a tool starts."""
        with self._lock:
            self.tool_calls += 1

    def get_stats(self) -> dict[str, Any]:
        """Return current statistics."""
        with self._lock:
            return {
                "llm_calls": self.llm_calls,
                "tool_calls": self.tool_calls,
                "tokens_in": self.tokens_in,
                "tokens_out": self.tokens_out,
            }
