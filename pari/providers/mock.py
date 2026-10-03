"""PARI Providers: Offline / Mock Provider for local testing and dry-runs.

Enables offline testing of the agent loop, tool execution, session recovery,
and diff review without requiring remote cloud API tokens.
"""

from typing import Any, Dict, List, Optional
from pari.providers.base import LLMProvider, ModelResponse, ProviderMessage, ToolCall


class MockOfflineProvider(LLMProvider):
    """Fallback provider when no cloud API keys are configured."""

    def __init__(self, model_name: str = "mock-offline"):
        super().__init__(model_name, api_key="offline")

    async def complete(
        self,
        messages: List[ProviderMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
    ) -> ModelResponse:
        last_user_msg = ""
        for m in reversed(messages):
            if m.role == "user":
                last_user_msg = m.content
                break

        # Check if user message indicates an intent to run a tool
        lower = last_user_msg.lower()
        if "list" in lower or "find" in lower:
            return ModelResponse(
                text="Scanning repository files for requested matches...",
                tool_calls=[ToolCall(id="mock-1", name="find_files", arguments={"pattern": "*"})],
            )
        elif "grep" in lower or "search" in lower:
            return ModelResponse(
                text="Searching codebase for query pattern...",
                tool_calls=[ToolCall(id="mock-2", name="grep_search", arguments={"query": "def "})],
            )

        return ModelResponse(
            text=(
                f"PARI Agent (Offline Mode) received: '{last_user_msg}'\n\n"
                "To connect to frontier models, set your API key:\n"
                "  export ANTHROPIC_API_KEY='sk-ant-...'\n"
                "  export OPENAI_API_KEY='sk-...'\n"
                "  export DEEPSEEK_API_KEY='sk-...' or launch Ollama locally.\n"
                "Type /help for in-session commands (/undo, /diff, /add, /exit)."
            ),
            tokens_in=50,
            tokens_out=60,
        )
