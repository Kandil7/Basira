# DATA SOURCES

## Odoo ERP (Read-Only)

All Odoo access is read-only via XML-RPC. The system never writes to Odoo in Phase 1.

### Connection
```python
# Infrastructure: src/infrastructure/data/odoo_client.py
# Interface: src/domain/interfaces/odoo_client.py
```

### Repositories

| Repository | File | Purpose | Key Methods |
|-----------|------|---------|-------------|
| `SalesRepository` | `repositories/sales_repository.py` | Sales order queries | `get_daily_sales()`, `get_sales_range()` |
| `InventoryRepository` | `repositories/inventory_repository.py` | Stock level queries | `get_stock_levels()`, `get_low_stock_items()` |
| `CustomerRepository` | `repositories/customers_repository.py` | Customer/partner queries | `get_customer()`, `get_customer_orders()` |

### Data Models Accessed

| Odoo Model | Purpose | Used By |
|------------|---------|---------|
| `sale.order` | Sales orders, amounts, dates | Analytical Agent, CX Agent |
| `sale.order.line` | Line items, products | Analytical Agent |
| `stock.quant` | Inventory quantities | Analytical Agent, InventoryRepository |
| `stock.warehouse` | Warehouse/branch mapping | Analytical Agent, CustomerRepository |
| `res.partner` | Customers, branches | CX Agent, CustomerRepository |
| `product.product` | Product catalog | Analytical Agent, CX Agent |
| `helpdesk.ticket` | Support tickets | CX Agent |

### Read-Only Operations
- `search_read()` — Search and read records
- `read()` — Read specific records by ID
- `fields_get()` — Get field metadata

### Authentication
XML-RPC authentication via username/password. Credentials stored in environment variables.

---

## Qdrant Vector Store

### Collections

| Collection | Content | Used By |
|------------|---------|---------|
| `company_docs` | Policies, SOPs, FAQs | CX Agent, Internal Ops Agent |
| `reports` | Summarized reports | Internal Ops Agent, Analytical Agent |
| `chat_history` | Conversation embeddings | All agents (context) |

### Connection
```python
# Infrastructure: src/infrastructure/rag/vectorstore.py
# Interface: src/domain/interfaces/vector_store.py
```

### Embedding Configuration
- **Phase 1**: Placeholder hash-based vectors (no external embedding API)
- **Production**: Voyage AI / Jina / local model (1536 dimensions)
- Distance: Cosine similarity

### Document Ingestion
```python
# Ingest pipeline: src/infrastructure/rag/ingest/__init__.py
# Chunking utils: src/infrastructure/rag/ingest/chunking.py
```

Documents are chunked before storage:
- **Chunk size**: 1000 characters
- **Chunk overlap**: 200 characters
- **Metadata**: source file, page number, section, timestamp

### RAG Retriever
```python
# src/infrastructure/rag/retriever.py
# Wraps QdrantVectorStore for semantic search
# Methods: retrieve(), retrieve_with_context()
```

---

## n8n Automation

n8n consumes the FastAPI endpoints. It is NOT a data source but an automation orchestrator.

### API Endpoints for n8n
| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/reports/daily` | Daily branch reports |
| `POST /api/v1/chat` | CX intent routing |
| `POST /api/v1/internal/summarize` | Report summarization |
| `POST /api/v1/kpis/branches` | Branch KPIs |

### Authentication
n8n uses `X-Internal-Key` header for API authentication.

---

## Environment Variables

| Variable | Source | Description |
|----------|--------|-------------|
| `ODOO_URL` | Odoo | ERP instance URL |
| `ODOO_DB` | Odoo | Database name |
| `ODOO_USERNAME` | Odoo | API user |
| `ODOO_PASSWORD` | Odoo | API password |
| `QDRANT_HOST` | Qdrant | Vector store host |
| `QDRANT_PORT` | Qdrant | Vector store port |
| `QDRANT_COLLECTION` | Qdrant | Default collection name |
| `GROQ_API_KEY` | Groq (groq.com) | LLM API key |
| `GROQ_MODEL` | Groq | Model to use (default: llama-3.3-70b-versatile) |
| `GROQ_BASE_URL` | Groq | API base URL |
| `N8N_WEBHOOK_BASE` | n8n | n8n webhook base URL |
| `N8N_API_KEY` | n8n | n8n API authentication |
