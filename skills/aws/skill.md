---
name: aws
description: AWS SDK patterns for Python (boto3) and TypeScript (AWS SDK v3) covering IAM credential chain, S3, DynamoDB single-table design, Lambda handlers, SQS batch processing, Secrets Manager, botocore retry config, and cost controls.
---

# AWS SDK Patterns

Production patterns for AWS services using boto3 (Python) and AWS SDK v3 (TypeScript).

## When to Activate

- Writing code that imports `boto3`, `@aws-sdk/*`, or `aws-sdk`
- Configuring authentication for AWS services (IAM roles, instance profiles, environment credentials)
- Reading or writing objects in S3 with presigned URLs or multipart upload
- Designing a DynamoDB table or writing query/scan access patterns
- Writing Lambda handler functions or connecting them to SQS/S3/API Gateway triggers
- Processing SQS messages with partial batch failure handling
- Retrieving secrets from Secrets Manager or Parameter Store
- Troubleshooting `ClientError`, credential resolution, or throttling

## Authentication

### Credential Chain (always prefer role-based auth)

boto3 and AWS SDK v3 resolve credentials in this order — the same code works locally and in production without changes:

```
1. Explicit credentials passed to client (avoid — hardcodes secrets)
2. Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN
3. AWS config file: ~/.aws/credentials
4. IAM instance profile (EC2) / task role (ECS) / execution role (Lambda)
5. IAM Roles Anywhere / container credentials
```

```python
# Python — boto3 picks up credentials automatically
import boto3

s3 = boto3.client("s3", region_name="us-east-1")  # uses credential chain

# BAD: hardcoded credentials
s3 = boto3.client("s3", aws_access_key_id="AKIA...", aws_secret_access_key="...")

# GOOD: explicit profile for local dev only
session = boto3.Session(profile_name="dev")
s3 = session.client("s3")
```

```typescript
// TypeScript — SDK v3 uses same chain automatically
import { S3Client } from "@aws-sdk/client-s3";

const s3 = new S3Client({ region: "us-east-1" });  // no credentials needed

// Local dev with named profile
import { fromIni } from "@aws-sdk/credential-providers";
const s3 = new S3Client({
  region: "us-east-1",
  credentials: fromIni({ profile: "dev" }),
});
```

### IAM Role Decision Matrix

| Environment | Auth method | How to set up |
|---|---|---|
| Local dev | Named profile (`~/.aws/credentials`) | `aws configure --profile dev` |
| GitHub Actions | OIDC + IAM role (no long-lived keys) | `aws-actions/configure-aws-credentials` with `role-to-assume` |
| Lambda | Execution role (auto-injected) | Attach IAM role to function in console/IaC |
| ECS / Fargate | Task role | `taskRoleArn` in task definition |
| EC2 | Instance profile | Attach IAM role to instance |
| Local → assume role | `AWS_PROFILE` + role ARN | Add `role_arn` to `~/.aws/config` |

## Configuration

```python
from pydantic_settings import BaseSettings

class AWSSettings(BaseSettings):
    aws_region: str = "us-east-1"
    s3_bucket: str
    dynamodb_table: str
    sqs_queue_url: str
    secrets_manager_prefix: str = "/myapp/prod"

    class Config:
        env_file = ".env"

settings = AWSSettings()
```

Never store `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` in `.env` files committed to source control.

## S3

### Upload and Download

```python
import boto3
from botocore.exceptions import ClientError

s3 = boto3.client("s3", region_name="us-east-1")

def upload_object(bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
    return f"s3://{bucket}/{key}"

def download_object(bucket: str, key: str) -> bytes:
    response = s3.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()

def list_objects(bucket: str, prefix: str = "") -> list[str]:
    paginator = s3.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        keys.extend(obj["Key"] for obj in page.get("Contents", []))
    return keys
```

```typescript
import { S3Client, PutObjectCommand, GetObjectCommand } from "@aws-sdk/client-s3";
import { Readable } from "stream";

const s3 = new S3Client({ region: "us-east-1" });

async function uploadObject(bucket: string, key: string, body: Buffer, contentType: string) {
  await s3.send(new PutObjectCommand({ Bucket: bucket, Key: key, Body: body, ContentType: contentType }));
  return `s3://${bucket}/${key}`;
}

