# Basira (بصيرة)

> **Insight, perception, deep vision** — A multi-agent AI platform for retail & food companies with Arabic-first NLU.

## Overview

Basira is a production-grade AI agents platform built with:

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11+ / FastAPI |
| **Agent Orchestration** | LangGraph (stateful multi-agent graphs) |
| **LLM** | Groq (groq.com) — fast inference, OpenAI-compatible |
| **Vector Store** | Qdrant (self-hosted via Docker) |
| **Automation** | n8n (workflow JSONs in-repo) |

## Agents

| Agent | Purpose | Priority |
|-------|---------|----------|
| **Analytical Agent** | Sales, inventory, branch analytics from Odoo | 🔴 Top |
| **Customer Service Agent** | Customer inquiries via RAG + Odoo APIs | 🟡 High |
| **Internal Ops Agent** | Report summarization, KPI extraction, tasks | 🟢 Medium |

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
