import pytest
from model_gateway.core.errors import NoCapableProviderError
from model_gateway.core.fake import FakeModelProvider
from model_gateway.core.router import ModelGatewayRouter
from model_gateway.core.types import Capabilities

pytestmark = pytest.mark.unit


def _capabilities(**overrides: bool | int) -> Capabilities:
    values: dict[str, bool | int] = {
        "supports_prompt_caching": False,
        "supports_parallel_tool_calls": False,
        "max_context_tokens": 1024,
        "supports_streaming": False,
        "supports_embeddings": False,
    }
    values.update(overrides)
    return Capabilities(**values)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("supports_prompt_caching", True),
        ("supports_parallel_tool_calls", True),
        ("max_context_tokens", 2048),
        ("supports_streaming", True),
        ("supports_embeddings", True),
    ],
)
def test_select_checks_each_capability(field: str, value: bool | int) -> None:
    limited = FakeModelProvider(capabilities=_capabilities())
    full = FakeModelProvider(
        capabilities=_capabilities(**{field: value, "max_context_tokens": 4096})
    )
    requirements = _capabilities(**{field: value})
    router = ModelGatewayRouter({"limited": limited, "full": full})

    assert router.select(requirements) is full


def test_select_returns_first_suitable_provider() -> None:
    first = FakeModelProvider(capabilities=_capabilities())
    second = FakeModelProvider(capabilities=_capabilities())
    router = ModelGatewayRouter({"first": first, "second": second})

    assert router.select(_capabilities()) is first


def test_select_raises_typed_error_when_no_provider_matches() -> None:
    router = ModelGatewayRouter(
        {"limited": FakeModelProvider(capabilities=_capabilities())}
    )

    with pytest.raises(NoCapableProviderError, match="No model provider"):
        router.select(_capabilities(supports_embeddings=True))
