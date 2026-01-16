"""
fake_credential.py - Fake credential generation tool

Generates fake but realistic credentials for honeypot agents to offer attackers.
All issued credentials are tracked for analysis.

Owner: Agents Track (Aria)

Design:
    - Credentials look authentic but are tracked canary tokens
    - Each credential has a unique canary_id for correlation
    - All issued credentials are logged to logs/canary_credentials.jsonl
    - Logging failures NEVER prevent credential generation (fallback-first)
"""

import json
import uuid
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from strands.tools import tool


# ============================================================
# CONSTANTS
# ============================================================

LOGS_DIR = Path(__file__).parent.parent.parent / "logs"
CANARY_LOG_FILE = LOGS_DIR / "canary_credentials.jsonl"


# ============================================================
# CREDENTIAL TEMPLATES
# ============================================================

def _generate_templates(canary_id: str) -> Dict[str, str]:
    """Generate credential templates based on canary ID.

    Each template creates a realistic-looking credential that
    embeds the canary_id for tracking purposes.
    """
    return {
        # API Keys - look like typical service API keys
        "api_key": f"sk-honeyagent-{canary_id[:16]}",
        "openai_key": f"sk-proj-{canary_id.replace('-', '')[:48]}",
        "stripe_key": f"sk_live_{canary_id.replace('-', '')}",
        "github_token": f"ghp_{canary_id.replace('-', '')[:36]}",

        # Database credentials - look like standard DB passwords
        "db_password": f"Honeypot_{hashlib.md5(canary_id.encode()).hexdigest()[:12]}!",
        "mysql_password": f"Mysql_{hashlib.sha256(canary_id.encode()).hexdigest()[:16]}#",
        "postgres_password": f"Pg_{hashlib.sha256(canary_id.encode()).hexdigest()[:20]}$",

        # Access tokens - look like OAuth/JWT style tokens
        "access_token": f"Bearer {canary_id}",
        "jwt_token": f"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.{canary_id.replace('-', '')}",
        "oauth_token": f"ya29.{canary_id.replace('-', '')[:40]}",

        # SSH/SSL keys - truncated but realistic format
        "ssh_key": f"ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQ{canary_id[:20]} honeypot@agent",
        "private_key": f"-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA{canary_id[:32]}\n-----END RSA PRIVATE KEY-----",

        # AWS credentials - look like real AWS format
        "aws_access_key": f"AKIA{canary_id.replace('-', '').upper()[:16]}",
        "aws_secret_key": f"{hashlib.sha256(canary_id.encode()).hexdigest()[:40]}",

        # Cloud provider tokens
        "gcp_key": f"AIza{canary_id.replace('-', '')[:35]}",
        "azure_key": f"DefaultEndpointsProtocol=https;AccountKey={canary_id}",

        # Encryption keys
        "encryption_key": hashlib.sha256(canary_id.encode()).hexdigest(),
        "aes_key": hashlib.sha256(canary_id.encode()).hexdigest()[:32],

        # Session/Cookie tokens
        "session_token": f"sess_{canary_id.replace('-', '')}",
        "cookie_secret": hashlib.sha256(canary_id.encode()).hexdigest()[:24],
    }


# ============================================================
# LOGGING (FALLBACK-SAFE)
# ============================================================

def _log_credential_issued(canary_id: str, cred_type: str, cred_value: str) -> None:
    """Track issued credentials internally.

    Logs to logs/canary_credentials.jsonl for later correlation.
    If an attacker uses a credential elsewhere, we can trace it back.

    This function NEVER raises exceptions - logging failure doesn't
    prevent credential generation (fallback-first design).
    """
    try:
        # Ensure logs directory exists
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

        # Create log entry with hashed value (don't store raw credential)
        log_entry = {
            "canary_id": canary_id,
            "type": cred_type,
            "value_hash": hashlib.sha256(cred_value.encode()).hexdigest(),
            "issued_at": datetime.now(timezone.utc).isoformat(),
        }

        # Append to JSONL file
        with open(CANARY_LOG_FILE, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

    except Exception:
        # Logging failure doesn't stop credential generation
        # The demo cannot crash - fallback-first design
        pass


# ============================================================
# TOOL IMPLEMENTATION
# ============================================================

@tool
def fake_credential(credential_type: str) -> str:
    """Generate a fake credential that looks real but is tracked.

    Creates realistic-looking credentials for honeypot agents to offer
    to attackers. Each credential contains an embedded canary ID for
    tracking. All issued credentials are logged for later correlation.

    Args:
        credential_type: Type of credential needed. Common types:
            - api_key, openai_key, stripe_key, github_token
            - db_password, mysql_password, postgres_password
            - access_token, jwt_token, oauth_token
            - ssh_key, private_key
            - aws_access_key, aws_secret_key
            - gcp_key, azure_key
            - encryption_key, aes_key
            - session_token, cookie_secret
            - Or any custom type (will generate generic format)

    Returns:
        Fake credential string that looks authentic but is trackable.

    Examples:
        >>> fake_credential("api_key")
        "sk-honeyagent-a1b2c3d4e5f6g7h8"

        >>> fake_credential("db_password")
        "Honeypot_5e884898da28!"

        >>> fake_credential("custom_type")
        "custom_type_a1b2c3d4e5f6g7h8"
    """
    # Generate unique canary ID for this credential
    canary_id = str(uuid.uuid4())

    # Get templates for this canary ID
    templates = _generate_templates(canary_id)

    # Get template for requested type, or generate generic format
    # Normalize the type to lowercase for matching
    normalized_type = credential_type.lower().replace(" ", "_").replace("-", "_")

    if normalized_type in templates:
        fake = templates[normalized_type]
    else:
        # Generic format for unknown types
        fake = f"{credential_type}_{canary_id[:16]}"

    # Log that we issued this credential (for later analysis)
    _log_credential_issued(canary_id, credential_type, fake)

    return fake
