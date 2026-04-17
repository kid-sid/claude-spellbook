---
name: azure
description: Azure SDK patterns for Python covering authentication with DefaultAzureCredential, Blob Storage, AI Search (vector + hybrid), Document Intelligence, Key Vault secrets, Azure Functions, and cost controls.
---

# Azure SDK

Production patterns for Azure services in Python using the official Azure SDKs.

## When to Activate

- Writing code that imports `azure-storage-blob`, `azure-search-documents`, `azure-ai-formrecognizer`, or `azure-identity`
- Configuring authentication for Azure services (Managed Identity, service principals, connection strings)
- Designing or querying an Azure AI Search index (vector, text, hybrid)
- Extracting content from documents using Azure Document Intelligence
- Managing secrets with Azure Key Vault
- Deploying a pipeline as an Azure Function
- Troubleshooting Azure SDK errors or retry behavior

## Authentication

### DefaultAzureCredential (always prefer this)

```python
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

credential = DefaultAzureCredential()
client = BlobServiceClient(account_url="https://<account>.blob.core.windows.net", credential=credential)
```

`DefaultAzureCredential` tries, in order: environment variables → Managed Identity → Azure CLI → VS Code → Interactive browser. The same code works locally (via CLI auth) and in production (via Managed Identity) without changes.

```python
# BAD: connection string hardcoded
client = BlobServiceClient.from_connection_string("DefaultEndpointsProtocol=https;AccountName=...")

# BAD: key hardcoded
client = BlobServiceClient(account_url=url, credential="storage-account-key-here")

# GOOD: keyless auth
credential = DefaultAzureCredential()
client = BlobServiceClient(account_url=url, credential=credential)
```

### Auth decision matrix

| Environment | Credential type | How to enable |
|---|---|---|
| Local dev | Azure CLI | `az login` |
| CI/CD | Service principal (env vars) | Set `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID` |
| Azure VM / AKS | System-assigned Managed Identity | Enable on the resource in portal/Bicep |
| Azure Functions | User-assigned Managed Identity | Set `AZURE_CLIENT_ID` env var |
| Testing | `ClientSecretCredential` | Explicit — never use in production code |

## Configuration (pydantic-settings)

```python
from pydantic_settings import BaseSettings

class AzureSettings(BaseSettings):
    azure_storage_account_url: str
    azure_search_endpoint: str
    azure_search_index_name: str
    azure_document_intelligence_endpoint: str
    azure_key_vault_url: str | None = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = AzureSettings()
```

Never store credentials in settings — let `DefaultAzureCredential` handle them.

## Azure Blob Storage

### Upload

```python
from azure.storage.blob import BlobServiceClient, ContentSettings

def upload_file(account_url: str, container: str, blob_name: str, data: bytes, content_type: str) -> str:
    credential = DefaultAzureCredential()
    client = BlobServiceClient(account_url=account_url, credential=credential)
    blob = client.get_blob_client(container=container, blob=blob_name)
    blob.upload_blob(
        data,
        overwrite=True,
        content_settings=ContentSettings(content_type=content_type),
    )
    return blob.url
```

### Download and list

```python
def download_blob(account_url: str, container: str, blob_name: str) -> bytes:
    client = BlobServiceClient(account_url=account_url, credential=DefaultAzureCredential())
    blob = client.get_blob_client(container=container, blob=blob_name)
    return blob.download_blob().readall()

def list_blobs(account_url: str, container: str, prefix: str = "") -> list[str]:
    client = BlobServiceClient(account_url=account_url, credential=DefaultAzureCredential())
    container_client = client.get_container_client(container)
    return [b.name for b in container_client.list_blobs(name_starts_with=prefix)]
```

### SAS token (time-limited read access)

```python
from datetime import datetime, timedelta, timezone
from azure.storage.blob import generate_blob_sas, BlobSasPermissions

def get_sas_url(account_name: str, account_key: str, container: str, blob: str, expiry_hours: int = 1) -> str:
    sas = generate_blob_sas(
        account_name=account_name,
        container_name=container,
        blob_name=blob,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.now(timezone.utc) + timedelta(hours=expiry_hours),
    )
    return f"https://{account_name}.blob.core.windows.net/{container}/{blob}?{sas}"
```

