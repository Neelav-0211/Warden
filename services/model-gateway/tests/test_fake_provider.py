import pytest
from contract_test_model_provider import ModelProviderContract
from model_gateway.core.fake import FakeModelProvider
from model_gateway.core.types import Capabilities, EmbedRequest, GenerateRequest

pytestmark = pytest.mark.unit


def _configured_fake_provider() -> FakeModelProvider:
    return FakeModelProvider(
        capabilities=Capabilities(
            supports_prompt_caching=True,
            supports_parallel_tool_calls=True,
            max_context_tokens=8192,
            supports_streaming=True,
            supports_embeddings=True,
        ),
        responses={"hello": "hello back", "stream this": "one two three"},
        tool_calls={"lookup": {"query": "weather"}},
    )


@pytest.fixture
def fake_provider() -> FakeModelProvider:
    return _configured_fake_provider()


class TestFakeModelProvider(ModelProviderContract):
    @pytest.fixture
    def model_provider(self) -> FakeModelProvider:
        return _configured_fake_provider()


@pytest.mark.asyncio
async def test_fake_provider_returns_scripted_response(
    fake_provider: FakeModelProvider,
) -> None:
    response = await fake_provider.generate(
        GenerateRequest(prompt="hello", max_tokens=16)
    )

    assert response.content == "hello back"


@pytest.mark.asyncio
async def test_fake_provider_respects_max_tokens() -> None:
    provider = FakeModelProvider(responses={"prompt": "one two three"})

    response = await provider.generate(GenerateRequest(prompt="prompt", max_tokens=2))

    assert response.content.split() == ["one", "two"]


@pytest.mark.asyncio
async def test_fake_embeddings_are_deterministic() -> None:
    provider = FakeModelProvider()
    request = EmbedRequest(texts=["alpha", "beta"])

    first = await provider.embed(request)
    second = await provider.embed(request)

    assert first == second
    assert len(first.embeddings) == len(request.texts)
    assert all(vector for vector in first.embeddings)
