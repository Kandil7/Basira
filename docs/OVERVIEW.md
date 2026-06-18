# OVERVIEW

## Purpose

**Basira** (بصيرة — "insight, perception, deep vision") is a multi-agent AI platform for retail & food companies. It provides AI-powered analytics, customer service, and internal operations through a unified API with Arabic-first NLU.

## Phase 1 Scope (Current)

Phase 1 delivers three AI agents with shared infrastructure:

### Analytical Agent (Top Priority)
- Connects to Odoo ERP (read-only) for sales, inventory, and branch data
- Answers Arabic natural language questions about business performance
- Generates actionable recommendations based on data analysis
- Exposes `/reports/daily` and `/kpis/branches` endpoints

### Customer Service Agent (Second Priority)
- Answers customer inquiries about orders, branches, and policies
- Uses RAG (Retrieval-Augmented Generation) on company documents in Qdrant
- Supports multi-channel deployment (web, WhatsApp via n8n)
- Integrates with Odoo APIs for order status and customer history

### Internal Ops Agent (Third Priority)
- Summarizes uploaded reports (PDF/Excel)
- Extracts KPIs from structured data
- Generates prioritized task lists for operations teams
- Uses Qdrant for document storage and retrieval

## Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Backend | Python 3.11+ / FastAPI | High performance, async support, type safety |
| Agents | LangGraph | Stateful graph-based orchestration, checkpointing |
| LLM | Groq (groq.com) | Fast inference, OpenAI-compatible API |
| Vector Store | Qdrant | Production-ready, self-hostable, rich filtering |
| Automation | n8n | Visual workflow builder, webhook triggers |

## Architecture at a Glance

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────────────┐
│  FastAPI    │────▶│  Supervisor  │────▶│  Agent Nodes (LangGraph) │
│  /chat      │     │  Graph       │     │  ┌────────┐ ┌────────┐  │
└─────────────┘     └──────────────┘     │  │Analyt. │ │   CX   │  │
                                          │  │ Agent  │ │ Agent  │  │
┌─────────────┐     ┌──────────────┐     │  └───┬────┘ └───┬────┘  │
│  n8n        │────▶│  HTTP APIs   │     │  ┌───┴────┐      │       │
│  Workflows  │     │  /reports    │     │  │Internal│      │       │
└─────────────┘     │  /kpis       │     │  │  Ops   │      │       │
                    └──────────────┘     │  └───┬────┘      │       │
                                          └─────┼───────────┼───────┘
┌─────────────┐                                │           │
│  Odoo ERP   │◀───────────────────────────────┴───────────┘
│  (read-only)│     Domain Services + Repositories
└─────────────┘
                                          ┌──────────────┐
                                          │   Qdrant     │
                                          │  (RAG)       │
                                          └──────────────┘
```

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your Groq API key and other credentials

# 2. Start Qdrant (optional for basic testing)
docker compose up -d qdrant

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Run the API
uvicorn src.api.main:app --reload

# 5. Test /chat
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "ما هي مبيعات اليوم؟", "channel": "web"}'

# 6. Run tests
pytest
```

## Project Structure

```
basira/
├── docs/                    # Architecture & API documentation
├── src/
│   ├── config/              # Settings & environment
│   ├── domain/              # Business logic (no framework deps)
│   │   ├── models/          # Data models (Pydantic)
│   │   ├── interfaces/      # Abstract contracts
│   │   └── services/        # Business services
│   ├── infrastructure/      # External integrations
│   │   ├── data/            # Odoo client + repositories
│   │   ├── rag/             # Qdrant vector store + retriever
│   │   └── logging/         # Structured logging
│   ├── agents/              # LangGraph agent definitions
│   │   ├── graph.py         # Supervisor graph
│   │   ├── builder.py       # Graph factory
│   │   ├── state.py         # AgentState definition
│   │   ├── llm.py           # Groq LLM client
│   │   ├── nodes/           # Agent nodes
│   │   ├── tools/           # LangChain tools
│   │   └── prompts/         # Prompt templates
│   ├── api/                 # FastAPI routes & app
│   └── automation/          # n8n workflow JSONs
├── tests/                   # Unit + integration tests
└── docker-compose.yml       # Qdrant + API services
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — System design and Clean Architecture layers
- [Agents](docs/AGENTS.md) — LangGraph agent specifications
- [Data Sources](docs/DATA_SOURCES.md) — Odoo, Qdrant, and DB adapters
- [API Reference](docs/API_REFERENCE.md) — FastAPI endpoint docs
- [n8n Workflows](docs/N8N_WORKFLOWS.md) — Automation workflow docs
- [Branching Strategy](docs/BRANCHING_STRATEGY.md) — Git workflow guidelines

## License

MIT
