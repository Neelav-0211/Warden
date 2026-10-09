from collections.abc import AsyncIterator, Mapping
from copy import deepcopy
from hashlib import sha256
from typing import Any

from jsonschema import validate

from model_gateway.core.types import (
    Capabilities,
    EmbedRequest,
    EmbedResponse,
    GenerateChunk,
    GenerateRequest,
    GenerateResponse,
    ToolCallRequest,
    ToolCallResponse,
)


class FakeModelProvider:
    """Deterministic in-memory provider for tests and local development."""

    def __init__(
        self,
        *,
        capabilities: Capabilities | None = None,
        responses: Mapping[str, str] | None = None,
        tool_calls: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        self._capabilities = capabilities or Capabilities(
            supports_prompt_caching=True,
            supports_parallel_tool_calls=True,
            max_context_tokens=8192,
            supports_streaming=True,
            supports_embeddings=True,
        )
        self._responses = dict(responses or {})
        self._tool_calls = deepcopy(dict(tool_calls or {}))

    async def generate(self, req: GenerateRequest) -> GenerateResponse:
        content = self._responses.get(req.prompt, f"Fake response: {req.prompt}")
        tokens = content.split()
        if len(tokens) > req.max_tokens:
            content = " ".join(tokens[: req.max_tokens])
            return GenerateResponse(content=content, finish_reason="length")
        return GenerateResponse(content=content)

    async def stream(self, req: GenerateRequest) -> AsyncIterator[GenerateChunk]:
        response = await self.generate(req)
        chunk_size = 16
        for offset in range(0, len(response.content), chunk_size):
            yield GenerateChunk(content=response.content[offset : offset + chunk_size])

    async def tool_call(self, req: ToolCallRequest) -> ToolCallResponse:
        arguments = deepcopy(self._tool_calls.get(req.name, {}))
        validate(instance=arguments, schema=req.arguments_schema)
        return ToolCallResponse(name=req.name, arguments=arguments)

    async def embed(self, req: EmbedRequest) -> EmbedResponse:
        embeddings = [
            [byte / 255.0 for byte in sha256(text.encode("utf-8")).digest()]
            for text in req.texts
        ]
        return EmbedResponse(embeddings=embeddings)

    def capabilities(self) -> Capabilities:
        return self._capabilities.model_copy(deep=True)