async function downloadObject(bucket: string, key: string): Promise<Buffer> {
  const res = await s3.send(new GetObjectCommand({ Bucket: bucket, Key: key }));
  return Buffer.from(await res.Body!.transformToByteArray());
}
```

### Presigned URLs

```python
from datetime import timedelta

def get_presigned_url(bucket: str, key: str, expiry_seconds: int = 3600) -> str:
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expiry_seconds,
    )

def get_presigned_upload_url(bucket: str, key: str, content_type: str, expiry_seconds: int = 900) -> str:
    return s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
        ExpiresIn=expiry_seconds,
    )
```

### Multipart Upload (files > 100 MB)

```python
import boto3
from boto3.s3.transfer import TransferConfig

s3_resource = boto3.resource("s3")

config = TransferConfig(
    multipart_threshold=100 * 1024 * 1024,   # 100 MB
    multipart_chunksize=50 * 1024 * 1024,    # 50 MB chunks
    max_concurrency=10,
)

def upload_large_file(bucket: str, key: str, file_path: str):
    s3_resource.Object(bucket, key).upload_file(file_path, Config=config)
```

## DynamoDB

### Single-Table Design

```
Table: MyApp
PK           SK                     Attributes
USER#u1      PROFILE                name, email, plan
USER#u1      ORDER#2024-01          status, total
USER#u1      ORDER#2024-02          status, total
ORDER#o1     METADATA               customer_id, created_at
ORDER#o1     ITEM#sku-a             qty, unit_price

GSI1: GSI1PK=customer_id, GSI1SK=created_at → query all orders for a customer
```

Access patterns map to key structure — define all access patterns before writing schema.

### CRUD Operations

```python
import boto3
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal

dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
table = dynamodb.Table("MyApp")

def put_item(item: dict) -> None:
    table.put_item(Item=item)

def get_item(pk: str, sk: str) -> dict | None:
    response = table.get_item(Key={"PK": pk, "SK": sk})
    return response.get("Item")

def query_items(pk: str, sk_prefix: str) -> list[dict]:
    response = table.query(
        KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with(sk_prefix),
    )
    return response["Items"]

def update_item(pk: str, sk: str, updates: dict) -> None:
    expr = "SET " + ", ".join(f"#{k} = :{k}" for k in updates)
    table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression=expr,
        ExpressionAttributeNames={f"#{k}": k for k in updates},
        ExpressionAttributeValues={f":{k}": v for k, v in updates.items()},
    )

def delete_item(pk: str, sk: str) -> None:
    table.delete_item(Key={"PK": pk, "SK": sk})
```

### Batch Operations

```python
def batch_write(items: list[dict]) -> None:
    with table.batch_writer() as batch:  # auto-handles 25-item limit and unprocessed items
        for item in items:
            batch.put_item(Item=item)

def batch_get(keys: list[dict]) -> list[dict]:
    response = dynamodb.meta.client.batch_get_item(
        RequestItems={table.name: {"Keys": keys[:100]}}  # max 100 per call
    )
    return response["Responses"].get(table.name, [])
```

### DynamoDB vs RDS Decision

| Factor | DynamoDB | RDS (Postgres) |
|---|---|---|
| Access patterns | Known, finite, key-based | Ad-hoc queries, complex joins |
| Scale | Millions of req/s, auto-scale | Vertical + read replicas |
| Schema | Flexible, item-level | Strict, table-level |
| Consistency | Eventually consistent (default) | ACID |
| Operational cost | ~Zero ops | Patching, backups, failover |
| Cost model | Pay-per-request or provisioned | Instance hours |

## Lambda

### Handler Patterns

```python
# Python — structured handler with typed events
import json, logging
from typing import Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event: dict, context: Any) -> dict:
    logger.info("invocation", extra={"request_id": context.aws_request_id, "event": event})

    try:
        result = process(event)
        return {"statusCode": 200, "body": json.dumps(result)}
    except ValueError as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}
    except Exception:
        logger.exception("unhandled_error")
        raise  # let Lambda retry / send to DLQ

def process(event: dict) -> dict:
    ...
```

```typescript
// TypeScript — API Gateway proxy event
import { APIGatewayProxyEvent, APIGatewayProxyResult, Context } from "aws-lambda";

