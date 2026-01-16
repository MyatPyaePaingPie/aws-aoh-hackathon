# Amazon Bedrock Titan Embeddings Research

**Date**: 2026-01-16
**Purpose**: Usage patterns, common failures, and fallback strategies for HoneyAgent hackathon

---

## 1. API Usage Patterns

### Model Information

| Property | Value |
|----------|-------|
| Model ID | `amazon.titan-embed-text-v1` |
| Output dimensions | 1,536 (fixed) |
| Max input tokens | 8,192 |
| Languages supported | 25+ |
| Batch support | No (single text only) |

### Basic Request Format

```python
import boto3
import json

bedrock_runtime = boto3.client(
    service_name='bedrock-runtime',
    region_name='us-west-2'
)

body = json.dumps({
    "inputText": "Your text to embed here"
})

response = bedrock_runtime.invoke_model(
    body=body,
    modelId='amazon.titan-embed-text-v1',
    accept='application/json',
    contentType='application/json'
)

response_body = json.loads(response['body'].read())
embedding = response_body['embedding']  # List of 1,536 floats
token_count = response_body['inputTextTokenCount']
```

### Response Format

```json
{
  "embedding": [0.123, -0.456, ...],  // 1,536 floats
  "inputTextTokenCount": 42
}
```

### Key Limitations

- **No inference parameters**: v1 does not support `maxTokenCount`, `topP`, `normalize`, or `dimensions`
- **No batch embedding**: Must call once per text
- **Fixed dimensions**: Always returns 1,536-dimension vectors
- **Float only**: No binary/int8 quantization options

---

## 2. Common Errors and HTTP Status Codes

### Complete Exception Reference

| Exception | HTTP Code | Retryable | Description |
|-----------|-----------|-----------|-------------|
| `ThrottlingException` | 429 | Yes | Exceeded account quotas |
| `ModelNotReadyException` | 429 | Yes (auto 5x) | Model not ready for inference |
| `ModelTimeoutException` | 408 | Yes | Processing exceeded timeout |
| `InternalServerException` | 500 | Yes | AWS internal error |
| `ServiceUnavailableException` | 503 | Yes | Service temporarily down |
| `ValidationException` | 400 | No | Invalid input format |
| `ServiceQuotaExceededException` | 400 | No | Hard quota limit |
| `AccessDeniedException` | 403 | No | Missing permissions |
| `ResourceNotFoundException` | 404 | No | Model/resource not found |
| `ModelErrorException` | 424 | Depends | Model processing failed |

### Error Messages You'll See

```
ThrottlingException: "Your request rate is too high. Reduce the frequency of requests."
ThrottlingException: "Too many tokens, please wait before trying again."
ThrottlingException: "Your request was denied due to exceeding the account quotas for Amazon Bedrock."
ModelTimeoutException: "Processing time exceeded the model timeout length."
ValidationException: "The value is invalid for inputText."
AccessDeniedException: "You don't have access to the model..."
```

### Boto3 Exception Classes

```python
from botocore.exceptions import ClientError

# Specific Bedrock exceptions:
client.exceptions.ThrottlingException
client.exceptions.ModelTimeoutException
client.exceptions.InternalServerException
client.exceptions.ServiceUnavailableException
client.exceptions.ValidationException
client.exceptions.ServiceQuotaExceededException
client.exceptions.ModelNotReadyException
client.exceptions.AccessDeniedException
```

---

## 3. Rate Limiting and Throttling

### Quota Types

1. **Requests Per Minute (RPM)**: How many API calls per minute
2. **Tokens Per Minute (TPM)**: Total tokens processed per minute
3. **Transactions Per Second (TPS)**: Burst rate limit

### Why Throttling Happens

- Shared capacity pool across customers (on-demand mode)
- Spikes during high-demand periods
- Misconfigured client-side retry loops
- Quotas silently set to 0 (known AWS bug)

### Checking Quotas

```bash
# View current quotas
aws service-quotas list-service-quotas --service-code bedrock

# Request increase
aws service-quotas request-service-quota-increase \
  --service-code bedrock \
  --quota-code L-XXXXX \
  --desired-value 100
```

---

## 4. Retry Strategies

### Exponential Backoff with Jitter (Recommended)

