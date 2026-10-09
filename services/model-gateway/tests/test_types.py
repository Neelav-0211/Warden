import pytest
from model_gateway.core.types import (
    EmbedRequest,
    EmbedResponse,
    GenerateRequest,
    GenerateResponse,
    ToolCallRequest,
    ToolCallResponse,
)
from pydantic import ValidationError

pytestmark = pytest.mark.unit


def test_generation_types_validate_and_round_trip() -> None:
    request = GenerateRequest(prompt="review this change", max_tokens=64)
    response = GenerateResponse(content="Looks good.")

    assert GenerateRequest.model_validate(request.model_dump()) == request
    assert GenerateResponse.model_validate(response.model_dump()) == response


def test_generation_request_rejects_non_positive_token_limit() -> None:
    with pytest.raises(ValidationError):
        GenerateRequest(prompt="hello", max_tokens=0)


def test_tool_call_types_preserve_schema_and_arguments() -> None:
    request = ToolCallRequest(
        prompt="look up the weather",
        name="lookup",
        arguments_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
        },
    )
    response = ToolCallResponse(name="lookup", arguments={"query": "weather"})

    assert ToolCallRequest.model_validate(request.model_dump()) == request
    assert ToolCallResponse.model_validate(response.model_dump()) == response


def test_embedding_types_validate_inputs_and_outputs() -> None:
    request = EmbedRequest(texts=["first", "second"])
    response = EmbedResponse(embeddings=[[0.1, 0.2], [0.3, 0.4]])

    assert EmbedRequest.model_validate(request.model_dump()) == request
    assert EmbedResponse.model_validate(response.model_dump()) == response

    with pytest.raises(ValidationError):
        EmbedRequest(texts=[])
