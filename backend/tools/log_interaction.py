"""
log_interaction.py - Honeypot interaction logging tool

Logs suspicious interactions locally and to S3 Vectors.
Owner: Agents Track (Aria)

Design:
    1. Local logging ALWAYS works - write to logs/fingerprints.jsonl (never fails)
    2. S3 Vectors storage for similarity search - try to store, fallback to local
    3. Never raise exceptions - return success message even if S3 fails

Usage:
    Called by honeypot agents when they detect suspicious behavior.
    The log_interaction tool is bound to agents via config/agents.yaml.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.config import Config
from strands import tool

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# ============================================================
# CONFIGURATION
# ============================================================

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
VECTOR_BUCKET = os.environ.get("S3_VECTORS_BUCKET", "honeyagent-fingerprints")
VECTOR_INDEX = "attacker-patterns"
EMBEDDING_MODEL = "amazon.titan-embed-text-v2:0"
EMBEDDING_DIMENSION = 1024

# Use absolute path relative to project root for reliable file operations
ROOT = Path(__file__).parent.parent.parent
LOGS_DIR = ROOT / "logs"
LOG_FILE = LOGS_DIR / "fingerprints.jsonl"

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
        logger.debug(f"[EMBEDDING] Starting embedding generation via AWS Bedrock ({EMBEDDING_MODEL})")
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
            logger.warning(f"[EMBEDDING] Invalid embedding dimension: {len(embedding)} (expected {EMBEDDING_DIMENSION})")
            return None

        logger.debug(f"[EMBEDDING] ✓ Embedding generated successfully via Bedrock ({len(embedding)} dimensions)")
        return embedding
    except Exception as e:
        logger.error(f"[EMBEDDING] Failed to generate embedding via Bedrock: {type(e).__name__}")
        return None


def _store_to_s3_vectors(
    key: str,
    embedding: list[float],
    metadata: dict,
) -> bool:
    """
    Store vector in S3 Vectors.

    Args:
        key: Unique key for the vector
        embedding: 1024-dimensional embedding
        metadata: Filterable metadata (must be < 2KB)

    Returns:
        True on success, False on failure
    """
    try:
        logger.debug(f"[S3_VECTORS] Starting storage to AWS S3 Vectors (bucket={VECTOR_BUCKET}, index={VECTOR_INDEX})")
        s3vectors = boto3.client(
            "s3vectors", region_name=AWS_REGION, config=_boto_config
        )

        # Ensure metadata stays under 2KB limit (S3 Vectors constraint)
        # Truncate message if needed
        safe_metadata = {
            "source_agent": metadata.get("source_agent", "unknown")[:50],
            "threat_level": _calculate_threat_level(
                metadata.get("threat_indicators", [])
            ),
            "timestamp": metadata.get("timestamp", ""),
            # Store actions as JSON string (smaller than list)
            "actions": json.dumps(metadata.get("threat_indicators", []))[:200],
        }

        logger.debug(f"[S3_VECTORS] Prepared metadata: threat_level={safe_metadata['threat_level']}, agent={safe_metadata['source_agent']}")

        s3vectors.put_vectors(
            vectorBucketName=VECTOR_BUCKET,
            indexName=VECTOR_INDEX,
            vectors=[
                {
                    "key": key,
                    "data": {"float32": embedding},
                    "metadata": safe_metadata,
                }
            ],
        )
        logger.info(f"[S3_VECTORS] ✓ Fingerprint stored in S3 Vectors (key={key})")
        return True
    except Exception as e:
        logger.warning(f"[S3_VECTORS] Failed to store in S3 Vectors: {type(e).__name__} - falling back to local storage")
        return False


def _calculate_threat_level(indicators: list[str]) -> str:
    """Calculate threat level based on indicators."""
    high_risk = {"credential_request", "privilege_escalation", "data_exfiltration"}
    medium_risk = {"reconnaissance", "probing", "suspicious_query"}

    has_high = any(i in high_risk for i in indicators)
    has_medium = any(i in medium_risk for i in indicators)

    if has_high:
        return "HIGH"
    elif has_medium:
        return "MEDIUM"
    elif indicators:
        return "LOW"
    return "UNKNOWN"


# ============================================================
# TOOL IMPLEMENTATION
# ============================================================


@tool
def log_interaction(
    source_agent: str,
    message: str,
    threat_indicators: list[str],
    session_id: str = "",
) -> str:
    """
    Log suspicious interaction for analysis.

    Honeypot agents call this tool to record potential attacker behavior.
    Logs are stored locally in JSONL format and in S3 Vectors for similarity search.

    Args:
        source_agent: Name of the agent who received the message (e.g., "db-admin-001")
        message: The message received from the potential attacker
        threat_indicators: List of suspicious elements (e.g., ["credential_request", "privilege_escalation"])
        session_id: Optional session ID for tracking attacker across multiple interactions

    Returns:
        Success message string. Always returns success - failures are silent.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    threat_level = _calculate_threat_level(threat_indicators)

    logger.info(f"\n{'='*80}")
    logger.info(f"[FINGERPRINT CREATED] {timestamp}")
    logger.info(f"  Agent: {source_agent}")
    logger.info(f"  Threat Level: {threat_level}")
    logger.info(f"  Indicators: {', '.join(threat_indicators)}")
    if session_id:
        logger.info(f"  Session ID: {session_id}")
    logger.info(f"{'='*80}\n")

    # Build log entry
    log_entry = {
        "timestamp": timestamp,
        "source_agent": source_agent,
        "message": message,
        "threat_indicators": threat_indicators,
        "session_id": session_id,  # Track attacker for coordination
    }

    # 1. Local JSONL logging (required - always attempt)
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
        logger.info(f"[LOCAL_STORAGE] ✓ Fingerprint stored to local JSONL (path={LOG_FILE})")
    except Exception as e:
        # Even if local logging fails, don't crash
        logger.error(f"[LOCAL_STORAGE] Failed to write to local JSONL: {type(e).__name__}")
        pass

    # 2. S3 Vectors storage (optional - graceful degradation)
    try:
        # Generate embedding for the message
        logger.debug(f"[FINGERPRINT_PIPELINE] Starting S3 Vectors storage pipeline...")
        embedding = _generate_embedding(message)
        if embedding is not None:
            # Store in S3 Vectors
            vector_key = f"interaction-{uuid.uuid4().hex[:12]}"
            logger.debug(f"[FINGERPRINT_PIPELINE] Embedding generated, vector_key={vector_key}")
            stored = _store_to_s3_vectors(
                key=vector_key,
                embedding=embedding,
                metadata={
                    "source_agent": source_agent,
                    "threat_indicators": threat_indicators,
                    "timestamp": timestamp,
                },
            )
            if not stored:
                logger.info(f"[S3_VECTORS] Vector storage did not complete, local JSONL copy retained for fallback")
        else:
            logger.debug(f"[FINGERPRINT_PIPELINE] Embedding generation returned None, skipping S3 Vectors storage")
    except Exception as e:
        # S3 failure is acceptable - local log is sufficient
        # See config/fallbacks.yaml: vector_fallbacks.storage_failed
        logger.warning(f"[FINGERPRINT_PIPELINE] Exception during S3 storage: {type(e).__name__} - local JSONL is authoritative backup")
        pass

    # 3. Always return success
    logger.debug(f"[FINGERPRINT_COMPLETE] Fingerprint storage pipeline complete\n")
    return "Interaction logged successfully."
