# AGENTS

## Agent Architecture

All agents are implemented as LangGraph nodes within a supervisor graph. The supervisor classifies user intent via Groq LLM and routes to the appropriate agent node.

### Graph Construction

```python
from src.agents.builder import build_graph
from src.agents.state import create_initial_state

graph = build_graph(settings, analytics_svc, cx_svc, doc_svc, retriever)
result = await graph.ainvoke(create_initial_state("ما هي مبيعات اليوم؟"))
```

### Supervisor Graph

```
START → supervisor (classify via Groq LLM)
          ├─ analytics    → analytical_agent → END
          ├─ cx           → cx_agent → END
          ├─ internal_ops → internal_ops_agent → END
          └─ general      → general_agent → END
```

---

## 1. Analytical Agent (Priority: Top)

### Purpose
Analyze sales, inventory, and branch performance data from Odoo. Answer Arabic natural language questions and generate recommendations.

### Prompt
Loaded from `src/agents/prompts/analytical_prompt.txt`.

### Tools Used
| Tool | Description | Data Source |
|------|-------------|-------------|
| `get_daily_sales` | Fetch daily sales by branch/date | Odoo (sale.order) |
| `get_inventory_status` | Current stock levels | Odoo (stock.quant) |
| `get_branch_kpis` | KPIs per branch | Odoo (computed) |

### State Fields Set
- `agent`: "analytical"
- `tools_used`: ["analytics_service", "odoo_data"]

### Endpoints
- `POST /api/v1/reports/daily` — Get daily branch reports
- `POST /api/v1/kpis/branches` — Get branch KPIs
- Routed via `/chat` when intent = "analytics"

### Example
```json
// Request
{"query": "ما هي مبيعات فرع الرياض اليوم؟", "channel": "web"}

// Response
{
  "response": "مبيعات فرع الرياض اليوم هي 45,000 ريال...",
  "intent": "analytics",
  "agent": "analytical",
  "tools_used": ["analytics_service", "odoo_data"],
  "sources": [],
  "processing_time_ms": 1250
}
```

---

## 2. Customer Service (CX) Agent (Priority: High)

### Purpose
Answer customer inquiries about orders, branches, company policies. Supports multi-channel deployment via n8n.

### Prompt
Loaded from `src/agents/prompts/cx_prompt.txt`.

### Tools Available
| Tool | Description | Data Source |
|------|-------------|-------------|
| `get_order_status` | Order tracking info | Odoo (sale.order) |
| `get_customer_info` | Customer details by ID/phone | Odoo (res.partner) |
| `create_ticket` | Create a support ticket | Odoo (helpdesk.ticket) |
| `lookup_policy` | Search company FAQ/policies | Qdrant (RAG) |
| `search_faq` | Alias for `lookup_policy` | Qdrant (RAG) |

### State Fields Set
- `agent`: "cx"
- `tools_used`: ["rag_retrieval", "order_lookup", "customer_lookup"]
- `sources`: ["doc:xxx", "order:123", "customer:456"]

### Channel Support
- **Web Chat API**: Internal endpoint consumed by n8n
- **WhatsApp**: Via n8n WhatsApp trigger → `/chat` with CX intent

### Example
```json
// Request
{"query": "أين طلبي رقم 12345؟", "channel": "whatsapp", "metadata": {"customer_phone": "+966501234567"}}

// Response
{
  "response": "طلبك رقم 12345 قيد التوصيل حالياً...",
  "intent": "cx",
  "agent": "cx",
  "tools_used": ["order_lookup"],
  "sources": ["order:12345"],
  "processing_time_ms": 980
}
```

---

## 3. Internal Ops Agent (Priority: Medium)

### Purpose
Summarize uploaded reports (PDF/Excel), extract KPIs, and generate task lists for operations teams.

### Prompt
Loaded from `src/agents/prompts/internal_ops_prompt.txt`.

### Tools Used
| Tool | Description | Data Source |
|------|-------------|-------------|
| `summarize_document` | Summarize PDF/Excel content | Uploaded file |
| `extract_kpis` | Extract key metrics | LLM + parsing |
| `document_retrieval` | Search stored reports | Qdrant |

### State Fields Set
- `agent`: "internal_ops"
- `tools_used`: ["document_retrieval"]
- `sources`: ["doc:xxx"]

### Endpoints
- `POST /api/v1/internal/summarize` — Upload and summarize a report
- Routed via `/chat` when intent = "internal_ops"

---

## 4. General Agent (Fallback)

### Purpose
Handle greetings, off-topic queries, and unclear requests.

### Prompt
Loaded from `src/agents/prompts/general_prompt.txt`.

### State Fields Set
- `agent`: "general"
- `tools_used`: []

---

## Agent State Schema

```python
class AgentState(dict):
    messages: list[dict]        # Conversation history
    user_query: str             # Raw user input
    task: str                   # Current task description
    intent: str                 # Classified intent
    agent: str | None           # Which agent handled this
    context: dict               # RAG-retrieved context
    response: str               # Final response
    sources: list[str]          # Source references (doc:xxx, order:xxx)
    metadata: dict              # Channel, user info
    tools_used: list[str]       # Audit trail
    error: str | None           # Error if failed
```

## Error Handling

All agents follow a consistent error pattern:
1. Tool call fails → Log warning, continue with available data
2. LLM call fails → Return error message to user
3. Agent fails → Supervisor returns generic error + logs incident
4. All errors are logged with structlog