export const handler = async (
  event: APIGatewayProxyEvent,
  context: Context,
): Promise<APIGatewayProxyResult> => {
  const body = JSON.parse(event.body ?? "{}");
  try {
    const result = await process(body);
    return { statusCode: 200, body: JSON.stringify(result) };
  } catch (err) {
    console.error({ requestId: context.awsRequestId, err });
    return { statusCode: 500, body: JSON.stringify({ error: "internal error" }) };
  }
};
```

### Lambda Environment Best Practices

```python
import os
import boto3

# Initialize clients outside the handler — reused across warm invocations
_s3 = None
_table = None

def get_s3():
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3")
    return _s3

def get_table():
    global _table
    if _table is None:
        dynamodb = boto3.resource("dynamodb")
        _table = dynamodb.Table(os.environ["DYNAMODB_TABLE"])
    return _table

# Read config from environment, not hardcoded
BUCKET = os.environ["S3_BUCKET"]
REGION = os.environ.get("AWS_REGION", "us-east-1")
```

### Lambda Event Source Comparison

| Trigger | Invocation | Retry behavior | Batch |
|---|---|---|---|
| API Gateway / ALB | Sync | None (caller handles) | No |
| SQS | Async | Redrive to DLQ after maxReceiveCount | Yes (up to 10000) |
| S3 | Async | 2 retries then discard | No (one event per object) |
| DynamoDB Streams | Async | Retry until success or record expires | Yes (per shard) |
| EventBridge | Async | Configurable retry + DLQ | No |
| SNS | Async | 3 retries then DLQ | No |

## SQS

### Send and Receive

```python
sqs = boto3.client("sqs", region_name="us-east-1")
QUEUE_URL = os.environ["SQS_QUEUE_URL"]

def send_message(body: dict, deduplication_id: str | None = None) -> str:
    params = {"QueueUrl": QUEUE_URL, "MessageBody": json.dumps(body)}
    if deduplication_id:  # required for FIFO queues
        params["MessageDeduplicationId"] = deduplication_id
        params["MessageGroupId"] = body.get("group_id", "default")
    response = sqs.send_message(**params)
    return response["MessageId"]

def send_batch(messages: list[dict]) -> None:
    entries = [
        {"Id": str(i), "MessageBody": json.dumps(msg)}
        for i, msg in enumerate(messages[:10])  # max 10 per batch
    ]
    response = sqs.send_message_batch(QueueUrl=QUEUE_URL, Entries=entries)
    if response.get("Failed"):
        raise RuntimeError(f"batch send failed: {response['Failed']}")
```

### Lambda SQS Consumer with Partial Batch Failure

```python
def handler(event: dict, context: Any) -> dict:
    batch_item_failures = []

    for record in event["Records"]:
        message_id = record["messageId"]
        try:
            body = json.loads(record["body"])
            process_message(body)
        except Exception:
            logger.exception("message_failed", extra={"message_id": message_id})
            batch_item_failures.append({"itemIdentifier": message_id})

    # Return only failed IDs — SQS retries these, deletes the rest
    return {"batchItemFailures": batch_item_failures}
```

Enable **partial batch failure** (`FunctionResponseTypes: [ReportBatchItemFailures]`) in the event source mapping — otherwise one failure requeues the entire batch.

## Secrets Manager

```python
import json
import boto3
from functools import lru_cache

_sm = boto3.client("secretsmanager", region_name="us-east-1")

@lru_cache(maxsize=None)  # cache per Lambda warm instance
def get_secret(secret_name: str) -> dict:
    response = _sm.get_secret_value(SecretId=secret_name)
    raw = response.get("SecretString") or response["SecretBinary"].decode()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"value": raw}

# Usage
db_creds = get_secret("/myapp/prod/db")
password = db_creds["password"]
```

### Secrets Manager vs Parameter Store

| Factor | Secrets Manager | Parameter Store (SSM) |
|---|---|---|
| Secret rotation | Built-in (Lambda-based) | Manual |
| Versioning | Yes | Yes |
| Cost | $0.40/secret/month | Free (standard), $0.05/10K API calls advanced |
| Size limit | 64 KB | 4 KB (standard), 8 KB (advanced) |
| Best for | DB passwords, API keys, rotation | Config values, feature flags, non-sensitive config |

```python
# Parameter Store (cheaper for non-secrets)
ssm = boto3.client("ssm")

def get_parameter(name: str, with_decryption: bool = True) -> str:
    response = ssm.get_parameter(Name=name, WithDecryption=with_decryption)
    return response["Parameter"]["Value"]
```

## Retry and Error Handling

### botocore Retry Config

```python
from botocore.config import Config