## Azure AI Search

### Index schema (with vector field)

```python
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SimpleField, SearchableField, SearchFieldDataType,
    VectorSearch, HnswAlgorithmConfiguration, VectorSearchProfile,
    SearchField, SemanticConfiguration, SemanticSearch, SemanticPrioritizedFields,
    SemanticField,
)

def create_index(endpoint: str, index_name: str) -> None:
    client = SearchIndexClient(endpoint=endpoint, credential=DefaultAzureCredential())
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SearchableField(name="title", type=SearchFieldDataType.String),
        SimpleField(name="source", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="chunk_index", type=SearchFieldDataType.Int32, filterable=True),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=1536,
            vector_search_profile_name="hnsw-profile",
        ),
    ]
    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="hnsw")],
        profiles=[VectorSearchProfile(name="hnsw-profile", algorithm_configuration_name="hnsw")],
    )
    semantic_search = SemanticSearch(
        configurations=[
            SemanticConfiguration(
                name="default",
                prioritized_fields=SemanticPrioritizedFields(
                    content_fields=[SemanticField(field_name="content")],
                    title_field=SemanticField(field_name="title"),
                ),
            )
        ]
    )
    index = SearchIndex(
        name=index_name,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search,
    )
    client.create_or_update_index(index)
```

### Upload documents

```python
from azure.search.documents import SearchClient

def upload_documents(endpoint: str, index_name: str, docs: list[dict]) -> None:
    client = SearchClient(
        endpoint=endpoint,
        index_name=index_name,
        credential=DefaultAzureCredential(),
    )
    # Batch in chunks of 1000 (SDK limit)
    for i in range(0, len(docs), 1000):
        result = client.upload_documents(documents=docs[i:i + 1000])
        failed = [r for r in result if not r.succeeded]
        if failed:
            raise RuntimeError(f"{len(failed)} documents failed to index: {failed[0].key}")
```

### Search: text / vector / hybrid

```python
from azure.search.documents.models import VectorizedQuery

def search(
    endpoint: str,
    index_name: str,
    query: str,
    query_vector: list[float],
    top: int = 5,
    mode: str = "hybrid",  # "text" | "vector" | "hybrid"
    filter_expr: str | None = None,
) -> list[dict]:
    client = SearchClient(endpoint=endpoint, index_name=index_name, credential=DefaultAzureCredential())

    vector_query = VectorizedQuery(
        vector=query_vector,
        k_nearest_neighbors=top,
        fields="content_vector",
    ) if mode in ("vector", "hybrid") else None

    results = client.search(
        search_text=query if mode in ("text", "hybrid") else None,
        vector_queries=[vector_query] if vector_query else None,
        filter=filter_expr,
        top=top,
        query_type="semantic" if mode == "hybrid" else "simple",
        semantic_configuration_name="default" if mode == "hybrid" else None,
    )
    return [dict(r) for r in results]
```

### Search mode comparison

| Mode | When to use | Relevance | Cost |
|---|---|---|---|
| Text | Keyword lookup, exact matches | Low | Lowest |
| Vector | Semantic similarity, paraphrase | High | Medium |
| Hybrid | Production RAG (default choice) | Highest | Medium |
| Semantic reranking | High-precision Q&A on top of hybrid | Highest | Higher |

## Azure Document Intelligence

```python
from azure.ai-formrecognizer import DocumentAnalysisClient

def analyze_document(endpoint: str, file_bytes: bytes, model_id: str = "prebuilt-read") -> dict:
    client = DocumentAnalysisClient(endpoint=endpoint, credential=DefaultAzureCredential())
    poller = client.begin_analyze_document(model_id, document=file_bytes)
    result = poller.result()
    return {
        "content": result.content,
        "pages": len(result.pages),
        "tables": [
            {
                "row_count": t.row_count,
                "column_count": t.column_count,
                "cells": [{"row": c.row_index, "col": c.column_index, "text": c.content} for c in t.cells],
            }
            for t in (result.tables or [])
        ],
    }
```

