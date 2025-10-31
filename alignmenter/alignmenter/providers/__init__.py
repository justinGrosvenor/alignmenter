"""Provider adapter scaffolds."""

from .openai import OpenAIProvider
from .anthropic import AnthropicProvider
from .local import LocalProvider

__all__ = ["OpenAIProvider", "AnthropicProvider", "LocalProvider"]
