# Basira (بصيرة)

> **Insight, perception, deep vision** — A multi-agent AI platform for retail & food companies with Arabic-first NLU.

[![CI](https://img.shields.io/badge/CI-Passing-brightgreen)](#)
[![Python](https://img.shields.io/badge/Python-3.11+-blue)](#)
[![Tests](https://img.shields.io/badge/Tests-135Passing-brightgreen)](#)
[![Phase](https://img.shields.io/badge/Phase-3%20Complete-brightgreen)](#)
[![License](https://img.shields.io/badge/License-MIT-blue)](#)

## Overview

Basira is a production-grade AI agents platform for retail and food companies, built with **Clean Architecture** and **Arabic-first NLU**. It integrates with Odoo ERP for real-time data access and uses LangGraph for stateful multi-agent orchestration.

### Key Features

| Feature | Description |
|---------|-------------|
| 🤖 **6 AI Agents** | Analytics, CX, Internal Ops, Pricing, Supply Chain, General |
| 🔍 **Advanced RAG** | Hybrid search (semantic + BM25), reranking, query expansion, compression |
| 🔐 **Production Security** | RBAC, guardrails, PII detection, rate limiting |
| 📊 **Real-time Dashboard** | Streamlit UI with chat, analytics, metrics, and export |
| 🔄 **n8n Automation** | 3 workflow templates for reports, CX, and alerts |
| 📈 **135 Tests** | Unit, integration, and E2E tests with mocked dependencies |
| 🗄️ **Persistent Storage** | Redis sessions, PostgreSQL audit log, Qdrant RAG |
| 🔌 **Connection Pooling** | Odoo and Qdrant connection pools for high concurrency |
| 📄 **Report Export** | PDF, Excel, CSV, JSON export with Arabic RTL support |
| 📞 **Escalation Workflow** | Human handoff with auto-detection, tickets, and assignment |
| 🏪 **POS Integration** | WooCommerce and Square connectors with factory pattern |
| 📚 **Training Docs** | Arabic training guide and user quick-start guide |

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | Python 3.11+ / FastAPI | REST API and WebSocket support |
| **Agent Orchestration** | LangGraph | Stateful multi-agent graphs with checkpoints |
| **LLM** | Groq (groq.com) | Fast inference, OpenAI-compatible |
| **Vector Store** | Qdrant | Semantic search and RAG |
| **Session Store** | Redis | Persistent conversation history |
| **Audit Log** | PostgreSQL | Agent action audit trail |
| **Dashboard** | Streamlit | Internal monitoring UI |
| **Automation** | n8n | Workflow orchestration |
| **CI/CD** | GitHub Actions | Automated testing and deployment |

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

# 3. Start services (Redis + PostgreSQL + Qdrant)
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
│   │   ├── routes/          # 14 API endpoints
│   │   └── middleware/      # Auth, rate limiting, guardrails, RBAC
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
│   │   ├── collaboration/   # Multi-agent delegation
│   │   ├── memory/          # Persistent conversation memory
│   │   ├── agent_context/   # Context-aware responses
│   │   └── evaluation/      # LLM evaluation framework
│   ├── dashboard/           # Streamlit dashboard
│   └── automation/          # n8n workflow JSONs
├── tests/                   # 123 tests (unit + integration + E2E)
├── docs/                    # Architecture & API docs
├── .github/workflows/       # CI/CD pipeline
├── docker-compose.yml       # Redis + PostgreSQL + Qdrant + API
└── pyproject.toml           # Dependencies & config
```

## Agents

| Agent | Purpose | Tools | API Endpoints |
|-------|---------|-------|---------------|
| **Analytical Agent** | Sales, inventory, branch analytics | Daily sales, inventory status, branch KPIs | `/reports/daily`, `/kpis/branches` |
| **Customer Service Agent** | Customer inquiries via RAG + Odoo | Order status, customer info, policy lookup | `/chat` (cx intent) |
| **Internal Ops Agent** | Report summarization, KPI extraction | Document search, summarize, extract KPIs | `/internal/summarize`, `/internal/search` |
| **Pricing Agent** | Price analysis, discounts, recommendations | Product prices, discount analysis | `/pricing/products`, `/pricing/recommendations` |
| **Supply Chain Agent** | Suppliers, procurement, replenishment | Suppliers, purchase orders, performance | `/supply-chain/*` |
| **General Agent** | Fallback for greetings and unclear queries | — | `/chat` (general intent) |

## API Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/v1/chat` | Chat with AI agents (supervisor entry) | ✅ |
| POST | `/api/v1/reports/daily` | Daily branch reports | ✅ |
| POST | `/api/v1/kpis/branches` | Branch KPIs | ✅ |
| POST | `/api/v1/inventory/low-stock` | Low stock alerts | ✅ |
| POST | `/api/v1/pricing/products` | Product pricing | ✅ |
| POST | `/api/v1/pricing/recommendations` | Pricing recommendations | ✅ |
| POST | `/api/v1/pricing/discounts` | Discount analysis | ✅ |
| POST | `/api/v1/supply-chain/suppliers` | Supplier list | ✅ |
| POST | `/api/v1/supply-chain/replenishment` | Replenishment alerts | ✅ |
| POST | `/api/v1/supply-chain/purchase-orders` | Purchase orders | ✅ |
| POST | `/api/v1/supply-chain/supplier-performance` | Supplier performance | ✅ |
| POST | `/api/v1/internal/summarize` | Document upload & summarization | ✅ |
| POST | `/api/v1/internal/search` | Semantic document search | ✅ |
| GET | `/api/v1/health` | System health check | ❌ |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GROQ_API_KEY` | Groq API key for LLM | Required |
| `GROQ_MODEL` | Groq model name | `llama-3.3-70b-versatile` |
| `QDRANT_HOST` | Qdrant server host | `localhost` |
| `QDRANT_PORT` | Qdrant server port | `6333` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql+asyncpg://basira:basira@localhost:5432/basira` |
| `ODOO_URL` | Odoo XML-RPC URL | Optional |
| `ODOO_DB` | Odoo database name | Optional |
| `ODOO_USERNAME` | Odoo username | Optional |
| `ODOO_PASSWORD` | Odoo password | Optional |
| `INTERNAL_API_KEY` | API authentication key | `change-me-in-production` |
| `APP_ENV` | Application environment | `development` |

## Docker Services

| Service | Port | Description |
|---------|------|-------------|
| **API** | 8000 | FastAPI application |
| **Dashboard** | 8501 | Streamlit dashboard |
| **Redis** | 6379 | Session store & cache |
| **PostgreSQL** | 5432 | Audit log & persistence |
| **Qdrant** | 6333 | Vector store |

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/ARCHITECTURE.md) | System design and Clean Architecture layers |
| [Agents](docs/AGENTS.md) | LangGraph agent specifications |
| [Data Sources](docs/DATA_SOURCES.md) | Odoo, Qdrant, and DB adapters |
| [API Reference](docs/API_REFERENCE.md) | FastAPI endpoint docs |
| [n8n Workflows](docs/N8N_WORKFLOWS.md) | Automation workflow docs |
| [Branching Strategy](docs/BRANCHING_STRATEGY.md) | Git workflow guidelines |

## Development

### Branching Strategy

```
main ─────────────────────────────────────────────● (release)
           │                                    /
develop ───●──●──●──●──●──●──●──●──●──●──●──●──●
             │  │  │  │  │  │  │  │  │  │  │  │
             │  │  │  │  │  │  │  │  │  │  │  └─ feature/sprint6
             │  │  │  │  │  │  │  │  │  │  └──── feature/sprint5
             │  │  │  │  │  │  │  │  │  └─────── feature/sprint4
             │  │  │  │  │  │  │  │  └────────── feature/sprint3
             │  │  │  │  │  │  │  └───────────── feature/sprint2
             │  │  │  │  │  │  └──────────────── feature/sprint1
             │  │  │  │  │  └─────────────────── feature/phase2
             │  │  │  │  └────────────────────── feature/phase1
```

### Commit Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(agents): add pricing agent with discount analysis
fix(api): handle empty response from Odoo
test: add unit tests for guardrails engine
docs: update API reference with new endpoints
```

### Phase Progress

| Phase | Focus | Status |
|-------|-------|--------|
| **Phase 1** | MVP — Core agents, API, RAG | ✅ Complete |
| **Phase 2** | Advanced — Pricing, Supply Chain, Eval | ✅ Complete |
| **Phase 3** | Production — Redis, PostgreSQL, Dashboard, Security | ✅ Complete |

## License

MIT
