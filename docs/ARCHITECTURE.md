# ARCHITECTURE

## Clean Architecture Layers

This project follows Clean Architecture (Uncle Bob) with strict dependency rules:

```
┌─────────────────────────────────────────────────────────┐
│                   INTERFACE LAYER                        │
│  FastAPI routes, n8n webhook handlers                   │
│  → Only maps HTTP → Application/Agent calls             │
├─────────────────────────────────────────────────────────┤
│                   AGENTS LAYER                          │
│  LangGraph graphs, nodes, tools, prompts                │
│  → Orchestrates domain services + infrastructure        │
├─────────────────────────────────────────────────────────┤
│                APPLICATION LAYER                        │
│  Use cases, service orchestration                       │
│  → Coordinates domain logic for specific workflows      │
├─────────────────────────────────────────────────────────┤
│                   DOMAIN LAYER                          │
│  Models, interfaces, business rules                     │
│  → ZERO framework imports (no FastAPI, Qdrant, etc.)   │
├─────────────────────────────────────────────────────────┤
│                INFRASTRUCTURE LAYER                     │
│  Odoo client, Qdrant client, logging, HTTP              │
│  → Implements domain interfaces                         │
└─────────────────────────────────────────────────────────┘
```

## Dependency Rule

```
Interface → Application → Domain
                  ↓
            Infrastructure (implements Domain interfaces)
```

- **Domain** depends on nothing external. Only Pydantic for models.
- **Infrastructure** implements `domain.interfaces` contracts.
- **Agents** use domain services and infrastructure tools.
- **API** only maps HTTP to agent/service calls.

## Module Map

### `src/config/`
Settings loaded from environment. Single source of truth for all configuration.

### `src/domain/`
| Module | Purpose |
|--------|---------|
| `models/` | Pydantic data models (SalesReport, KPI, Customer, etc.) |
| `interfaces/` | Abstract base classes (VectorStore, OdooClient, etc.) |
| `services/` | Business logic (AnalyticsService, CustomerService, etc.) |

### `src/infrastructure/`
| Module | Purpose |
|--------|---------|
| `data/odoo_client.py` | Odoo XML-RPC read-only client |
| `data/repositories/` | Concrete repos (SalesRepo, InventoryRepo, CustomerRepo) |
| `rag/vectorstore.py` | Qdrant vector store implementation |
| `rag/retriever.py` | Semantic retrieval with Qdrant |
| `rag/ingest/` | Document ingestion pipeline (stubs) |
| `logging/` | Structured logging with structlog |

### `src/agents/`
| Module | Purpose |
|--------|---------|
| `builder.py` | Graph factory — `build_graph()` entry point |
| `graph.py` | LangGraph supervisor graph definition |
| `state.py` | Shared `AgentState` definition |
| `llm.py` | Groq LLM client wrapper |
| `nodes/` | Individual agent nodes (supervisor, analytical, cx, internal_ops, general) |
| `tools/` | LangChain tools wrapping domain services |
| `prompts/` | Prompt templates loaded from .txt files |

### `src/api/`
| Module | Purpose |
|--------|---------|
| `main.py` | FastAPI app factory + lifespan |
| `routes/` | HTTP endpoint handlers (chat, analytics, internal, health) |
| `dependencies.py` | Dependency injection helpers |

### `src/automation/n8n/`
| Module | Purpose |
|--------|---------|
| `workflows/` | Exported n8n workflow JSON files |

## Supervisor Graph Flow

```
                    ┌──────────────┐
                    │   START      │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  supervisor  │ ← Classifies intent via Groq LLM
                    │  (classify)  │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┬──────────────┐
              │            │            │              │
     ┌────────▼──┐  ┌──────▼─────┐ ┌───▼────────┐ ┌──▼──────────┐
     │analytics  │  │    cx      │ │internal_ops│ │   general   │
     │  _agent   │  │   _agent   │ │  _agent    │ │   _agent    │
     └─────┬─────┘  └─────┬──────┘ └─────┬──────┘ └──────┬──────┘
           │              │              │               │
     ┌─────▼─────┐  ┌─────▼──────┐ ┌────▼───────┐ ┌────▼────────┐
     │   END     │  │    END     │ │    END     │ │    END      │
     └───────────┘  └────────────┘ └────────────┘ └─────────────┘
```

## Data Flow: Analytical Query

```
User → POST /chat {"query": "ما هي مبيعات فرع الرياض اليوم؟"}
  → Supervisor classifies intent: "analytics"
  → Analytical Agent node receives query
  → Agent calls AnalyticsService.get_daily_sales()
    → OdooClient executes XML-RPC call
    → Returns structured DailyReport
  → Agent generates Arabic response via Groq LLM
  → Response returned with agent="analytical", sources=[]
```

## Data Flow: CX Query

```
User → POST /chat {"query": "أين طلبي رقم 12345؟", "channel": "whatsapp"}
  → Supervisor classifies intent: "cx"
  → CX Agent node receives query
  → Agent calls CustomerService.get_order_status("12345")
    → OdooClient executes XML-RPC call
  → Agent queries Qdrant for FAQ/policy context
  → Agent generates response via Groq LLM
  → Response returned with agent="cx", sources=["order:12345", "doc:xxx"]
```

## State Schema

```python
class AgentState(dict):
    messages: list[dict]        # Conversation history
    user_query: str             # Raw user input
    task: str                   # Current task description
    intent: str                 # "analytics" | "cx" | "internal_ops" | "general"
    agent: str | None           # Which agent handled the request
    context: dict               # RAG-retrieved context
    response: str               # Final agent response
    sources: list[str]          # Source references for attribution
    metadata: dict              # Channel, user info, timestamps
    tools_used: list[str]       # Audit trail of tools called
    error: str | None           # Error message if failed
```

## Prompt Management

All agent prompts are stored as `.txt` files in `src/agents/prompts/`:
- `supervisor_prompt.txt` — Intent classification
- `analytical_prompt.txt` — Sales/inventory analysis
- `cx_prompt.txt` — Customer service
- `internal_ops_prompt.txt` — Report summarization
- `general_prompt.txt` — Fallback

Loaded at import time via `prompts/__init__.py` and imported by each node.
