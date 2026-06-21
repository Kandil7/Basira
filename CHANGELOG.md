# Changelog

All notable changes to Basira will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-01-01

### Added

#### Core Platform
- 6 AI agents (Analytical, CX, Internal Ops, Pricing, Supply Chain, General)
- LangGraph supervisor with Arabic-first intent classification
- FastAPI backend with 14 REST endpoints
- Clean Architecture (Domain → Infrastructure → Agents → API)

#### RAG Pipeline
- Hybrid search (semantic + BM25) with Reciprocal Rank Fusion
- Cross-encoder reranking for relevance
- LLM-based query expansion and contextual compression
- Advanced retriever pipeline (expansion → hybrid → rerank → compress)

#### Embeddings
- Multi-provider support (OpenAI, Jina, local sentence-transformers, placeholder)
- Redis-backed embedding cache with 7-day TTL
- Arabic text preprocessing (diacritics removal, normalization)
- Batch processing with rate limiting

#### Vector Store
- Production Qdrant with async operations
- Exponential backoff retry (3 attempts)
- Advanced metadata filtering (range, exists, match any, AND/OR)
- HNSW indexing and scalar quantization
- Multi-tenancy via namespace prefix
- Batch upsert with rate limiting

#### Cache Layer
- Multi-tier cache (L1 in-memory LRU + L2 Redis)
- Stampede protection (SingleFlight pattern)
- Cache decorators (@cached, @cache_invalidate, @cache_warm)
- Configurable TTL per tier

#### Rate Limiting
- 3 algorithms (Sliding Window, Token Bucket, Fixed Window)
- Redis-backed distributed rate limiting
- Per-endpoint and per-role limits
- Rate limit headers (X-RateLimit-*)
- Graceful degradation (fail open if Redis is down)

#### Security
- RBAC with 6 roles and 14 permissions
- Guardrails engine (content filter, financial protection, output length)
- PII detection (phone, email, national ID, credit card, IBAN, IP)
- Authentication middleware (X-Internal-Key)

#### Data Integration
- Odoo XML-RPC client (read-only) with retry and auth caching
- WooCommerce POS connector
- Square POS connector (placeholder)
- n8n workflow templates (reports, CX, alerts)

#### Observability
- Structured logging with structlog
- OpenTelemetry tracing (configured)
- Real-time metrics (latency percentiles, throughput, error rates)
- Comprehensive health check endpoint

#### Operations
- PostgreSQL audit log with graceful degradation
- Redis session store with in-memory fallback
- Connection pooling for Odoo and Qdrant
- Multi-agent collaboration with delegation
- Persistent conversation memory
- Context-aware agent responses

#### Dashboard
- Streamlit UI with Chat, Analytics, Documents, Settings pages
- Report export (PDF, Excel, CSV, JSON)
- Pilot monitoring section

#### Documentation
- Architecture documentation
- API reference
- Deployment guide
- Pilot deployment guide
- Training documentation (Arabic)
- User quick-start guide

#### Testing
- 239 unit tests across 14 test files
- Integration tests with mocked services
- E2E tests for API endpoints
- CI/CD pipeline (GitHub Actions)

#### DevOps
- Multi-stage Dockerfile (production + development)
- Docker Compose with 5 services (Redis, PostgreSQL, Qdrant, API, Dashboard)
- Health checks on all services
- Resource limits and restart policies

## [0.1.0] - 2023-12-01

### Added
- Initial MVP with 4 agents (Analytical, CX, Internal Ops, General)
- FastAPI backend with 8 endpoints
- Odoo XML-RPC integration
- Qdrant vector store
- n8n automation (3 workflows)
