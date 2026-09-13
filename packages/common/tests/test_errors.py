import pytest
from common.errors import (
    ConfigError,
    ExternalServiceError,
    NotFoundError,
    WardenError,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("error_type", "code"),
    [
        (ConfigError, "config_error"),
        (NotFoundError, "not_found"),
        (ExternalServiceError, "external_service_error"),
    ],
)
def test_error_types_have_stable_codes(
    error_type: type[WardenError], code: str
) -> None:
    error = error_type("message")

    assert isinstance(error, WardenError)
    assert error.code == code
    assert str(error) == "message"
