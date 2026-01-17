# Copyright 2026 HoneyAgent Contributors
# SPDX-License-Identifier: Apache-2.0
"""Provider factory with graceful fallbacks.

The ProviderFactory creates provider instances based on configuration,
automatically falling back to mock implementations when optional
dependencies are not installed.

Example:
    from backend.core.factory import ProviderFactory

    # From config file
    config = yaml.safe_load(open("config/providers.yaml"))

    # Create providers (falls back to mock if deps missing)
    identity = ProviderFactory.create_identity_provider(config["identity"])
    vectors = ProviderFactory.create_vector_store(config["vector_store"])
    images = ProviderFactory.create_image_generator(config["image_generator"])
    llm = ProviderFactory.create_llm_provider(config["llm"])
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .protocols import (
        IdentityProvider,
        VectorStore,
        ImageGenerator,
        LLMProvider,
        CredentialGenerator,
    )

logger = logging.getLogger(__name__)


class ProviderFactory:
    """Factory for creating providers with graceful fallbacks.

    All create_* methods follow the same pattern:
    1. Check config for provider type
    2. Attempt to import and instantiate the provider
    3. On ImportError, log warning and fall back to mock
    4. Return provider instance

    This ensures HoneyAgent works out-of-the-box with zero configuration.
    """

    @staticmethod
    def create_identity_provider(config: dict) -> "IdentityProvider":
        """Create identity provider based on config.

        Args:
            config: Dict with "type" key ("auth0" or "mock") and
                    provider-specific configuration.

        Returns:
            IdentityProvider instance.

        Supported types:
            - "auth0": Requires `pip install honeyagent[auth0]`
            - "mock": Always available (default)
        """
        provider_type = config.get("type", "mock")

        if provider_type == "auth0":
            try:
                from backend.providers.auth0 import Auth0Provider

                auth0_config = config.get("auth0", {})
                logger.info("Using Auth0 identity provider")
                return Auth0Provider(**auth0_config)
            except ImportError:
                logger.warning(
                    "Auth0 provider unavailable. "
                    "Install with: pip install honeyagent[auth0]"
                )
                logger.info("Falling back to mock identity provider")

        # Default to mock
        from backend.providers.mock import MockIdentityProvider

        mock_config = config.get("mock", {})
        return MockIdentityProvider(**mock_config)

    @staticmethod
    def create_vector_store(config: dict) -> "VectorStore":
        """Create vector store based on config.

        Args:
            config: Dict with "type" key ("s3" or "mock") and
                    provider-specific configuration.

        Returns:
            VectorStore instance.

        Supported types:
            - "s3": Requires `pip install honeyagent[aws]`
            - "mock": Always available (default)
        """
        provider_type = config.get("type", "mock")

        if provider_type == "s3":
            try:
                from backend.providers.aws import S3VectorStore

                s3_config = config.get("s3", {})
                logger.info("Using S3 vector store")
                return S3VectorStore(**s3_config)
            except ImportError:
                logger.warning(
                    "S3 vector store unavailable. "
                    "Install with: pip install honeyagent[aws]"
                )

        from backend.providers.mock import MockVectorStore

        return MockVectorStore()

    @staticmethod
    def create_image_generator(config: dict) -> "ImageGenerator":
        """Create image generator based on config.

        Args:
            config: Dict with "type" key ("freepik" or "mock") and
                    provider-specific configuration.

        Returns:
            ImageGenerator instance.

        Supported types:
            - "freepik": Requires `pip install honeyagent[freepik]`
            - "mock": Always available (default)
        """
        provider_type = config.get("type", "mock")

        if provider_type == "freepik":
            try:
                from backend.providers.freepik import FreepikGenerator

                freepik_config = config.get("freepik", {})
                logger.info("Using Freepik image generator")
                return FreepikGenerator(**freepik_config)
            except ImportError:
                logger.warning(
                    "Freepik generator unavailable. "
                    "Install with: pip install honeyagent[freepik]"
                )

        from backend.providers.mock import MockImageGenerator

        return MockImageGenerator()

    @staticmethod
    def create_llm_provider(config: dict) -> "LLMProvider":
        """Create LLM provider based on config.

        Args:
            config: Dict with "type" key ("bedrock" or "mock") and
                    provider-specific configuration.

        Returns:
            LLMProvider instance.

        Supported types:
            - "bedrock": Requires `pip install honeyagent[aws]`
            - "mock": Always available (default)
        """
        provider_type = config.get("type", "mock")

        if provider_type == "bedrock":
            try:
                from backend.providers.aws import BedrockProvider

                bedrock_config = config.get("bedrock", {})
                logger.info("Using Bedrock LLM provider")
                return BedrockProvider(**bedrock_config)
            except ImportError:
                logger.warning(
                    "Bedrock provider unavailable. "
                    "Install with: pip install honeyagent[aws]"
                )

        from backend.providers.mock import MockLLMProvider

        return MockLLMProvider()

    @staticmethod
    def create_credential_generator(config: dict) -> "CredentialGenerator":
        """Create credential generator based on config.

        Args:
            config: Dict with "type" key ("tonic" or "mock") and
                    provider-specific configuration.

        Returns:
            CredentialGenerator instance.

        Supported types:
            - "tonic": Requires Tonic Fabricate API key
            - "mock": Always available (default)
        """
        provider_type = config.get("type", "mock")

        if provider_type == "tonic":
            try:
                from backend.providers.tonic import TonicGenerator

                tonic_config = config.get("tonic", {})
                logger.info("Using Tonic credential generator")
                return TonicGenerator(**tonic_config)
            except ImportError:
                logger.warning(
                    "Tonic generator unavailable. "
                    "Install with: pip install honeyagent[tonic]"
                )

        from backend.providers.mock import MockCredentialGenerator

        return MockCredentialGenerator()


# Convenience functions for quick access
def get_identity_provider(config: dict) -> "IdentityProvider":
    """Shorthand for ProviderFactory.create_identity_provider."""
    return ProviderFactory.create_identity_provider(config)


def get_vector_store(config: dict) -> "VectorStore":
    """Shorthand for ProviderFactory.create_vector_store."""
    return ProviderFactory.create_vector_store(config)


def get_image_generator(config: dict) -> "ImageGenerator":
    """Shorthand for ProviderFactory.create_image_generator."""
    return ProviderFactory.create_image_generator(config)


def get_llm_provider(config: dict) -> "LLMProvider":
    """Shorthand for ProviderFactory.create_llm_provider."""
    return ProviderFactory.create_llm_provider(config)


def get_credential_generator(config: dict) -> "CredentialGenerator":
    """Shorthand for ProviderFactory.create_credential_generator."""
    return ProviderFactory.create_credential_generator(config)
