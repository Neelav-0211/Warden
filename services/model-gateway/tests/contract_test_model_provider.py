import pytest
from model_gateway.core.interface import ModelProvider
from model_gateway.core.types import GenerateRequest, ToolCallRequest


class ModelProviderContract:
    @pytest.mark.asyncio
    async def test_generate_returns_content(
        self, model_provider: ModelProvider
    ) -> None:
        response = await model_provider.generate(
            GenerateRequest(prompt="hello", max_tokens=16)
        )

        assert response.content

    @pytest.mark.asyncio
    async def test_tool_call_arguments_match_requested_schema(
        self, model_provider: ModelProvider
    ) -> None:
        response = await model_provider.tool_call(
            ToolCallRequest(
                prompt="look up the weather",
                name="lookup",
                arguments_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                    "additionalProperties": False,
                },
            )
        )

        assert response.name == "lookup"
        assert response.arguments == {"query": "weather"}

    def test_capabilities_are_pure(self, model_provider: ModelProvider) -> None:
        assert model_provider.capabilities() == model_provider.capabilities()

    @pytest.mark.asyncio
    async def test_stream_matches_generate_content(
        self, model_provider: ModelProvider
    ) -> None:
        request = GenerateRequest(prompt="stream this", max_tokens=16)
        generated = await model_provider.generate(request)
        chunks = [chunk async for chunk in model_provider.stream(request)]

        assert "".join(chunk.content for chunk in chunks) == generated.content
