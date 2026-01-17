# Python Packaging Patterns for Multi-Provider Projects

**Research Date**: 2026-01-16
**Focus**: Optional dependencies, provider abstraction, modular architecture for HoneyAgent

---

## Executive Summary

Modern Python packaging enables clean separation of core logic from provider-specific implementations through:

1. **Optional dependencies** (`pip install package[provider]`) for feature-gated installations
2. **Protocol-based abstractions** for provider-agnostic interfaces
3. **Adapter pattern** for encapsulating provider-specific logic
4. **Recursive extras** for composite dependency groups (e.g., `all`, `dev`)

Key insight: Successful multi-provider packages (LangChain, Haystack, LlamaIndex) prioritize **runtime safety** through graceful import failures and clear error messages directing users to install required extras.

---

## 1. Optional Dependencies Pattern

### Modern pyproject.toml Structure

```toml
[project]
name = "honeyagent"
version = "0.1.0"
dependencies = [
    "fastapi>=0.104.0",
    "pydantic>=2.0.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
# Provider-specific extras
auth0 = [
    "authlib>=1.3.0",
    "auth0-python>=4.7.0",
]
aws = [
    "boto3>=1.34.0",
    "aioboto3>=12.3.0",
]
freepik = [
    "httpx>=0.27.0",
    "pillow>=10.2.0",
]

# Composite extras
all = [
    "honeyagent[auth0,aws,freepik]",
]
dev = [
    "honeyagent[all]",
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.1.0",
]

[project.scripts]
honeyagent = "honeyagent.cli:main"
```

### Best Practices

1. **Minimum version constraints**: Use `>=` for minimum tested versions; avoid upper bounds unless incompatibility is known
2. **Recursive extras**: Refer to your own package in extras (e.g., `"honeyagent[auth0,aws]"`) — supported since pip 21.2
3. **Naming convention**: Use hyphens in extra names, not underscores (normalized by pip)
4. **PEP 508 compliance**: All dependency strings must be valid PEP 508 format
5. **Optional vs dependency-groups**:
   - `[project.optional-dependencies]` → published to PyPI for end-user features
   - `[dependency-groups]` → development-only, never published (newer standard)

