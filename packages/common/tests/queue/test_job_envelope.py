from datetime import UTC, datetime

import pytest
from common.queue import JobEnvelope
from pydantic import ValidationError

pytestmark = pytest.mark.unit


def test_job_envelope_round_trip() -> None:
    envelope = JobEnvelope(
        job_id="job-123",
        job_type="review",
        payload={
            "repository": "owner/repo",
            "nested": [None, True, 4, {"key": "value"}],
        },
        enqueued_at=datetime(2026, 9, 14, 12, 30, tzinfo=UTC),
        attempt=1,
    )

    assert JobEnvelope.model_validate_json(envelope.model_dump_json()) == envelope


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("job_id", ""),
        ("job_type", ""),
        ("payload", []),
        ("payload", {"invalid": object()}),
        ("enqueued_at", "not-a-date"),
        ("enqueued_at", datetime(2026, 9, 14)),
        ("attempt", 0),
        ("attempt", -1),
        ("attempt", 1.5),
        ("attempt", True),
    ],
)
def test_job_envelope_rejects_invalid_fields(field: str, value: object) -> None:
    data: dict[str, object] = {
        "job_id": "job-123",
        "job_type": "review",
        "payload": {},
        "enqueued_at": datetime.now(UTC),
        "attempt": 1,
    }
    data[field] = value

    with pytest.raises(ValidationError):
        JobEnvelope.model_validate(data)


@pytest.mark.parametrize("field", ["job_id", "job_type", "payload", "enqueued_at"])
def test_job_envelope_requires_wire_fields(field: str) -> None:
    data: dict[str, object] = {
        "job_id": "job-123",
        "job_type": "review",
        "payload": {},
        "enqueued_at": datetime.now(UTC),
    }
    del data[field]

    with pytest.raises(ValidationError):
        JobEnvelope.model_validate(data)


def test_job_envelope_defaults_to_first_attempt() -> None:
    envelope = JobEnvelope(
        job_id="job-123",
        job_type="review",
        payload={},
        enqueued_at=datetime.now(UTC),
    )

    assert envelope.attempt == 1
