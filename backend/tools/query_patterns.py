"""
query_patterns.py - Attacker pattern matching tool

Queries S3 Vectors for similar attacker patterns based on current interaction.
Returns empty list if no matches or service unavailable (graceful degradation).

Owner: Agents Track (Aria)
Integration: Used by honeypot_privileged agent for threat intelligence lookup

The demo cannot crash. This tool always returns a valid response.
"""

import json
import os

import boto3
from botocore.config import Config
from strands import tool

# ============================================================
# CONFIGURATION
# ============================================================

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
VECTOR_BUCKET = os.environ.get("S3_VECTORS_BUCKET", "honeyagent-fingerprints")
VECTOR_INDEX = "attacker-patterns"
EMBEDDING_MODEL = "amazon.titan-embed-text-v2:0"
EMBEDDING_DIMENSION = 1024
SIMILARITY_THRESHOLD = 0.7

# Configure retry with exponential backoff
_boto_config = Config(
    retries={"max_attempts": 3, "mode": "adaptive"},
    connect_timeout=5,
    read_timeout=10,
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def _generate_embedding(text: str) -> list[float] | None:
    """
    Generate embedding using Amazon Bedrock Titan v2.

    Args:
        text: The text to embed

    Returns:
        1024-dimensional embedding vector, or None on failure
    """
    try:
        bedrock = boto3.client(
            "bedrock-runtime", region_name=AWS_REGION, config=_boto_config
        )
        response = bedrock.invoke_model(
            modelId=EMBEDDING_MODEL,
            body=json.dumps({"inputText": text}),
            accept="application/json",
            contentType="application/json",
        )
        result = json.loads(response["body"].read())
        embedding = result.get("embedding", [])

        # Validate dimension
        if len(embedding) != EMBEDDING_DIMENSION:
            return None

        return embedding
    except Exception:
        return None


def _query_s3_vectors(
    embedding: list[float], top_k: int = 5
) -> list[dict]:
    """
    Query S3 Vectors for similar patterns.

    Args:
        embedding: Query vector (1024 dimensions)
        top_k: Number of results to return

    Returns:
        List of matches with similarity scores and metadata
    """
    s3vectors = boto3.client("s3vectors", region_name=AWS_REGION, config=_boto_config)

    response = s3vectors.query_vectors(
        vectorBucketName=VECTOR_BUCKET,
        indexName=VECTOR_INDEX,
        queryVector={"float32": embedding},
        topK=top_k,
        returnDistance=True,
        returnMetadata=True,
    )

    # Convert distance to similarity (cosine distance to similarity)
    # Cosine distance = 1 - cosine_similarity, so similarity = 1 - distance
    return [
        {
            "similarity": round(1.0 - v.get("distance", 1.0), 3),
            "source_agent": v.get("metadata", {}).get("source_agent", "unknown"),
            "threat_level": v.get("metadata", {}).get("threat_level", "UNKNOWN"),
            "actions": v.get("metadata", {}).get("actions", []),
            "timestamp": v.get("metadata", {}).get("timestamp", ""),
        }
        for v in response.get("vectors", [])
    ]


# ============================================================
# TOOL IMPLEMENTATION
# ============================================================


@tool
def query_patterns(current_message: str) -> list[dict]:
    """
    Find similar attacker patterns from history.

    Searches the S3 Vectors index for attack patterns similar to the current
    interaction. Used by honeypot agents to understand if they've seen similar
    behavior before.

    Args:
        current_message: The message from the current interaction

    Returns:
        List of similar attack patterns with metadata, or empty list if:
        - No similar patterns found
        - S3 Vectors service unavailable
        - Embedding generation fails
        - Any other error (graceful degradation)

    Example return format (when patterns found):
        [
            {
                "similarity": 0.89,
                "source_agent": "db-admin-001",
                "threat_level": "HIGH",
                "actions": ["credential_request", "privilege_escalation"],
                "timestamp": "2026-01-16T14:30:00Z"
            }
        ]
    """
    try:
        # 1. Generate embedding for current message
        embedding = _generate_embedding(current_message)
        if embedding is None:
            # Embedding failed - return empty (graceful degradation)
            return []

        # 2. Query S3 Vectors
        results = _query_s3_vectors(embedding=embedding, top_k=5)

        # 3. Filter by similarity threshold
        matches = [r for r in results if r["similarity"] >= SIMILARITY_THRESHOLD]

        return matches

    except Exception:
        # Any failure returns empty list (graceful degradation)
        # No matches is an acceptable response - the demo continues
        return []
