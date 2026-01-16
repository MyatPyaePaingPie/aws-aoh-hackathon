# S3 Vectors Research

**Date**: 2026-01-16
**Purpose**: Integration patterns, failure modes, and fallback strategies for HoneyAgent

---

## What is S3 Vectors?

Amazon S3 Vectors is cloud object storage with **native vector support** - the first of its kind. It provides:

- Purpose-built, cost-optimized vector storage for AI agents, RAG, and semantic search
- Sub-second latency for infrequent queries, ~100ms for frequent queries
- Up to 90% cost reduction compared to dedicated vector databases
- Same elasticity, durability, and availability as S3

**Key Difference from Regular S3**: S3 Vectors has a dedicated `s3vectors` boto3 client with specialized APIs for vector operations. It uses "vector buckets" and "vector indexes" rather than regular S3 buckets and objects.

### Architecture Components

| Component | Description |
|-----------|-------------|
| Vector Bucket | New bucket type purpose-built for vectors |
| Vector Index | Container within bucket for organizing vectors |
| Vectors | Float32 embeddings with optional metadata |
| Metadata | Up to 50 keys, filterable or non-filterable |

---

## GA Status (December 2025)

S3 Vectors is **generally available** as of December 2025. Key improvements from preview:

| Metric | Preview (July 2025) | GA (Dec 2025) |
|--------|---------------------|---------------|
| Vectors per index | 50 million | 2 billion (40x) |
| Top-K results | 30 | 100 |
| Regions | 5 | 14 |
| Frequent query latency | ~200ms | ~100ms (2-3x faster) |

### Available Regions (GA)
- US: us-east-1, us-east-2, us-west-2
- Europe: eu-central-1, eu-west-1, eu-west-2, eu-north-1
- Asia Pacific: ap-southeast-1, ap-southeast-2, ap-northeast-1, ap-south-1, ap-northeast-2
- Canada: ca-central-1

---

## API Patterns

### Client Setup

```python
import boto3

# S3 Vectors uses a SEPARATE client from regular S3
s3vectors = boto3.client('s3vectors', region_name='us-east-1')
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
```

### Create Vector Bucket

```python
response = s3vectors.create_vector_bucket(
    vectorBucketName='my-vector-bucket'
    # Note: Encryption settings are PERMANENT after creation
)
```

### Create Vector Index

```python
response = s3vectors.create_index(
    vectorBucketName='my-vector-bucket',
    indexName='my-index',
    dimension=1536,  # IMMUTABLE after creation
    distanceMetric='cosine',  # IMMUTABLE: cosine, euclidean, or dotproduct
    # Non-filterable metadata keys are IMMUTABLE after creation
)
```

### Put Vectors (Batch)

```python
import numpy as np

vectors = [
    {
        "key": f"doc-{i}",
        "data": {
            "float32": embedding.astype(np.float32).tolist()  # MUST be float32
        },
        "metadata": {
            "source": "document.pdf",
            "chunk_id": i,
            # Filterable metadata: max 2KB
            # Total metadata: max 40KB
        }
    }
    for i, embedding in enumerate(embeddings)
]

# Batch up to 500 vectors per call
response = s3vectors.put_vectors(
    vectorBucketName='my-vector-bucket',
    indexName='my-index',
    vectors=vectors[:500]  # Max 500 per request
)
```

### Query Vectors

```python
response = s3vectors.query_vectors(
    vectorBucketName='my-vector-bucket',
    indexName='my-index',
    queryVector={"float32": query_embedding},
    topK=10,  # Max 100
    returnDistance=True,
    returnMetadata=True
)

# Response structure
for vector in response['vectors']:
    key = vector['key']
    distance = vector.get('distance')
    metadata = vector.get('metadata')
```

### Query with Metadata Filter

```python
response = s3vectors.query_vectors(
    vectorBucketName='my-vector-bucket',
    indexName='my-index',
    queryVector={"float32": query_embedding},
    topK=10,
    filter={
        "$and": [
            {"category": {"$eq": "security"}},
            {"timestamp": {"$gte": 1704067200}}
        ]
    },
    returnDistance=True,
    returnMetadata=True
)
```

---

## Quotas and Limits

### Account Limits
| Resource | Limit |
|----------|-------|
| Vector buckets per region | 10,000 |
| Vector indexes per bucket | 10,000 |
| Vectors per index | 2 billion |

### Vector Limits
| Resource | Limit |
|----------|-------|
| Dimension | 1 - 4,096 |
| Data type | float32 only |
| Metadata keys | 50 max |
| Filterable metadata | 2 KB |
| Total metadata | 40 KB |
| Non-filterable keys | 10 max |

