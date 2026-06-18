# N8N WORKFLOWS

## Overview

This document describes the n8n automation workflows for Phase 3. Each workflow is stored as a JSON file under `src/automation/n8n/workflows/` and can be imported directly into n8n.

## Authentication

All n8n workflows use the `X-Internal-Key` header for API authentication. The key is stored in n8n credentials and passed to each HTTP Request node.

---

## Workflow 1: Daily Branch Report

**File:** `src/automation/n8n/workflows/daily_branch_report.json`

### Purpose
Automatically generate and distribute daily branch reports every morning.

### Flow
```
Cron Trigger (8:00 AM daily)
  → HTTP Request: POST /api/v1/reports/daily
  → IF (success)
      → Format Report (Code node)
      → Send Email (SMTP)
      → Send Slack Message (optional)
  → IF (failure)
      → Send Alert to Ops Channel
```

### API Contract
```json
// Request
POST /api/v1/reports/daily
{
  "date": "2025-01-15",
  "branch_id": null,
  "include_comparison": true
}

// Response
{
  "date": "2025-01-15",
  "branches": [{"branch_id": "1", "total_sales": 45000, ...}],
  "summary": {"total_sales": 45000, "total_orders": 120}
}
```

---

## Workflow 2: WhatsApp CX Agent

**File:** `src/automation/n8n/workflows/whatsapp_cx_agent.json`

### Purpose
Handle incoming WhatsApp messages as customer service inquiries via the CX Agent.

### Flow
```
WhatsApp Trigger (incoming message)
  → Extract Customer Info
  → HTTP Request: POST /api/v1/chat
  → Format Response
  → Reply via WhatsApp
```

### API Contract
```json
// Request
POST /api/v1/chat
{
  "query": "أين طلبي رقم 12345؟",
  "channel": "whatsapp",
  "metadata": {"customer_phone": "+966501234567"}
}

// Response
{
  "response": "طلبك رقم 12345 قيد التوصيل...",
  "intent": "cx",
  "agent": "cx",
  "tools_used": ["order_lookup"],
  "sources": ["order:12345"]
}
```

---

## Workflow 3: Low Stock Alert

**File:** `src/automation/n8n/workflows/low_stock_alert.json`

### Purpose
Monitor inventory levels and send alerts when stock falls below thresholds.

### Flow
```
Schedule Trigger (every 2 hours)
  → HTTP Request: POST /api/v1/inventory/low-stock
  → Filter Low Stock Items
  → IF (low_stock_exists)
      → Format Alert
      → Send Email to Procurement
      → Send Slack Alert
```

### API Contract
```json
// Request
POST /api/v1/inventory/low-stock
{
  "threshold": 10.0
}

// Response
{
  "threshold": 10.0,
  "low_stock_count": 3,
  "items": [{"product_id": "P001", "quantity_available": 5.0, ...}]
}
```

---

## Workflow 4: CX Ticket Escalation (NEW)

### Purpose
When CX Agent detects a complex issue, escalate to a human agent via ticket creation.

### Flow
```
Webhook Trigger (from /chat response)
  → IF response.tools_used contains "create_ticket"
      → Send notification to support team
      → Log to database
```

---

## Common Request/Response Patterns

### Authentication
All requests must include:
```
X-Internal-Key: <your-internal-api-key>
Content-Type: application/json
```

### Error Handling
All endpoints return consistent error format:
```json
{
  "error": {
    "code": "AGENT_ERROR",
    "message": "Failed to process request",
    "details": {"error": "..."}
  }
}
```

### n8n HTTP Request Node Configuration
| Field | Value |
|-------|-------|
| Method | POST |
| URL | `{{ $env.API_BASE_URL }}/api/v1/chat` |
| Headers | `X-Internal-Key: {{ $env.INTERNAL_API_KEY }}` |
| Body | JSON |

---

## Environment Variables for n8n

| Variable | Description | Example |
|----------|-------------|---------|
| `API_BASE_URL` | FastAPI base URL | `http://localhost:8000` |
| `INTERNAL_API_KEY` | API authentication key | `test-key-123` |
| `SMTP_FROM` | Sender email | `reports@company.com` |
| `REPORT_EMAIL` | Report recipient | `ops@company.com` |
| `SLACK_CHANNEL` | Slack channel for reports | `#daily-reports` |
| `PROCUREMENT_EMAIL` | Low stock alerts | `procurement@company.com` |
