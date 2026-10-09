from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Capabilities(BaseModel):
    """Features and context capacity advertised by a model provider."""

    model_config = ConfigDict(frozen=True)

    supports_prompt_caching: bool = False
    supports_parallel_tool_calls: bool = False
    max_context_tokens: int = Field(default=0, ge=0)
    supports_streaming: bool = False
    supports_embeddings: bool = False


class GenerateRequest(BaseModel):
    """A provider-independent text generation request."""

    prompt: str = Field(min_length=1)
    max_tokens: int = Field(gt=0)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)


class GenerateResponse(BaseModel):
    """Generated text and the reason generation stopped."""

    content: str = Field(min_length=1)
    finish_reason: str = "stop"


class GenerateChunk(BaseModel):
    """One ordered fragment of a streamed generation response."""

    content: str


class ToolCallRequest(BaseModel):
    """A request to produce arguments conforming to a JSON Schema."""

    prompt: str = Field(min_length=1)
    name: str = Field(min_length=1)
    arguments_schema: dict[str, Any]


class ToolCallResponse(BaseModel):
    """A tool name and its structured arguments."""

    name: str = Field(min_length=1)
    arguments: dict[str, Any]


class EmbedRequest(BaseModel):
    """Texts to encode as vectors."""

    texts: list[str] = Field(min_length=1)


class EmbedResponse(BaseModel):
    """One vector for each input text, in the same order."""

    embeddings: list[list[float]] = Field(min_length=1)