**Sources:**
- [Python Packaging User Guide - Writing pyproject.toml](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)
- [PyOpenSci - Add Required, Optional Dependencies](https://www.pyopensci.org/python-package-guide/package-structure-code/declare-dependencies.html)
- [Hynek Schlawack - Recursive Optional Dependencies](https://hynek.me/articles/python-recursive-optional-dependencies/)

---

## 2. Provider Abstraction Patterns

### Protocol-Based Abstraction (Recommended)

Python's `Protocol` from `typing` enables structural subtyping without inheritance.

```python
# backend/core/protocols.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class IdentityProvider(Protocol):
    """Protocol for identity verification providers."""

    async def verify_token(self, token: str) -> dict:
        """Verify authentication token.

        Returns:
            dict: {"valid": bool, "user_id": str | None, "metadata": dict}
        """
        ...

    async def check_authorization(self, user_id: str, resource: str, action: str) -> bool:
        """Check fine-grained authorization."""
        ...
```

**Concrete implementation:**

```python
# backend/providers/auth0.py
class Auth0Provider:
    """Auth0 implementation of IdentityProvider protocol."""

    def __init__(self, domain: str, client_id: str):
        try:
            from authlib.integrations.httpx_client import AsyncOAuth2Client
        except ImportError:
            raise ImportError(
                "Auth0Provider requires 'authlib'. "
                "Install with: pip install honeyagent[auth0]"
            )
        self.domain = domain
        self.client_id = client_id

    async def verify_token(self, token: str) -> dict:
        # Implementation
        ...

    async def check_authorization(self, user_id: str, resource: str, action: str) -> bool:
        # Implementation
        ...
```

### Strategy Pattern with Dynamic Loading

```python
# backend/core/provider_factory.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .protocols import IdentityProvider

class ProviderFactory:
    """Factory for loading providers based on available dependencies."""

    @staticmethod
    def create_identity_provider(provider: str, config: dict) -> "IdentityProvider":
        """Create identity provider instance with fallback.

        Args:
            provider: Provider name ("auth0", "mock")
            config: Provider-specific configuration

        Returns:
            IdentityProvider instance

        Raises:
            ImportError: If provider dependencies not installed
        """
        if provider == "auth0":
            try:
                from ..providers.auth0 import Auth0Provider
                return Auth0Provider(**config)
            except ImportError as e:
                raise ImportError(
                    f"Auth0 provider requires additional dependencies. "
                    f"Install with: pip install honeyagent[auth0]"
                ) from e

        elif provider == "mock":
            from ..providers.mock import MockIdentityProvider
            return MockIdentityProvider(**config)

        else:
            raise ValueError(f"Unknown provider: {provider}")
```

### Lazy Import Pattern

```python
# backend/tools/image_generator.py
class ImageGenerator:
    """Lazy-loading image generation tool."""

    def __init__(self):
        self._client = None

    async def generate(self, prompt: str) -> bytes:
        """Generate image with lazy dependency loading."""
        if self._client is None:
            try:
                from ..providers.freepik import FreepikClient
                self._client = FreepikClient()
            except ImportError:
                # Fallback to mock implementation
                from ..providers.mock import MockImageClient
                self._client = MockImageClient()

        return await self._client.generate(prompt)
```

**Sources:**
- [Refactoring Guru - Strategy Pattern in Python](https://refactoring.guru/design-patterns/strategy/python/example)
- [Microsoft ISE - Multi-Provider Strategy for App Configuration](https://devblogs.microsoft.com/ise/multi-provider-strategy-configuration-python/)
- [Python PEP 544 - Protocols](https://peps.python.org/pep-0544/)

---

## 3. Real-World Examples

### LangChain's Approach

**Architecture:**
- **Unified interfaces**: `llms.Model`, `chains.Chain`, `agents.Agent`, `vectorstores.VectorStore`
- **Provider-specific implementations**: `openai.LLM`, `anthropic.LLM`, `pinecone.VectorStore`
- **Hot-swappable backends**: Change providers via configuration without code changes

**Key pattern**: Interface-based design with hidden provider implementations behind common APIs.

**Sources:**
- [Medium - LLM Driven Applications with LangChain Abstraction](https://medium.com/@bijit211987/llm-driven-applications-with-langchain-abstraction-4907a32bdfb0)
- [DigitalOcean - LangChain Framework Explained](https://www.digitalocean.com/community/conceptual-articles/langchain-framework-explained)

### Haystack's Approach

**Architecture:**
- **Modular pipeline**: Components connected in explicit, graph-based workflows
- **Typed reusable components**: `@component` decorator with explicit I/O
- **Technology-agnostic**: Mix and match LLM providers (OpenAI, HuggingFace, Azure), vector databases (Elasticsearch, Qdrant, Weaviate), and embedding models

**Key pattern**: Component-based architecture with clear separation between core logic and provider integrations.

**Sources:**
- [ZenML - Haystack vs LlamaIndex](https://www.zenml.io/blog/haystack-vs-llamaindex)
- [Index.dev - AI Framework Comparison 2026](https://www.index.dev/skill-vs-skill/ai-langchain-vs-llamaindex-vs-haystack)

### LlamaIndex's Approach

**Architecture:**
- **RAG-first toolkit**: Focused on data indexing and grounded retrieval
- **Code-first style**: Lower-level, more flexible approach
- **AgentWorkflow**: New workflow system for composing retrieval and generation

**Key pattern**: Flexibility over convention — developers have freedom in component connections.

---

## 4. Recommended Approach for HoneyAgent

### Package Structure

```
honeyagent/
├── backend/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── protocols.py         # Protocol definitions
│   │   ├── factory.py           # Provider factory
│   │   ├── agents.py            # Agent orchestration
│   │   └── router.py            # Request routing
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── auth0.py             # Optional: requires auth0 extra
│   │   ├── aws.py               # Optional: requires aws extra
│   │   ├── freepik.py           # Optional: requires freepik extra
│   │   └── mock.py              # Always available (no deps)
│   └── tools/
│       ├── __init__.py
│       ├── s3_vector.py         # Optional: requires aws extra
│       └── image_gen.py         # Optional: requires freepik extra
├── config/
│   ├── agents.yaml
│   ├── routing.yaml
│   └── fallbacks.yaml
├── tests/
│   ├── unit/
│   │   ├── test_protocols.py
│   │   ├── test_auth0.py        # Conditional: skip if auth0 not installed
│   │   └── test_aws.py          # Conditional: skip if aws not installed
│   └── integration/
└── pyproject.toml
```

### Implementation Strategy

#### 1. Define Core Protocols

```python
# backend/core/protocols.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class IdentityProvider(Protocol):
    async def verify_token(self, token: str) -> dict: ...
    async def check_authorization(self, user_id: str, resource: str, action: str) -> bool: ...

@runtime_checkable
class VectorStore(Protocol):
    async def store(self, vectors: list[float], metadata: dict) -> str: ...
    async def search(self, query: list[float], top_k: int) -> list[dict]: ...

@runtime_checkable
class ImageGenerator(Protocol):
    async def generate(self, prompt: str) -> bytes: ...
```

#### 2. Provider Factory with Graceful Failures

```python
# backend/core/factory.py
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .protocols import IdentityProvider, VectorStore, ImageGenerator

logger = logging.getLogger(__name__)

class ProviderFactory:
    @staticmethod
    def create_identity_provider(config: dict) -> "IdentityProvider":
        provider_type = config.get("type", "mock")

        if provider_type == "auth0":
            try:
                from ..providers.auth0 import Auth0Provider
                return Auth0Provider(**config)
            except ImportError:
                logger.warning(
                    "Auth0 provider not available. Install with: pip install honeyagent[auth0]"
                )
                logger.info("Falling back to mock identity provider")
                from ..providers.mock import MockIdentityProvider
                return MockIdentityProvider()

        elif provider_type == "mock":
            from ..providers.mock import MockIdentityProvider
            return MockIdentityProvider()

        else:
            raise ValueError(f"Unknown identity provider: {provider_type}")

    @staticmethod
    def create_vector_store(config: dict) -> "VectorStore":
        provider_type = config.get("type", "mock")

        if provider_type == "s3":
            try:
                from ..providers.aws import S3VectorStore
                return S3VectorStore(**config)
            except ImportError:
                logger.warning(
                    "AWS provider not available. Install with: pip install honeyagent[aws]"
                )
                from ..providers.mock import MockVectorStore
                return MockVectorStore()

        elif provider_type == "mock":
            from ..providers.mock import MockVectorStore
            return MockVectorStore()

        else:
            raise ValueError(f"Unknown vector store: {provider_type}")
```

#### 3. Conditional Testing

```python
# tests/unit/test_auth0.py
import pytest

auth0 = pytest.importorskip("authlib", reason="Auth0 extra not installed")

@pytest.mark.auth0
async def test_auth0_token_verification():
    from backend.providers.auth0 import Auth0Provider
    # Test implementation
    ...
```

```toml
# pyproject.toml - Test markers
[tool.pytest.ini_options]
markers = [
    "auth0: tests requiring auth0 extra",
    "aws: tests requiring aws extra",
    "freepik: tests requiring freepik extra",
]
```

#### 4. Environment-Based Configuration

```yaml
# config/providers.yaml
identity:
  type: ${IDENTITY_PROVIDER:mock}  # Defaults to mock if env var not set
  auth0:
    domain: ${AUTH0_DOMAIN}
    client_id: ${AUTH0_CLIENT_ID}

vector_store:
  type: ${VECTOR_STORE:mock}
  s3:
    bucket: ${S3_BUCKET}
    region: ${AWS_REGION:us-east-1}

image_generator:
  type: ${IMAGE_PROVIDER:mock}
  freepik:
    api_key: ${FREEPIK_API_KEY}
```

---

## 5. CLI Entry Points

### Defining Entry Points in pyproject.toml

```toml
[project.scripts]
honeyagent = "honeyagent.cli:main"
honeyagent-server = "honeyagent.server:start"

[project.gui-scripts]
honeyagent-gui = "honeyagent.gui:launch"  # Launches without terminal window
```

### CLI Implementation

```python
# honeyagent/cli.py
import sys
import argparse

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="HoneyAgent CLI")
    parser.add_argument("--config", help="Config file path")
    parser.add_argument("--provider", help="Override identity provider")

    args = parser.parse_args()

    # Load config, start server, etc.
    ...

if __name__ == "__main__":
    sys.exit(main())
```

**How it works:**
- Setuptools generates a standalone script "shim" that imports the module and calls the function
- The function should accept no arguments (use argparse internally)
- Entry point name becomes a command available in the system shell after installation

**Sources:**
- [Setuptools - Entry Points Documentation](https://setuptools.pypa.io/en/latest/userguide/entry_point.html)
- [PyBites - How to Package and Deploy CLI Applications](https://pybit.es/articles/how-to-package-and-deploy-cli-apps/)

---

## 6. Complete pyproject.toml Template

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "honeyagent"
version = "0.1.0"
description = "Deception-as-a-Service for Agent Networks"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "you@example.com"}
]
keywords = ["security", "honeypot", "agents", "deception"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

dependencies = [
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "pyyaml>=6.0",
    "httpx>=0.27.0",
    "python-multipart>=0.0.6",
]

[project.optional-dependencies]
# Provider-specific extras
auth0 = [
    "authlib>=1.3.0",
    "auth0-python>=4.7.0",
]
aws = [
    "boto3>=1.34.0",
    "aioboto3>=12.3.0",
    "numpy>=1.26.0",  # For vector operations
]
freepik = [
    "pillow>=10.2.0",
    "aiofiles>=23.2.0",
]

# Composite extras
all = [
    "honeyagent[auth0,aws,freepik]",
]
dev = [
    "honeyagent[all]",
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "ruff>=0.1.0",
    "mypy>=1.8.0",
    "pre-commit>=3.6.0",
]
docs = [
    "mkdocs>=1.5.0",
    "mkdocs-material>=9.5.0",
]

[project.scripts]
honeyagent = "honeyagent.cli:main"
honeyagent-server = "honeyagent.server:start"

[project.urls]
Homepage = "https://github.com/yourusername/honeyagent"
Documentation = "https://honeyagent.readthedocs.io"
Repository = "https://github.com/yourusername/honeyagent"
Issues = "https://github.com/yourusername/honeyagent/issues"

# Ruff configuration
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
ignore = ["E501"]  # Line too long (handled by formatter)

# Pytest configuration
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
markers = [
    "auth0: tests requiring auth0 extra",
    "aws: tests requiring aws extra",
    "freepik: tests requiring freepik extra",
    "integration: integration tests",
    "e2e: end-to-end tests",
]
asyncio_mode = "auto"

# MyPy configuration
[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = [
    "authlib.*",
    "auth0.*",
    "boto3.*",
    "aioboto3.*",
]
ignore_missing_imports = true

# Coverage configuration
[tool.coverage.run]
source = ["honeyagent"]
omit = ["*/tests/*", "*/test_*.py"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.:",
]
```

---

## 7. Installation and Usage

### Basic Installation

```bash
# Core package only (with mock providers)
pip install honeyagent

# With specific provider
pip install honeyagent[auth0]
pip install honeyagent[aws]

# Multiple providers
pip install honeyagent[auth0,aws]

# All providers
pip install honeyagent[all]

# Development environment
pip install -e ".[dev]"
```

### Testing Strategy

```bash
# Run all tests (skips provider-specific tests if extras not installed)
pytest

# Run only core tests
pytest -m "not auth0 and not aws and not freepik"

# Run specific provider tests
pytest -m auth0  # Only if auth0 extra installed

# Run with coverage
pytest --cov=honeyagent --cov-report=html
```

---

## 8. Key Takeaways for HoneyAgent

### ✅ Do

1. **Use Protocol classes** for provider abstractions — structural subtyping without inheritance
2. **Implement graceful fallbacks** — always fall back to mock providers when optional deps missing
3. **Provide clear error messages** — tell users exactly which extra to install
4. **Use lazy imports** — only import provider modules when actually used
5. **Define recursive extras** — create `all` and `dev` extras that combine others
6. **Make mocks first-class** — mock providers should be fully functional for testing/demos
7. **Use conditional test markers** — skip provider-specific tests when extras not installed
8. **Document installation patterns** — show users how to install specific providers

### ❌ Don't

1. **Don't use `@runtime_checkable` for performance-critical paths** — it's slow
2. **Don't raise ImportError directly** — catch and provide helpful messages
3. **Don't hardcode provider selection** — use factory pattern with config
4. **Don't use `isinstance()` with Protocols in hot loops** — use `hasattr()` or duck typing
5. **Don't publish development dependencies as optional-dependencies** — use `[dependency-groups]` instead
6. **Don't set upper version bounds** — only use `>=` unless you know of incompatibility
7. **Don't make tests fail** when optional deps missing — skip them with `pytest.importorskip()`

### Implementation Priority

1. **Core protocols** — Define `IdentityProvider`, `VectorStore`, `ImageGenerator`
2. **Mock providers** — Implement fully functional mocks (no external deps)
3. **Factory pattern** — Create `ProviderFactory` with graceful fallbacks
4. **Optional providers** — Implement Auth0, AWS, Freepik with lazy imports
5. **pyproject.toml** — Define all extras and entry points
6. **Conditional tests** — Add markers and skip logic for provider tests
7. **Documentation** — Update README with installation examples

---

## Sources

### Optional Dependencies
- [Python Packaging User Guide - Writing pyproject.toml](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)
- [Poetry - pyproject.toml Documentation](https://python-poetry.org/docs/pyproject/)
- [PyOpenSci - Declare Dependencies](https://www.pyopensci.org/python-package-guide/package-structure-code/declare-dependencies.html)
- [Hynek Schlawack - Recursive Optional Dependencies](https://hynek.me/articles/python-recursive-optional-dependencies/)
- [UV - Declaring Dependencies](https://docs.astral.sh/uv/pip/dependencies/)

### Provider Patterns
- [Refactoring Guru - Strategy Pattern in Python](https://refactoring.guru/design-patterns/strategy/python/example)
- [Auth0 - Strategy Design Pattern in Python](https://auth0.com/blog/strategy-design-pattern-in-python/)
- [Microsoft ISE - Multi-Provider Strategy Configuration](https://devblogs.microsoft.com/ise/multi-provider-strategy-configuration-python/)
- [Medium - Designing Modular Python Packages](https://medium.com/@hieutrantrung.it/designing-modular-python-packages-with-adapters-and-optional-dependencies-63efd8b07715)

### Protocol Classes
- [Python PEP 544 - Protocols](https://peps.python.org/pep-0544/)
- [Real Python - Python Protocols](https://realpython.com/python-protocol/)
- [MyPy - Protocols and Structural Subtyping](https://mypy.readthedocs.io/en/stable/protocols.html)
- [PyBites - Leveraging Typing.Protocol](https://pybit.es/articles/typing-protocol-abc-alternative/)

### Real-World Examples
- [Medium - LangChain Abstraction](https://medium.com/@bijit211987/llm-driven-applications-with-langchain-abstraction-4907a32bdfb0)
- [DigitalOcean - LangChain Framework Explained](https://www.digitalocean.com/community/conceptual-articles/langchain-framework-explained)
- [ZenML - Haystack vs LlamaIndex](https://www.zenml.io/blog/haystack-vs-llamaindex)
- [Index.dev - AI Framework Comparison 2026](https://www.index.dev/skill-vs-skill/ai-langchain-vs-llamaindex-vs-haystack)

### Entry Points and CLI
- [Setuptools - Entry Points Documentation](https://setuptools.pypa.io/en/latest/userguide/entry_point.html)
- [PyBites - Package and Deploy CLI Applications](https://pybit.es/articles/how-to-package-and-deploy-cli-apps/)
- [Python Packaging - Entry Points Specification](https://packaging.python.org/en/latest/specifications/entry-points/)

---

**End of Research Document**
