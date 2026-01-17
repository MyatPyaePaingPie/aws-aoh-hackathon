# Copyright 2026 HoneyAgent Contributors
# SPDX-License-Identifier: Apache-2.0
"""Provider implementations for HoneyAgent.

This package contains implementations of the core protocols defined in
honeyagent.core.protocols. Providers are loaded dynamically based on
configuration and available dependencies.

Available providers:
- mock: Always available, zero dependencies (default)
- auth0: Requires `pip install honeyagent[auth0]`
- aws: Requires `pip install honeyagent[aws]`
- freepik: Requires `pip install honeyagent[freepik]`

Use ProviderFactory to create instances:

    from honeyagent.core.factory import ProviderFactory

    identity = ProviderFactory.create_identity_provider(config)
    vectors = ProviderFactory.create_vector_store(config)
"""

from .mock import (
    MockIdentityProvider,
    MockVectorStore,
    MockImageGenerator,
    MockLLMProvider,
    MockCredentialGenerator,
)

__all__ = [
    "MockIdentityProvider",
    "MockVectorStore",
    "MockImageGenerator",
    "MockLLMProvider",
    "MockCredentialGenerator",
]
