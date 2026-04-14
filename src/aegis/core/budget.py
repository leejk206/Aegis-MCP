from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic

# Prices as of 2026 (USD per million tokens). Update manually when
# Anthropic adjusts pricing. Keys match .aegis/config.yaml llm.models
# values.
MODEL_PRICES: dict[str, dict[str, float]] = {
    "claude-opus-4-6":   {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-6": {"input":  3.00, "output": 15.00},
    "claude-haiku-4-5":  {"input":  1.00, "output":  5.00},
}


@dataclass
class Budget:
    usd_cap: float
    seconds_cap: float


@dataclass
class BudgetState:
    usd_spent: float = 0.0
    seconds_elapsed: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


class BudgetExhausted(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class BudgetTracker:
    budget: Budget
    state: BudgetState = field(default_factory=BudgetState)
    _start: float = 0.0

    def __post_init__(self) -> None:
        # Look up monotonic at runtime from the module so monkeypatching
        # in tests takes effect. Don't use field(default_factory=monotonic) —
        # that captures a direct reference at class-eval time and cannot be
        # mocked.
        if self._start == 0.0:
            self._start = monotonic()

    def record_llm_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        price = MODEL_PRICES.get(model)
        if price is None:
            raise ValueError(f"Unknown model for pricing: {model}")
        cost = (input_tokens / 1_000_000) * price["input"]
        cost += (output_tokens / 1_000_000) * price["output"]
        self.state.usd_spent += cost
        self.state.input_tokens += input_tokens
        self.state.output_tokens += output_tokens

    def _tick(self) -> None:
        self.state.seconds_elapsed = monotonic() - self._start

    def exhausted(self) -> tuple[bool, str | None]:
        self._tick()
        if self.state.usd_spent >= self.budget.usd_cap:
            return True, (
                f"USD cap ${self.budget.usd_cap:.2f} exceeded "
                f"(spent ${self.state.usd_spent:.4f})"
            )
        if self.state.seconds_elapsed >= self.budget.seconds_cap:
            return True, (
                f"Wallclock cap {self.budget.seconds_cap:.0f}s exceeded "
                f"(elapsed {self.state.seconds_elapsed:.0f}s)"
            )
        return False, None

    def remaining(self) -> dict[str, float]:
        self._tick()
        return {
            "usd": max(0.0, self.budget.usd_cap - self.state.usd_spent),
            "seconds": max(0.0, self.budget.seconds_cap - self.state.seconds_elapsed),
        }

    def raise_if_exhausted(self) -> None:
        is_exhausted, reason = self.exhausted()
        if is_exhausted:
            assert reason is not None
            raise BudgetExhausted(reason)
