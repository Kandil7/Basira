# Basira (بصيرة)

> **Insight, perception, deep vision** — A multi-agent AI platform for retail & food companies with Arabic-first NLU.

[![CI](https://img.shields.io/badge/CI-Passing-brightgreen)](#)
[![Python](https://img.shields.io/badge/Python-3.11+-blue)](#)
[![Tests](https://img.shields.io/badge/Tests-67 Passing-brightgreen)](#)
[![Phase](https://img.shields.io/badge/Phase-3%20Complete-brightgreen)](#)

## Overview

Basira is a production-grade AI agents platform for retail and food companies, built with Clean Architecture and Arabic-first NLU. It integrates with Odoo ERP for real-time data access and uses LangGraph for stateful multi-agent orchestration.

### Key Features

- 🤖 **6 AI Agents** — Analytics, CX, Internal Ops, Pricing, Supply Chain, General
- 🔍 **Advanced RAG** — Hybrid search (semantic + BM25), reranking, query expansion
- 🔐 **Production Security** — RBAC, guardrails, PII detection, rate limiting
- 📊 **Real-time Dashboard** — Streamlit UI with chat, analytics, and metrics
- 🔄 **n8n Automation** — 3 workflow templates for reports, CX, and alerts
- 📈 **67 Tests** — Unit + integration tests with mocked dependencies

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11+ / FastAPI |
| **Agent Orchestration** | LangGraph (stateful multi-agent graphs) |
| **LLM** | Groq (groq.com) — fast inference, OpenAI-compatible |
| **Vector Store** | Qdrant (self-hosted via Docker) |
| **Session Store** | Redis (with in-memory fallback) |
| **Audit Log** | PostgreSQL + SQLAlchemy async |
| **Dashboard** | Streamlit |
| **Automation** | n8n (workflow JSONs in-repo) |
| **CI/CD** | GitHub Actions |

## Agents

| Agent | Purpose | Tools |
|-------|---------|-------|
| **Analytical Agent** | Sales, inventory, branch analytics | Daily sales, inventory status, branch KPIs |
| **Customer Service Agent** | Customer inquiries via RAG + Odoo | Order status, customer info, policy lookup |
| **Internal Ops Agent** | Report summarization, KPI extraction | Document search, summarize, extract KPIs |
| **Pricing Agent** | Price analysis, discounts, recommendations | Product prices, discount analysis |
| **Supply Chain Agent** | Suppliers, procurement, replenishment | Suppliers, purchase orders, performance |
| **General Agent** | Fallback for greetings and unclear queries | — |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend                          │
│  POST /chat  •  POST /reports/daily  •  POST /pricing/products │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                    LangGraph Supervisor                          │
│         Intent Classification → Agent Routing                   │
└──────┬──────────┬──────────┬──────────┬──────────┬─────────────┘
       │          │          │          │          │
┌──────▼──┐ ┌────▼────┐ ┌───▼────┐ ┌───▼────┐ ┌──▼──────────┐
│Analyt.  │ │   CX    │ │  Ops   │ │Pricing │ │Supply Chain │
│ Agent   │ │ Agent   │ │ Agent  │ │ Agent  │ │   Agent     │
└────┬────┘ └────┬────┘ └───┬────┘ └───┬────┘ └──┬──────────┘
     │           │          │          │          │
┌────▼───────────▼──────────▼──────────▼──────────▼─────────────┐
│                    Domain Services                              │
│  AnalyticsService • CustomerService • PricingService • ...     │
└──────┬────────────────────────────────────────────────────────┘
       │
┌──────▼────────────────────────────────────────────────────────┐
│                    Infrastructure                               │
│  Odoo (XML-RPC)  •  Qdrant (RAG)  •  Redis  •  PostgreSQL   │
└───────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Groq API key (groq.com)

### Installation

```bash
# 1. Clone the repository
git clone <repository-url>
cd basira

# 2. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 3. Start services (Qdrant + Redis + PostgreSQL)
docker compose up -d

# 4. Install dependencies
pip install -e ".[dev]"

# 5. Run the API
uvicorn src.api.main:app --reload

# 6. Run the Dashboard (optional)
streamlit run src/dashboard/app.py
```

### Test the API

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Chat with Basira
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Internal-Key: change-me-in-production" \
  -d '{"query": "ما هي مبيعات اليوم؟", "channel": "web"}'

# Get daily report
curl -X POST http://localhost:8000/api/v1/reports/daily \
  -H "Content-Type: application/json" \
  -H "X-Internal-Key: change-me-in-production" \
  -d '{"date": "2025-01-15"}'
```

### Run Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# With coverage
pytest --cov=src --cov-report=html
```

## Project Structure

```
basira/
├── src/
│   ├── agents/              # LangGraph agent definitions
│   │   ├── nodes/           # Agent nodes (6 agents)
│   │   ├── tools/           # LangChain tools (12 tools)
│   │   ├── prompts/         # Arabic-first prompt templates
│   │   ├── graph.py         # Supervisor graph
│   │   ├── builder.py       # Graph factory
│   │   └── state.py         # AgentState definition
│   ├── api/                 # FastAPI routes & middleware
│   │   ├── routes/          # 13 API endpoints
│   │   └── middleware/      # Auth, rate limiting
│   ├── domain/              # Business logic (Clean Architecture)
│   │   ├── models/          # Pydantic data models
│   │   ├── interfaces/      # Abstract contracts
│   │   └── services/        # Domain services
│   ├── infrastructure/      # External integrations
│   │   ├── data/            # Odoo client + repositories
│   │   ├── rag/             # Qdrant + hybrid search + reranking
│   │   ├── session/         # Redis session store
│   │   ├── database/        # PostgreSQL audit log
│   │   ├── guardrails/      # Safety rules + PII detection
│   │   ├── rbac/            # Role-based access control
│   │   ├── metrics/         # Real-time monitoring
│   │   ├── pooling/         # Connection pooling
│   │   └── evaluation/      # LLM evaluation framework
│   ├── dashboard/           # Streamlit dashboard
│   └── automation/          # n8n workflow JSONs
├── tests/                   # 67 tests (unit + integration)
├── docs/                    # Architecture & API docs
├── .github/workflows/       # CI/CD pipeline
├── docker-compose.yml       # Redis + PostgreSQL + Qdrant + API
└── pyproject.toml           # Dependencies & config
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/chat` | Chat with AI agents (supervisor entry) |
| POST | `/api/v1/reports/daily` | Daily branch reports |
| POST | `/api/v1/kpis/branches` | Branch KPIs |
| POST | `/api/v1/inventory/low-stock` | Low stock alerts |
| POST | `/api/v1/pricing/products` | Product pricing |
| POST | `/api/v1/pricing/recommendations` | Pricing recommendations |
| POST | `/api/v1/pricing/discounts` | Discount analysis |
| POST | `/api/v1/supply-chain/suppliers` | Supplier list |
| POST | `/api/v1/supply-chain/replenishment` | Replenishment alerts |
| POST | `/api/v1/supply-chain/purchase-orders` | Purchase orders |
| POST | `/api/v1/supply-chain/supplier-performance` | Supplier performance |
| POST | `/api/v1/internal/summarize` | Document upload & summarization |
| POST | `/api/v1/internal/search` | Semantic document search |
| GET | `/api/v1/health` | System health check |

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — System design and Clean Architecture layers
- [Agents](docs/AGENTS.md) — LangGraph agent specifications
- [Data Sources](docs/DATA_SOURCES.md) — Odoo, Qdrant, and DB adapters
- [API Reference](docs/API_REFERENCE.md) — FastAPI endpoint docs
- [n8n Workflows](docs/N8N_WORKFLOWS.md) — Automation workflow docs
- [Branching Strategy](docs/BRANCHING_STRATEGY.md) — Git workflow guidelines

## Development

### Branching Strategy

- `main` — Production-ready code
- `develop` — Integration branch
- `feature/*` — Feature development
- `release/*` — Release preparation

### Commit Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(agents): add pricing agent with discount analysis
fix(api): handle empty response from Odoo
test: add unit tests for guardrails engine
docs: update API reference with new endpoints
```

## License

MIT