retry_config = Config(
    retries={
        "max_attempts": 5,
        "mode": "adaptive",   # adaptive > standard > legacy; backs off on throttle
    },
    connect_timeout=5,
    read_timeout=30,
)

s3 = boto3.client("s3", config=retry_config)
dynamodb = boto3.client("dynamodb", config=retry_config)
```

### ClientError Handling

```python
from botocore.exceptions import ClientError, NoCredentialsError

def safe_get_object(bucket: str, key: str) -> bytes | None:
    try:
        return s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    except ClientError as e:
        code = e.response["Error"]["Code"]
        match code:
            case "NoSuchKey" | "404":
                return None
            case "AccessDenied" | "403":
                logger.error("s3_access_denied", bucket=bucket, key=key)
                raise
            case "ThrottlingException" | "RequestLimitExceeded" | "SlowDown":
                raise  # botocore retry handles this
            case _:
                logger.error("s3_error", code=code, bucket=bucket, key=key)
                raise
    except NoCredentialsError:
        logger.critical("no_aws_credentials")
        raise
```

### Common Error Codes

| Service | Error Code | Meaning |
|---|---|---|
| S3 | `NoSuchKey` | Object doesn't exist |
| S3 | `NoSuchBucket` | Bucket doesn't exist or no access |
| DynamoDB | `ConditionalCheckFailedException` | Optimistic lock / condition failed |
| DynamoDB | `ProvisionedThroughputExceededException` | Throttled — retry with backoff |
| DynamoDB | `ResourceNotFoundException` | Table doesn't exist |
| Secrets Manager | `ResourceNotFoundException` | Secret not found |
| All | `AccessDeniedException` | IAM permissions missing |
| All | `ThrottlingException` | Rate limited — botocore retries |

## IAM Least Privilege

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::my-bucket/uploads/*"
    },
    {
      "Effect": "Allow",
      "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query", "dynamodb:UpdateItem"],
      "Resource": [
        "arn:aws:dynamodb:us-east-1:123456789012:table/MyApp",
        "arn:aws:dynamodb:us-east-1:123456789012:table/MyApp/index/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "arn:aws:secretsmanager:us-east-1:123456789012:secret:/myapp/prod/*"
    }
  ]
}
```

```
# BAD: wildcard on resource
"Action": "s3:*", "Resource": "*"

# BAD: admin permissions for app role
"Action": "*", "Resource": "*"

# GOOD: specific actions, specific ARNs with path constraints
```

## Cost Controls

| Lever | Impact | How |
|---|---|---|
| DynamoDB on-demand vs provisioned | High | On-demand for unpredictable traffic; provisioned + auto-scaling for steady workloads |
| S3 storage classes | Medium | Lifecycle policy: `Standard` → `Standard-IA` after 30d → `Glacier` after 90d |
| Lambda memory sizing | Medium | Profile with Lambda Power Tuning; more memory often runs faster and costs less |
| DynamoDB DAX cache | Medium | Cache read-heavy tables; reduces read capacity units |
| S3 request costs | Low-medium | Use CloudFront in front of S3 for high-volume GET patterns |
| Secrets Manager calls | Low | Cache secrets in Lambda warm instance; don't call on every invocation |
| CloudWatch Logs retention | Low | Set retention (7–30d) — default is forever |

> See also: `event-driven`, `caching`, `observability`

## Checklist

- [ ] All SDK clients use the credential chain — no hardcoded `aws_access_key_id` or `aws_secret_access_key`
- [ ] Lambda, ECS tasks, and EC2 instances use IAM roles/profiles — no long-lived keys in env vars
- [ ] IAM policies follow least privilege: specific actions, specific resource ARNs
- [ ] GitHub Actions uses OIDC role assumption — no IAM user keys stored as secrets
- [ ] boto3/SDK clients initialized outside Lambda handler (reused on warm invocations)
- [ ] botocore retry config set to `adaptive` mode with `max_attempts=5`
- [ ] `ClientError` caught and branched by error code — not caught and swallowed
- [ ] SQS Lambda consumer returns `batchItemFailures` for partial batch failure
- [ ] DynamoDB access patterns defined before schema — table designed around queries
- [ ] S3 lifecycle policy configured for infrequently accessed data
- [ ] Secrets retrieved from Secrets Manager or Parameter Store — not environment variables
- [ ] CloudWatch Logs retention period set on all log groups
