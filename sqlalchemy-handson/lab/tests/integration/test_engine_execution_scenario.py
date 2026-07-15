import pytest
from sqlalchemy import Engine

from scenarios.ch01_engine_execution import run

pytestmark = pytest.mark.integration


def test_execute_path_observes_checkout_before_cursor_execution(engine: Engine) -> None:
    evidence = run(engine)
    observations = "\n".join(evidence.observation)

    assert "event_order=checkout->before_cursor_execute" in observations
    assert "checkout_during_connect=True" in observations
    assert "sql_not_executed_at_checkout=True" in observations
    assert "result=42" in observations
    assert "dialect=postgresql" in observations
    assert "driver=psycopg" in observations


def test_engine_scenario_executes_naive_and_corrected_lifecycle_contrast(
    engine: Engine,
) -> None:
    observations = "\n".join(run(engine).observation)

    assert "naive_distinct_pools=True" in observations
    assert "corrected_reused_pool=True" in observations
