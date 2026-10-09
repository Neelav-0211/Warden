from collections.abc import Mapping

from model_gateway.core.errors import NoCapableProviderError
from model_gateway.core.interface import ModelProvider
from model_gateway.core.types import Capabilities


class ModelGatewayRouter:
    """Select the first configured provider satisfying required capabilities."""

    def __init__(self, providers: Mapping[str, ModelProvider]) -> None:
        self._providers = dict(providers)

    def select(self, requirements: Capabilities) -> ModelProvider:
        for provider in self._providers.values():
            available = provider.capabilities()
            if self._satisfies(available, requirements):
                return provider

        raise NoCapableProviderError(
            "No model provider satisfies the requested capabilities "
            f"{requirements.model_dump()}"
        )

    @staticmethod
    def _satisfies(available: Capabilities, required: Capabilities) -> bool:
        return (
            (not required.supports_prompt_caching or available.supports_prompt_caching)
            and (
                not required.supports_parallel_tool_calls
                or available.supports_parallel_tool_calls
            )
            and available.max_context_tokens >= required.max_context_tokens
            and (not required.supports_streaming or available.supports_streaming)
            and (not required.supports_embeddings or available.supports_embeddings)
        )