### API Limits
| Operation | Limit |
|-----------|-------|
| PutVectors batch | 500 vectors |
| DeleteVectors batch | 500 vectors |
| GetVectors batch | 100 vectors |
| QueryVectors topK | 100 results |
| Request payload | 20 MiB |

### Rate Limits
| Operation | Rate |
|-----------|------|
| PutVectors + DeleteVectors | 1,000 req/s per index |
| Vector throughput (write) | 2,500 vectors/s per index |
| QueryVectors | Hundreds req/s per index |

---

## Common Failure Modes

### 1. Metadata Size Exceeded (MOST COMMON)

**Error**: `ValidationException: Filterable metadata must have at most 2048 bytes`

**Cause**: LangChain and other frameworks add `page_content` to metadata by default.

**Fix**:
```python
# BAD: Default includes page_content
metadata = {"text": full_document_text}  # Can exceed 2KB

# GOOD: Store text as non-filterable or truncate
metadata = {
    "text_preview": full_text[:500],  # Filterable preview
    "source": "doc.pdf"
}
# Or configure non-filterable keys at index creation
```

### 2. Dimension Mismatch

**Error**: `ValidationException: Vector dimension does not match index dimension`

**Cause**: Embedding model outputs different dimensions than index configured.

**Fix**:
```python
# Validate before sending
def validate_vector(embedding, expected_dim):
    if len(embedding) != expected_dim:
        raise ValueError(f"Expected {expected_dim} dims, got {len(embedding)}")
```

### 3. Rate Limiting (429)

**Error**: `TooManyRequestsException`

**Cause**: Exceeding request rate limits.

**Fix**:
```python
from botocore.config import Config

# Configure automatic retries with exponential backoff
config = Config(
    retries={
        'max_attempts': 5,
        'mode': 'adaptive'  # Uses exponential backoff with jitter
    }
)
s3vectors = boto3.client('s3vectors', config=config)
```

### 4. Permission Denied (403)

**Error**: `AccessDenied` when querying with `returnMetadata=True`

**Cause**: Missing `s3vectors:GetVectors` permission.

**Required permissions**:
```json
{
    "Effect": "Allow",
    "Action": [
        "s3vectors:PutVectors",
        "s3vectors:QueryVectors",
        "s3vectors:GetVectors",  // Required for metadata
        "s3vectors:DeleteVectors"
    ],
    "Resource": "arn:aws:s3vectors:*:*:vector-bucket/*"
}
```

### 5. Cold Start Latency

**Issue**: First queries take 500-700ms instead of 100ms.

**Cause**: Index not "warm" - S3 Vectors optimizes for infrequent queries.

**Mitigation**: Accept cold start latency or implement keep-warm strategy for demo.

### 6. Metadata Not Persisted (Java SDK Bug)

**Issue**: Metadata returns null despite being stored.

**Status**: Known issue in Java SDK (v2.32.4). Python SDK works correctly.

---

## Fallback Strategies for HoneyAgent

### Pattern 1: Graceful Degradation

```python
async def query_vectors_with_fallback(query_embedding: list[float], top_k: int = 5) -> list[dict]:
    """Query S3 Vectors with fallback to static responses."""
    try:
        response = s3vectors.query_vectors(
            vectorBucketName=VECTOR_BUCKET,
            indexName=VECTOR_INDEX,
            queryVector={"float32": query_embedding},
            topK=top_k,
            returnMetadata=True,
            returnDistance=True
        )
        return response.get('vectors', [])
    except Exception:
        # Return plausible fallback - never expose error
        return get_fallback("vector_search")
```

### Pattern 2: Retry with Exponential Backoff

```python
import asyncio
from typing import TypeVar, Callable
import random

T = TypeVar('T')

async def with_retry(
    fn: Callable[[], T],
    max_attempts: int = 3,
    base_delay: float = 0.5
) -> T:
    """Retry with exponential backoff and jitter."""
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as e:
            if attempt == max_attempts - 1:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            await asyncio.sleep(delay)
```

### Pattern 3: Batch with Chunking

```python
def put_vectors_batched(vectors: list[dict], batch_size: int = 500):
    """Insert vectors in batches to respect API limits."""
    results = []
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i + batch_size]
        try:
            response = s3vectors.put_vectors(
                vectorBucketName=VECTOR_BUCKET,
                indexName=VECTOR_INDEX,
                vectors=batch
            )
            results.append({"batch": i // batch_size, "status": "success"})
        except Exception:
            results.append({"batch": i // batch_size, "status": "fallback"})
    return results
```