### Model selection

| Model ID | Best for |
|---|---|
| `prebuilt-read` | Text extraction from any document |
| `prebuilt-layout` | Tables, checkboxes, structure-aware extraction |
| `prebuilt-document` | Key-value pairs + tables |
| `prebuilt-invoice` | Invoices |
| `prebuilt-receipt` | Receipts |
| Custom model | Domain-specific forms with consistent layout |

## Key Vault

```python
from azure.keyvault.secrets import SecretClient

def get_secret(vault_url: str, secret_name: str) -> str:
    client = SecretClient(vault_url=vault_url, credential=DefaultAzureCredential())
    return client.get_secret(secret_name).value

# Cache the client — don't recreate per call
_kv_client: SecretClient | None = None

def kv_client(vault_url: str) -> SecretClient:
    global _kv_client
    if _kv_client is None:
        _kv_client = SecretClient(vault_url=vault_url, credential=DefaultAzureCredential())
    return _kv_client
```

## Retry with tenacity

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from azure.core.exceptions import HttpResponseError, ServiceRequestError

def is_retryable(exc: Exception) -> bool:
    if isinstance(exc, HttpResponseError):
        return exc.status_code in (429, 500, 502, 503, 504)
    return isinstance(exc, ServiceRequestError)

@retry(
    retry=retry_if_exception_type((HttpResponseError, ServiceRequestError)),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
def upload_with_retry(client: SearchClient, docs: list[dict]) -> None:
    client.upload_documents(documents=docs)
```

## Error handling

```python
from azure.core.exceptions import (
    HttpResponseError,
    ResourceNotFoundError,
    ResourceExistsError,
    ClientAuthenticationError,
    ServiceRequestError,
)

try:
    result = client.get_document(key="doc-123")
except ResourceNotFoundError:
    # Document does not exist — handle gracefully
    return None
except ClientAuthenticationError:
    # Credential expired or RBAC role missing — fail fast
    raise
except HttpResponseError as e:
    if e.status_code == 429:
        # Throttled — tenacity will handle retry
        raise
    logger.error("azure_error", status=e.status_code, message=e.message)
    raise
```

## Cost controls

| Lever | Impact | How |
|---|---|---|
| AI Search tier | High | `Basic` for dev, `Standard S1` for prod; avoid `S3 HD` unless >1B docs |
| Semantic reranking | Medium | Enable only on queries that need it; billed per 1000 queries |
| Document Intelligence | Medium | Use `prebuilt-read` (cheapest) unless you need tables or KV pairs |
| Blob storage tier | Low-medium | `Hot` for active docs, `Cool` for archive; lifecycle policies auto-tier |
| Vector dimensions | Medium | 1536 (ada-002) vs 3072 (text-embedding-3-large) — smaller = cheaper storage |

## Checklist

- [ ] All SDK clients use `DefaultAzureCredential` — no hardcoded keys or connection strings
- [ ] Managed Identity enabled on compute (Function App, VM, AKS node pool)
- [ ] RBAC roles assigned (`Storage Blob Data Contributor`, `Search Index Data Contributor`, etc.) — not access keys
- [ ] Secrets stored in Key Vault, not env vars or config files
- [ ] All long-running SDK calls wrapped with tenacity retry on 429/5xx
- [ ] Document upload batched in chunks of ≤1000 for Azure AI Search
- [ ] Index schema reviewed: filterable/sortable fields declared explicitly
- [ ] Hybrid search enabled for RAG queries (not text-only)
- [ ] Blob lifecycle policy configured to auto-tier cold data to `Cool`/`Archive`
- [ ] `ClientAuthenticationError` caught and surfaced immediately (not retried)
- [ ] SDK client instances reused per process — not recreated per request
- [ ] Azure resource names follow naming convention (`<service>-<env>-<region>-<suffix>`)
