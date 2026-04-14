import pytest

from aegis.core.budget import (
    Budget,
    BudgetExhausted,
    BudgetTracker,
    MODEL_PRICES,
)


def test_record_llm_call_accumulates_cost() -> None:
    tracker = BudgetTracker(Budget(usd_cap=10.0, seconds_cap=600))
    tracker.record_llm_call("claude-sonnet-4-6", input_tokens=1_000_000, output_tokens=0)
    assert tracker.state.usd_spent == pytest.approx(MODEL_PRICES["claude-sonnet-4-6"]["input"])

    tracker.record_llm_call("claude-sonnet-4-6", input_tokens=0, output_tokens=1_000_000)
    expected = (
        MODEL_PRICES["claude-sonnet-4-6"]["input"]
        + MODEL_PRICES["claude-sonnet-4-6"]["output"]
    )
    assert tracker.state.usd_spent == pytest.approx(expected)
    assert tracker.state.input_tokens == 1_000_000
    assert tracker.state.output_tokens == 1_000_000


def test_record_llm_call_unknown_model_raises() -> None:
    tracker = BudgetTracker(Budget(usd_cap=1.0, seconds_cap=60))
    with pytest.raises(ValueError):
        tracker.record_llm_call("gpt-9", input_tokens=100, output_tokens=100)


def test_exhausted_on_usd_cap() -> None:
    tracker = BudgetTracker(Budget(usd_cap=0.50, seconds_cap=600))
    tracker.record_llm_call("claude-opus-4-6", input_tokens=100_000, output_tokens=0)
    exhausted, reason = tracker.exhausted()
    assert exhausted
    assert reason is not None
    assert "USD" in reason


def test_exhausted_on_wallclock(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_time = [1000.0]

    def fake_monotonic() -> float:
        return fake_time[0]

    monkeypatch.setattr("aegis.core.budget.monotonic", fake_monotonic)
    tracker = BudgetTracker(Budget(usd_cap=10.0, seconds_cap=60))
    # After __post_init__, tracker._start == 1000.0 via the patched clock.
    assert tracker._start == 1000.0

    fake_time[0] = 1030.0  # +30s elapsed
    exhausted, reason = tracker.exhausted()
    assert exhausted is False

    fake_time[0] = 1061.0  # +61s elapsed, over cap
    exhausted, reason = tracker.exhausted()
    assert exhausted
    assert reason is not None
    assert "Wallclock" in reason


def test_remaining_values() -> None:
    tracker = BudgetTracker(Budget(usd_cap=5.0, seconds_cap=600))
    tracker.record_llm_call("claude-haiku-4-5", input_tokens=1_000_000, output_tokens=0)
    remaining = tracker.remaining()
    assert remaining["usd"] < 5.0
    assert remaining["seconds"] > 0


def test_raise_if_exhausted() -> None:
    tracker = BudgetTracker(Budget(usd_cap=0.001, seconds_cap=600))
    tracker.record_llm_call("claude-opus-4-6", input_tokens=1_000, output_tokens=0)
    with pytest.raises(BudgetExhausted):
        tracker.raise_if_exhausted()
