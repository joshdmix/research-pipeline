"""Base agent class: manages the Anthropic API tool-use loop."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import anthropic
import structlog

from research_pipeline.agent.tools import TOOL_DEFINITIONS, execute_tool
from research_pipeline.budget import Budget

log = structlog.get_logger()

MAX_TURNS = 25


class Agent:
    """A stateless agent that runs a tool-use conversation with Claude."""

    def __init__(
        self,
        model: str,
        system_prompt: str,
        budget: Budget,
        work_dir: Path,
        tools: list[dict] | None = None,
    ):
        self.client = anthropic.Anthropic()
        self.model = model
        self.system_prompt = system_prompt
        self.budget = budget
        self.work_dir = work_dir
        self.tools = tools or TOOL_DEFINITIONS
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def run(self, user_message: str) -> AgentResult:
        """Run the agent with a user message, executing tools until done."""
        messages = [{"role": "user", "content": user_message}]

        for turn in range(MAX_TURNS):
            if self.budget.exhausted:
                log.warning("agent_budget_exhausted", turn=turn)
                return AgentResult(
                    success=False,
                    summary="Budget exhausted",
                    data={},
                    tool_calls=[],
                )

            response = self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                system=self.system_prompt,
                messages=messages,
                tools=self.tools,
            )

            self.budget.record_usage(
                response.usage.input_tokens,
                response.usage.output_tokens,
            )

            if response.stop_reason == "end_turn":
                text = _extract_text(response)
                return AgentResult(
                    success=True,
                    summary=text,
                    data={},
                    tool_calls=[],
                )

            if response.stop_reason != "tool_use":
                text = _extract_text(response)
                return AgentResult(success=True, summary=text, data={}, tool_calls=[])

            # Process tool calls
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            result_data = {}

            for block in response.content:
                if block.type != "tool_use":
                    continue

                log.info("agent_tool_call", tool=block.name, id=block.id)

                # Capture report_analysis/report_result data
                if block.name in ("report_analysis", "report_result"):
                    result_data = block.input.get("analysis", block.input)

                tool_output = execute_tool(block.name, block.input, self.work_dir)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": tool_output,
                    }
                )

            messages.append({"role": "user", "content": tool_results})

            # If we got a report, we can return
            if result_data:
                success = result_data.get("success", True)
                summary = result_data.get("summary", "")
                return AgentResult(
                    success=success,
                    summary=summary,
                    data=result_data,
                    tool_calls=[],
                )

        log.warning("agent_max_turns_reached")
        return AgentResult(
            success=False,
            summary="Max turns reached",
            data={},
            tool_calls=[],
        )


class AgentResult:
    """Result from an agent run."""

    def __init__(
        self,
        success: bool,
        summary: str,
        data: dict[str, Any],
        tool_calls: list[dict],
    ):
        self.success = success
        self.summary = summary
        self.data = data
        self.tool_calls = tool_calls


def _extract_text(response) -> str:
    """Extract text content from a response."""
    parts = []
    for block in response.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "\n".join(parts)
