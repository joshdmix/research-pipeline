"""Token budget tracking for pipeline runs."""

from __future__ import annotations

from dataclasses import dataclass

import structlog

log = structlog.get_logger()


@dataclass
class Budget:
    max_input_tokens: int = 2_000_000
    max_output_tokens: int = 500_000
    input_tokens_used: int = 0
    output_tokens_used: int = 0

    @property
    def exhausted(self) -> bool:
        return (
            self.input_tokens_used >= self.max_input_tokens
            or self.output_tokens_used >= self.max_output_tokens
        )

    @property
    def input_remaining(self) -> int:
        return max(0, self.max_input_tokens - self.input_tokens_used)

    @property
    def output_remaining(self) -> int:
        return max(0, self.max_output_tokens - self.output_tokens_used)

    def record_usage(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens_used += input_tokens
        self.output_tokens_used += output_tokens
        if self.exhausted:
            log.warning(
                "budget_exhausted",
                input_used=self.input_tokens_used,
                output_used=self.output_tokens_used,
            )

    def summary(self) -> dict:
        return {
            "input_tokens": f"{self.input_tokens_used:,}/{self.max_input_tokens:,}",
            "output_tokens": f"{self.output_tokens_used:,}/{self.max_output_tokens:,}",
            "input_pct": f"{self.input_tokens_used / self.max_input_tokens * 100:.1f}%",
            "output_pct": f"{self.output_tokens_used / self.max_output_tokens * 100:.1f}%",
        }