```python
import time
import random
import json
import boto3
from botocore.exceptions import ClientError

def get_embedding_with_retry(
    client,
    text: str,
    max_attempts: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0
) -> list[float] | None:
    """
    Get embedding with exponential backoff retry.
    Returns embedding list or None on failure.
    """
    model_id = 'amazon.titan-embed-text-v1'

    for attempt in range(max_attempts):
        try:
            response = client.invoke_model(
                modelId=model_id,
                body=json.dumps({"inputText": text}),
                accept='application/json',
                contentType='application/json'
            )
            result = json.loads(response['body'].read())
            return result['embedding']

        except client.exceptions.ThrottlingException:
            if attempt == max_attempts - 1:
                return None
            delay = min(base_delay * (2 ** attempt), max_delay)
            jitter = delay * 0.2 * random.random()
            time.sleep(delay + jitter)

        except client.exceptions.ModelTimeoutException:
            if attempt == max_attempts - 1:
                return None
            delay = min(base_delay * (2 ** attempt), max_delay)
            time.sleep(delay)

        except (
            client.exceptions.InternalServerException,
            client.exceptions.ServiceUnavailableException
        ):
            if attempt == max_attempts - 1:
                return None
            time.sleep(base_delay * (2 ** attempt))

        except (
            client.exceptions.ValidationException,
            client.exceptions.AccessDeniedException,
            client.exceptions.ServiceQuotaExceededException
        ):
            # Non-retryable errors
            return None

        except ClientError:
            return None

    return None
```

### AWS SDK Built-in Retry

```python
from botocore.config import Config

# Configure SDK retries
config = Config(
    retries={
        'max_attempts': 5,
        'mode': 'adaptive'  # or 'standard'
    }
)

client = boto3.client('bedrock-runtime', config=config)
```

### Error Classification Helper

```python
RETRYABLE_ERRORS = {
    'ThrottlingException',
    'TooManyRequestsException',
    'ModelTimeoutException',
    'InternalServerException',
    'ServiceUnavailableException',
    'ModelNotReadyException'
}

NON_RETRYABLE_ERRORS = {
    'ValidationException',
    'AccessDeniedException',
    'ServiceQuotaExceededException',
    'ResourceNotFoundException',
    'InvalidRequestException'
}

def should_retry(error_code: str) -> bool:
    return error_code in RETRYABLE_ERRORS
```

---

## 5. Fallback Strategies for HoneyAgent

### Strategy 1: Return Cached/Precomputed Embeddings

```python
# Pre-compute embeddings for common honeypot responses
CACHED_EMBEDDINGS = {
    "credential_request": [...],  # 1,536 floats
    "system_access": [...],
    "data_exfil": [...]
}

async def get_embedding_with_fallback(text: str, category: str = None) -> list[float]:
    try:
        return await get_bedrock_embedding(text)
    except Exception:
        if category and category in CACHED_EMBEDDINGS:
            return CACHED_EMBEDDINGS[category]
        return CACHED_EMBEDDINGS["default"]
```

### Strategy 2: Zero Vector (Neutral Response)

```python
ZERO_EMBEDDING = [0.0] * 1536

def get_embedding_safe(text: str) -> list[float]:
    try:
        return get_bedrock_embedding(text)
    except Exception:
        # Return neutral embedding - won't match anything strongly
        return ZERO_EMBEDDING
```

### Strategy 3: Local Model Fallback

```python
from sentence_transformers import SentenceTransformer

# Load lightweight local model (50MB)
local_model = SentenceTransformer('all-MiniLM-L6-v2')

def get_embedding_with_local_fallback(text: str) -> list[float]:
    try:
        return get_bedrock_embedding(text)  # 1,536 dims
    except Exception:
        # Local fallback - 384 dims, pad to 1536
        local_emb = local_model.encode(text).tolist()
        return local_emb + [0.0] * (1536 - len(local_emb))
```

### Strategy 4: Cross-Region Fallback

```python
REGIONS = ['us-east-1', 'us-west-2', 'eu-west-1']

async def get_embedding_cross_region(text: str) -> list[float]:
    for region in REGIONS:
        try:
            client = boto3.client('bedrock-runtime', region_name=region)
            return get_embedding(client, text)
        except client.exceptions.ThrottlingException:
            continue
    raise Exception("All regions throttled")
```

