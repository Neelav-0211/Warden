import json
from collections.abc import MutableMapping
from typing import Any

import pytest
from common.logging import bind_context, get_logger
from structlog.contextvars import clear_contextvars, merge_contextvars
from structlog.testing import capture_logs


@pytest.fixture(autouse=True)
def _clear_log_context() -> None:
    clear_contextvars()


@pytest.mark.unit
def test_get_logger_emits_json_outside_local_environment(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    logger = get_logger("test")

    logger.info("ready", job_id="job-1")

    record = json.loads(capsys.readouterr().out)
    assert record["event"] == "ready"
    assert record["job_id"] == "job-1"
    assert record["logger"] == "test"


@pytest.mark.unit
def test_bind_context_adds_values_to_subsequent_records() -> None:
    logger = get_logger("test")
    bind_context(task_id="task-1", request_id="request-1")

    with capture_logs(processors=[merge_contextvars]) as records:
        logger.info("started")

    record: MutableMapping[str, Any] = records[0]
    assert record["task_id"] == "task-1"
    assert record["request_id"] == "request-1"
