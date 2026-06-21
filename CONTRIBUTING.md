# Contributing to Basira

Thank you for your interest in contributing to Basira! This document provides guidelines and information for contributors.

## Getting Started

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Git

### Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/Kandil7/Basira.git
   cd Basira
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate  # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Copy environment file**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

5. **Start development services**
   ```bash
   docker compose up -d redis postgres qdrant
   ```

6. **Run tests**
   ```bash
   pytest tests/unit/ -v
   ```

## Development Workflow

### Branch Strategy

We use Git Flow:
- `main` — Production-ready code
- `develop` — Integration branch
- `feature/*` — New features
- `fix/*` — Bug fixes
- `hotfix/*` — Urgent production fixes

### Creating a Branch

```bash
git checkout develop
git pull origin develop
git checkout -b feature/your-feature-name
```

### Code Standards

- **Python**: Follow PEP 8, use type hints
- **Formatting**: Use `black` and `ruff`
- **Linting**: Run `ruff check src/ tests/`
- **Type Checking**: Run `mypy src/`
- **Tests**: Maintain >80% coverage

### Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add new agent for inventory management
fix: resolve race condition in cache invalidation
docs: update API reference for new endpoints
test: add unit tests for rate limiter
refactor: extract common logic into utility module
```

### Pull Request Process

1. **Update documentation** if needed
2. **Add tests** for new functionality
3. **Ensure all tests pass**: `pytest tests/unit/ -v`
4. **Run linting**: `ruff check src/ tests/`
5. **Create PR** with clear description
6. **Wait for CI** to pass
7. **Request review** from maintainers

## Architecture Guidelines

### Clean Architecture

```
Domain Layer (src/domain/)
  ↓ depends on nothing
Infrastructure Layer (src/infrastructure/)
  ↓ depends on Domain
Agents Layer (src/agents/)
  ↓ depends on Domain + Infrastructure
API Layer (src/api/)
  ↓ depends on all layers
```

**Rules:**
- Domain layer has ZERO framework imports
- Infrastructure implements domain interfaces
- Agents use domain services, not infrastructure directly
- API wires everything together

### Adding a New Agent

1. **Define models** in `src/domain/models/`
2. **Create service** in `src/domain/services/`
3. **Implement tools** in `src/agents/tools/`
4. **Write prompt** in `src/agents/prompts/`
5. **Create node** in `src/agents/nodes/`
6. **Add to graph** in `src/agents/graph.py`
7. **Add routes** in `src/api/routes/`
8. **Write tests** in `tests/unit/`

### Adding a New Endpoint

1. **Create route file** in `src/api/routes/`
2. **Define request/response models** with Pydantic
3. **Add to main.py** router includes
4. **Update API_REFERENCE.md**
5. **Add tests**

## Testing

### Running Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests (requires running services)
pytest tests/integration/ -v

# With coverage
pytest tests/unit/ --cov=src --cov-report=html

# Specific test file
pytest tests/unit/test_agents.py -v
```

### Writing Tests

- Use `pytest` with `asyncio_mode = "auto"`
- Mock external services (Odoo, LLM, Redis)
- Test both success and error paths
- Use descriptive test names

## Documentation

- Update `docs/` for new features
- Add docstrings to all public functions
- Update `API_REFERENCE.md` for new endpoints
- Update `README.md` if adding major features

## Questions?

- Open an issue for bugs
- Start a discussion for features
- Check existing docs before asking

Thank you for contributing! 🎉
