"""Provider-agnostic model gateway contracts and in-memory test adapter."""

from model_gateway.core.errors import NoCapableProviderError
from model_gateway.core.fake import FakeModelProvider
from model_gateway.core.interface import ModelProvider
from model_gateway.core.router import ModelGatewayRouter
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

__all__ = [
    "Capabilities",
    "EmbedRequest",
    "EmbedResponse",
    "FakeModelProvider",
    "GenerateChunk",
    "GenerateRequest",
    "GenerateResponse",
    "ModelGatewayRouter",
    "ModelProvider",
    "NoCapableProviderError",
    "ToolCallRequest",
    "ToolCallResponse",
]
