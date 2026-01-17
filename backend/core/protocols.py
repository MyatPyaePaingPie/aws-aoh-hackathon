# Copyright 2026 HoneyAgent Contributors
# SPDX-License-Identifier: Apache-2.0
"""Protocol definitions for provider abstraction.

These protocols define the interfaces that all providers must implement,
enabling hot-swappable backends without code changes. Use the ProviderFactory
to instantiate providers based on configuration.

Example:
    from honeyagent.core.factory import ProviderFactory

    config = {"type": "auth0", "auth0": {"domain": "..."}}
    identity = ProviderFactory.create_identity_provider(config)

    result = await identity.verify_token(token)
"""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class IdentityResult:
    """Result of identity verification.

    Attributes:
        valid: Whether the token is valid.
        agent_id: Unique identifier for the agent (if authenticated).
        agent_type: Type of agent - "real", "honeypot", or None.
        is_honeypot: Whether this is a honeypot agent.
        fga_allowed: Whether fine-grained authorization passed.
        metadata: Additional provider-specific metadata.
    """

    valid: bool
    agent_id: str | None = None
    agent_type: str | None = None  # "real" | "honeypot" | None
    is_honeypot: bool = False
    fga_allowed: bool = True
    metadata: dict = field(default_factory=dict)


@runtime_checkable
class IdentityProvider(Protocol):
    """Protocol for identity verification providers.

    Implementations: Auth0Provider, MockIdentityProvider
    Install: pip install honeyagent[auth0] for Auth0
    """

    async def verify_token(self, token: str) -> IdentityResult:
        """Verify authentication token and return identity info.

        Args:
            token: JWT or bearer token to verify.

        Returns:
            IdentityResult with validation details.
        """
        ...

    async def check_authorization(
        self, user_id: str, resource: str, action: str
    ) -> bool:
        """Check fine-grained authorization.

        Args:
            user_id: The user/agent ID to check.
            resource: The resource being accessed.
            action: The action being performed (read, write, execute).

        Returns:
            True if authorized, False otherwise.
        """
        ...


@runtime_checkable
class VectorStore(Protocol):
    """Protocol for vector storage providers.

    Implementations: S3VectorStore, MockVectorStore
    Install: pip install honeyagent[aws] for S3
    """

    async def store(self, vectors: list[float], metadata: dict) -> str:
        """Store vectors with metadata.

        Args:
            vectors: The embedding vectors to store.
            metadata: Associated metadata (fingerprint, timestamp, etc).

        Returns:
            Unique ID for the stored vectors.
        """
        ...

    async def search(
        self, query: list[float], top_k: int = 10
    ) -> list[dict]:
        """Search for similar vectors.

        Args:
            query: Query embedding vector.
            top_k: Number of results to return.

        Returns:
            List of matches with scores and metadata.
        """
        ...


@runtime_checkable
class ImageGenerator(Protocol):
    """Protocol for image generation providers.

    Implementations: FreepikGenerator, MockImageGenerator
    Install: pip install honeyagent[freepik] for Freepik
    """

    async def generate(self, prompt: str) -> bytes:
        """Generate image from prompt.

        Args:
            prompt: Text prompt describing the image.

        Returns:
            Image bytes (PNG format).
        """
        ...


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM providers.

    Implementations: BedrockProvider, MockLLMProvider
    Install: pip install honeyagent[aws] for Bedrock
    """

    async def complete(
        self, prompt: str, system: str | None = None
    ) -> str:
        """Generate text completion.

        Args:
            prompt: User prompt.
            system: Optional system prompt.

        Returns:
            Generated text response.
        """
        ...

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for text.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector (list of floats).
        """
        ...


@runtime_checkable
class CredentialGenerator(Protocol):
    """Protocol for fake credential generation.

    Implementations: TonicGenerator, MockCredentialGenerator
    Install: pip install honeyagent[tonic] for Tonic Fabricate
    """

    async def generate(
        self, credential_type: str, context: dict | None = None
    ) -> dict:
        """Generate fake credential.

        Args:
            credential_type: Type of credential (api_key, password, token).
            context: Optional context for realistic generation.

        Returns:
            Dict with credential value and metadata.
        """
        ...
