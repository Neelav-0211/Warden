import pytest
from common.types import JobStatus, TaskStatus


@pytest.mark.unit
def test_task_status_values_are_stable() -> None:
    assert {status.value for status in TaskStatus} == {
        "pending",
        "running",
        "completed",
        "failed",
        "cancelled",
    }


@pytest.mark.unit
def test_job_status_values_are_stable() -> None:
    assert {status.value for status in JobStatus} == {
        "queued",
        "running",
        "completed",
        "failed",
        "cancelled",
    }
