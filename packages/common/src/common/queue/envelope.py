from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue


class JobEnvelope(BaseModel):
    """Backend-independent JSON wire format; attempts start at one."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    job_id: str = Field(min_length=1)
    job_type: str = Field(min_length=1)
    payload: dict[str, JsonValue]
    enqueued_at: AwareDatetime
    attempt: int = Field(default=1, ge=1, strict=True)