### Strategy 5: Graceful Degradation (HoneyAgent-Specific)

```python
# For honeypot: if embedding fails, still trap the attacker
async def analyze_threat_with_fallback(text: str) -> dict:
    try:
        embedding = await get_embedding(text)
        threat_score = await vector_similarity_search(embedding)
        return {"analyzed": True, "threat_score": threat_score}
    except Exception:
        # Fallback: keyword-based analysis
        keywords = ["password", "admin", "root", "ssh", "api_key"]
        matches = sum(1 for k in keywords if k in text.lower())
        return {
            "analyzed": True,
            "threat_score": min(matches * 0.2, 1.0),
            "method": "keyword_fallback"
        }
```

---

## 6. Best Practices Summary

### DO

1. **Implement retry with exponential backoff + jitter**
2. **Set max_delay to 60s** to sync with minute-based quota refresh
3. **Cache frequently embedded text** (honeypot responses)
4. **Use cross-region inference profiles** for high availability
5. **Monitor CloudWatch metrics**: `InputTokenCount`, `Invocations`, `ThrottledCount`
6. **Pre-flight check**: Validate IAM permissions and model access before demo

### DON'T

1. **Don't retry ValidationException** - fix the input instead
2. **Don't expose error messages** to users (security risk)
3. **Don't batch requests** - Titan v1 doesn't support it
4. **Don't assume quotas** - they can be silently set to 0

### Pre-Demo Checklist

```bash
# 1. Verify model access
aws bedrock list-foundation-models --query "modelSummaries[?modelId=='amazon.titan-embed-text-v1']"

# 2. Test invoke
aws bedrock-runtime invoke-model \
  --model-id amazon.titan-embed-text-v1 \
  --body '{"inputText": "test"}' \
  --content-type application/json \
  --accept application/json \
  output.json

# 3. Check quotas
aws service-quotas get-service-quota \
  --service-code bedrock \
  --quota-code L-XXX  # Replace with Titan quota code
```

---

## 7. HoneyAgent Integration Recommendations

### For Fallback-First Design

```python
# config/fallbacks.yaml
embeddings:
  default: [0.0, 0.0, ...]  # 1,536 zeros
  categories:
    credential_theft: "cached/credential_embedding.json"
    data_exfil: "cached/exfil_embedding.json"
    lateral_movement: "cached/lateral_embedding.json"
```

### Embedding Service Pattern

```python
class EmbeddingService:
    def __init__(self):
        self.client = boto3.client('bedrock-runtime')
        self.cache = {}  # LRU cache
        self.fallback_embeddings = load_fallbacks()

    async def embed(self, text: str, category: str = None) -> list[float]:
        # Check cache first
        if text in self.cache:
            return self.cache[text]

        try:
            embedding = await self._call_bedrock(text)
            self.cache[text] = embedding
            return embedding
        except Exception:
            # Fallback - never fail the demo
            return self.fallback_embeddings.get(
                category,
                self.fallback_embeddings["default"]
            )
```

---

## Sources

- [Amazon Titan Text Embeddings models - AWS Docs](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html)
- [Titan Embeddings G1 - Text Parameters](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-titan-embed-text.html)
- [InvokeModel API Reference](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_InvokeModel.html)
- [Error Handling and Retry Strategies - Practical AWS Bedrock](https://scttfrdmn.github.io/practical-aws-bedrock/tutorials/intermediate/error-handling.html)
- [Troubleshoot Bedrock Throttling - AWS re:Post](https://repost.aws/knowledge-center/bedrock-throttling-error)
- [Bedrock Quotas](https://docs.aws.amazon.com/bedrock/latest/userguide/quotas.html)
- [Getting Started with Titan Text Embeddings - AWS Blog](https://aws.amazon.com/blogs/machine-learning/getting-started-with-amazon-titan-text-embeddings/)
- [Titan Text Embeddings V2 - AWS Blog](https://aws.amazon.com/blogs/machine-learning/get-started-with-amazon-titan-text-embeddings-v2-a-new-state-of-the-art-embeddings-model-on-amazon-bedrock/)
- [Handling ThrottlingException - Bobcares](https://bobcares.com/blog/aws-bedrock-throttlingexception/)
