# Copyright 2026 HoneyAgent Contributors
# SPDX-License-Identifier: Apache-2.0
"""Mock providers for testing and zero-config demos.

These providers implement all core protocols without external dependencies,
enabling HoneyAgent to run out-of-the-box without any API keys or services.

Mock providers are first-class citizens:
- Fully functional for demos and testing
- Deterministic behavior for reproducibility
- No network calls or side effects
"""

import hashlib
import random
import uuid
from datetime import datetime, timezone

from backend.core.protocols import IdentityResult


class MockIdentityProvider:
    """Mock identity provider that validates all tokens.

    By default, marks ~30% of requests as honeypot-bound for demo purposes.
    Configure via constructor to customize behavior.
    """

    def __init__(
        self,
        default_valid: bool = True,
        honeypot_ratio: float = 0.3,
        **kwargs,
    ):
        """Initialize mock identity provider.

        Args:
            default_valid: Whether tokens are valid by default.
            honeypot_ratio: Fraction of requests to route to honeypot (0.0-1.0).
        """
        self.default_valid = default_valid
        self.honeypot_ratio = honeypot_ratio

    async def verify_token(self, token: str) -> IdentityResult:
        """Verify token and return mock identity.

        Uses token hash to deterministically assign honeypot status,
        ensuring consistent routing for the same token.
        """
        # Deterministic assignment based on token hash
        token_hash = int(hashlib.sha256(token.encode()).hexdigest()[:8], 16)
        is_honeypot = (token_hash % 100) < (self.honeypot_ratio * 100)

        return IdentityResult(
            valid=self.default_valid,
            agent_id=f"mock-agent-{token[:8] if len(token) >= 8 else token}",
            agent_type="honeypot" if is_honeypot else "real",
            is_honeypot=is_honeypot,
            fga_allowed=True,
            metadata={
                "provider": "mock",
                "verified_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    async def check_authorization(
        self, user_id: str, resource: str, action: str
    ) -> bool:
        """Always authorize in mock mode."""
        return True


class MockVectorStore:
    """In-memory vector store for testing.

    Stores vectors in memory with basic similarity search.
    Not suitable for production - use S3VectorStore instead.
    """

    def __init__(self, **kwargs):
        self.vectors: dict[str, dict] = {}

    async def store(self, vectors: list[float], metadata: dict) -> str:
        """Store vectors in memory."""
        id = str(uuid.uuid4())
        self.vectors[id] = {
            "vectors": vectors,
            "metadata": metadata,
            "stored_at": datetime.now(timezone.utc).isoformat(),
        }
        return id

    async def search(
        self, query: list[float], top_k: int = 10
    ) -> list[dict]:
        """Search vectors using cosine similarity.

        Simplified implementation - returns top_k results with mock scores.
        """
        results = []
        for id, data in list(self.vectors.items())[:top_k]:
            # Simplified scoring based on vector length similarity
            score = 1.0 - abs(len(query) - len(data["vectors"])) / max(
                len(query), len(data["vectors"]), 1
            )
            results.append({
                "id": id,
                "score": score,
                **data["metadata"],
            })
        return sorted(results, key=lambda x: x["score"], reverse=True)


class MockImageGenerator:
    """Mock image generator returning placeholder images.

    Returns a minimal 1x1 transparent PNG for all requests.
    Use FreepikGenerator for actual image generation.
    """

    # Minimal 1x1 transparent PNG
    PLACEHOLDER_PNG = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4,
        0x89, 0x00, 0x00, 0x00, 0x0A, 0x49, 0x44, 0x41,
        0x54, 0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00,
        0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00,
        0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE,
        0x42, 0x60, 0x82,
    ])

    async def generate(self, prompt: str) -> bytes:
        """Return placeholder image."""
        return self.PLACEHOLDER_PNG


class MockLLMProvider:
    """Mock LLM with context-aware canned responses.

    Provides realistic-sounding responses for demo purposes.
    Use BedrockProvider for actual LLM completions.
    """

    RESPONSES = {
        "default": [
            "I understand your request. Processing now.",
            "Thank you for reaching out. Let me help you with that.",
            "I can assist with that. Here's what I found.",
        ],
        "error": [
            "I apologize, but I couldn't process that request.",
            "There seems to be an issue. Let me try a different approach.",
        ],
        "success": [
            "Request completed successfully.",
            "Operation finished. Here are the results.",
        ],
    }

    async def complete(
        self, prompt: str, system: str | None = None
    ) -> str:
        """Return context-appropriate mock response."""
        prompt_lower = prompt.lower()

        if "error" in prompt_lower or "fail" in prompt_lower:
            category = "error"
        elif "success" in prompt_lower or "complete" in prompt_lower:
            category = "success"
        else:
            category = "default"

        # Use prompt hash for deterministic response
        idx = hash(prompt) % len(self.RESPONSES[category])
        return self.RESPONSES[category][idx]

    async def embed(self, text: str) -> list[float]:
        """Generate deterministic pseudo-embedding.

        Uses SHA-256 hash to create a 32-dimensional embedding.
        Consistent for the same input text.
        """
        h = hashlib.sha256(text.encode()).digest()
        return [float(b) / 255.0 for b in h]


class MockCredentialGenerator:
    """Mock credential generator with realistic-looking fakes.

    Generates credentials that look authentic but are clearly fake
    on inspection. Used for honeypot traps.
    """

    PREFIXES = {
        "api_key": ["sk-", "ak-", "key-", "api_"],
        "password": [""],
        "token": ["tok_", "token_", "jwt_"],
        "aws_key": ["AKIA", "ABIA", "ACCA"],
    }

    async def generate(
        self, credential_type: str, context: dict | None = None
    ) -> dict:
        """Generate fake credential.

        Args:
            credential_type: Type of credential to generate.
            context: Optional context (e.g., service name).
        """
        prefixes = self.PREFIXES.get(credential_type, [""])
        prefix = random.choice(prefixes)

        # Generate random suffix
        suffix_len = 32 if credential_type == "api_key" else 24
        suffix = "".join(
            random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=suffix_len)
        )

        value = f"{prefix}{suffix}"

        return {
            "value": value,
            "type": credential_type,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "is_fake": True,  # Always marked for internal tracking
            "context": context or {},
        }
