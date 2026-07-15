import pytest

from order_service.db.settings import DatabaseSettings
from scenarios.ch06_pooling_capacity import observe_pool_exhaustion, run

pytestmark = pytest.mark.integration


def test_third_checkout_times_out_when_two_slots_are_held() -> None:
    observed = observe_pool_exhaustion(DatabaseSettings.from_env())

    assert 0.15 <= observed.waited_seconds < 0.8
    assert "QueuePool limit of size 2 overflow 0 reached" in observed.error_message
    assert observed.checked_out_at_timeout == 2


def test_pool_scenario_records_capacity_and_timeout() -> None:
    observations = "\n".join(run(DatabaseSettings.from_env()).observation)
    assert "configured_hard_limit=2" in observations
    assert "checked_out_at_timeout=2" in observations
    assert "timeout_class=sqlalchemy.exc.TimeoutError" in observations
    assert "naive_checkout_timed_out=True" in observations
    assert "corrected_pool_recovered=True" in observations
    assert "timeout_within_expected_bound=True" in observations
    assert "waited_seconds=" not in observations


def test_timeout_emits_no_checkout_event_and_pool_recovers() -> None:
    observed = observe_pool_exhaustion(DatabaseSettings.from_env())

    assert observed.event_names[:3] == ("checkout", "checkout", "timeout")
    assert observed.event_names[-3:] == ("checkout", "reset", "checkin")
    assert observed.event_names.count("checkout") == 3
    assert observed.checked_out_after_recovery == 0