### Pattern 4: Validate Before Send

```python
def validate_vector_payload(vectors: list[dict], index_dimension: int) -> list[dict]:
    """Validate and sanitize vectors before sending."""
    valid = []
    for v in vectors:
        # Check dimension
        embedding = v.get("data", {}).get("float32", [])
        if len(embedding) != index_dimension:
            continue

        # Check metadata size
        metadata = v.get("metadata", {})
        import json
        if len(json.dumps(metadata).encode()) > 2048:
            # Truncate or remove large fields
            metadata = {k: v for k, v in metadata.items() if k != "text"}
            v["metadata"] = metadata

        valid.append(v)
    return valid
```

---

## HoneyAgent-Specific Recommendations

### 1. Index Configuration

```python
# For HoneyAgent attack pattern storage
HONEYPOT_INDEX_CONFIG = {
    "indexName": "honeypot-patterns",
    "dimension": 1536,  # Titan Embed v2
    "distanceMetric": "cosine",
    "nonFilterableMetadataKeys": ["raw_request", "full_response"]  # Large text fields
}
```

### 2. Metadata Schema

```python
# Keep filterable metadata small
ATTACK_METADATA = {
    "attack_type": str,      # "injection", "exfiltration", etc.
    "severity": int,         # 1-10
    "timestamp": int,        # Unix timestamp
    "source_ip_hash": str,   # Anonymized
    # Non-filterable (large):
    "raw_request": str,      # Full request body
    "analysis": str          # LLM analysis
}
```

### 3. Fallback for Demo

```yaml
# config/fallbacks.yaml
vector_search:
  - key: "attack-pattern-001"
    distance: 0.15
    metadata:
      attack_type: "prompt_injection"
      severity: 8
      description: "Attempted system prompt extraction"
  - key: "attack-pattern-002"
    distance: 0.23
    metadata:
      attack_type: "data_exfiltration"
      severity: 9
      description: "Attempted credential harvesting"
```

---

## What NOT to Do

1. **Don't use regular S3 client** - Use `boto3.client('s3vectors')`, not `boto3.client('s3')`

2. **Don't exceed 2KB filterable metadata** - Common with LangChain's default behavior

3. **Don't hardcode dimensions** - Validate embedding model output matches index

4. **Don't skip error handling** - Rate limits (429) are common under load

5. **Don't assume warm latency** - First query is 500-700ms, not 100ms

6. **Don't change index config after creation** - Dimension, distance metric, and non-filterable keys are immutable

7. **Don't forget GetVectors permission** - Required for `returnMetadata=True`

8. **Don't send float64** - Must be float32, convert with `numpy.float32`

---

## Sources

### Official AWS Documentation
- [Amazon S3 Vectors Feature Page](https://aws.amazon.com/s3/features/vectors/)
- [S3 Vectors User Guide](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors.html)
- [S3 Vectors Limitations](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-limitations.html)
- [S3 Vectors Best Practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-best-practices.html)
- [Getting Started Tutorial](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-getting-started.html)

### Boto3 Reference
- [S3Vectors Client](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3vectors.html)
- [put_vectors](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3vectors/client/put_vectors.html)
- [query_vectors](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3vectors/client/query_vectors.html)

### Announcements
- [S3 Vectors GA Announcement (Dec 2025)](https://aws.amazon.com/about-aws/whats-new/2025/12/amazon-s3-vectors-generally-available/)
- [S3 Vectors Preview Announcement (July 2025)](https://aws.amazon.com/about-aws/whats-new/2025/07/amazon-s3-vectors-preview-native-support-storing-querying-vectors/)
- [AWS News Blog - GA](https://aws.amazon.com/blogs/aws/amazon-s3-vectors-now-generally-available-with-increased-scale-and-performance/)

### Community Resources
- [Example Python Code (GitHub Gist)](https://gist.github.com/jasonforte/e8d1827c9ff169fb98eaff0ab2bc84a0)
- [LangChain S3 Vectors Issue #693](https://github.com/langchain-ai/langchain-aws/issues/693)
- [InfoQ - S3 Vectors GA Analysis](https://www.infoq.com/news/2026/01/aws-s3-vectors-ga/)
- [Dev.to - How S3 Vectors Work](https://dev.to/aws-builders/how-s3-vectors-work-a-friendly-guide-to-awss-new-vector-store-3f1d)
