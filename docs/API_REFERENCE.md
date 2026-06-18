# API REFERENCE

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

| Header | Type | Required | Description |
|--------|------|----------|-------------|
| `X-Internal-Key` | string | Yes (n8n) | Internal API key for n8n workflows |

---

## POST /chat

Supervisor entry point. Classifies intent and routes to appropriate agent.

### Request

```json
{
  "query": "ما هي مبيعات فرع الرياض اليوم؟",
  "channel": "web",
  "metadata": {
    "user_id": "optional-user-id",
    "session_id": "optional-session-id"
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | User query text (1-5000 chars) |
| `channel` | string | No | Origin: web, whatsapp, api, n8n (default: "web") |
| `metadata` | object | No | Additional context (user_id, session_id, etc.) |

### Response

```json
{
  "response": "مبيعات فرع الرياض اليوم هي 45,000 ريال...",
  "intent": "analytics",
  "agent": "analytical",
  "tools_used": ["analytics_service", "odoo_data"],
  "sources": [],
  "processing_time_ms": 1250.42,
  "metadata": {
    "channel": "web",
    "model": "llama-3.3-70b-versatile"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `response` | string | Agent response text |
| `intent` | string | Classified: analytics, cx, internal_ops, general |
| `agent` | string \| null | Which agent handled: analytical, cx, internal_ops, general |
| `tools_used` | string[] | Tools invoked during processing |
| `sources` | string[] | Source references (doc:xxx, order:xxx, customer:xxx) |
| `processing_time_ms` | float | Total processing time |
| `metadata` | object | Response metadata |

### Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 422 | Validation error |
| 500 | Agent processing failed |
| 503 | Agent system not initialized |

### Examples

**Analytics query:**
```json
{"query": "قارن مبيعات الفروع الثلاثة", "channel": "web"}
// → intent: "analytics", agent: "analytical"
```

**CX query:**
```json
{"query": "أين طلبي رقم 12345؟", "channel": "whatsapp"}
// → intent: "cx", agent: "cx", sources: ["order:12345"]
```

**Policy query:**
```json
{"query": "ما هي سياسة الإرجاع؟", "channel": "api"}
// → intent: "cx", agent: "cx", sources: ["doc:xxx"]
```

---

## POST /reports/daily

Get daily branch reports.

### Request
```json
{
  "date": "2025-01-15",
  "branch_id": "optional-branch-filter",
  "include_comparison": true
}
```

### Response
```json
{
  "date": "2025-01-15",
  "branches": [
    {
      "branch_id": "1",
      "branch_name": "Branch 1",
      "total_sales": 45000.00,
      "order_count": 120,
      "avg_order_value": 375.00,
      "top_products": []
    }
  ],
  "summary": {
    "total_sales": 45000.00,
    "total_orders": 120
  }
}
```

---

## POST /kpis/branches

Get branch KPIs.

### Request
```json
{
  "branch_ids": ["1", "2"],
  "period": "monthly",
  "start_date": "2025-01-01",
  "end_date": "2025-01-31"
}
```

### Response
```json
{
  "kpis": [
    {
      "branch_id": "1",
      "branch_name": "Branch 1",
      "metrics": {
        "total_revenue": 1500000.00,
        "total_orders": 4200,
        "avg_order_value": 357.14,
        "inventory_turnover": null,
        "customer_satisfaction": null,
        "return_rate": null
      },
      "trends": {
        "revenue_growth_pct": null,
        "order_growth_pct": null
      }
    }
  ],
  "period": "monthly",
  "date_range": {"start": "2025-01-01", "end": "2025-01-31"}
}
```

---

## POST /inventory/low-stock

Check for low stock items.

### Request
```json
{"threshold": 10.0}
```

### Response
```json
{
  "threshold": 10.0,
  "low_stock_count": 3,
  "items": [
    {"product_id": "P001", "product_name": "Product A", "branch_id": "BR001", "quantity_available": 5.0}
  ]
}
```

---

## POST /internal/summarize

Upload and summarize a report document.

### Request
```
Content-Type: multipart/form-data

file: (PDF or Excel file)
summary_type: "full" | "kpi_extraction" | "task_generation"
language: "ar" | "en"
```

### Response
```json
{
  "document_id": "doc_abc123",
  "filename": "report.pdf",
  "summary": "Ingested 15 chunks from report.pdf",
  "kpis": [],
  "tasks": [],
  "stored_in_qdrant": true,
  "chunk_count": 15
}
```

---

## GET /health

Health check endpoint.

### Response
```json
{
  "status": "healthy",
  "services": {
    "qdrant": "connected",
    "odoo": "connected",
    "llm": "available"
  },
  "version": "0.1.0"
}
```

## Error Responses

```json
{
  "error": {
    "code": "AGENT_ERROR",
    "message": "Failed to process chat request",
    "details": {"error": "..."}
  }
}
```
