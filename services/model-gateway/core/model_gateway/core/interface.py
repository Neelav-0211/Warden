from collections.abc import AsyncIterator
from typing import Protocol

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


class ModelProvider(Protocol):
    """Async provider contract shared by adapters and downstream services."""

    async def generate(self, req: GenerateRequest) -> GenerateResponse:
        """Generate a response constrained by the request token limit."""
        ...

    def stream(self, req: GenerateRequest) -> AsyncIterator[GenerateChunk]:
        """Stream ordered chunks whose concatenation is the generated content."""
        ...

    async def tool_call(self, req: ToolCallRequest) -> ToolCallResponse:
        """Return structured tool arguments matching the requested schema."""
        ...

    async def embed(self, req: EmbedRequest) -> EmbedResponse:
        """Return one embedding vector for each requested text."""
        ...

    def capabilities(self) -> Capabilities:
        """Return provider capabilities without side effects."""
        ...
