# BRANCHING STRATEGY

## Branch Types

| Branch | Purpose | Lifetime |
|--------|---------|----------|
| `main` | Stable, production-ready code | Permanent |
| `develop` | Integration branch for ongoing work | Permanent |
| `feature/*` | Individual feature development | Merged then deleted |
| `hotfix/*` | Critical production fixes | Merged then deleted |
| `release/*` | Release preparation | Merged then deleted |

## Workflow

### Feature Development
```bash
# 1. Create from develop
git checkout develop
git pull origin develop
git checkout -b feature/analytical-agent

# 2. Develop + commit
git add .
git commit -m "feat: implement analytical agent with LangGraph"

# 3. Push + PR
git push origin feature/analytical-agent
# Create PR → develop

# 4. Merge + cleanup
git checkout develop
git merge --no-ff feature/analytical-agent
git branch -d feature/analytical-agent
```

### Release Process
```bash
# 1. Create release branch
git checkout develop
git checkout -b release/0.1.0

# 2. Version bump + final fixes
# Edit pyproject.toml version
git commit -m "chore: bump version to 0.1.0"

# 3. Merge to main + tag
git checkout main
git merge --no-ff release/0.1.0
git tag -a v0.1.0 -m "Release 0.1.0"

# 4. Back-merge to develop
git checkout develop
git merge --no-ff release/0.1.0
```

## Commit Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>
```

### Types
| Type | When to Use |
|------|-------------|
| `feat` | New feature or agent |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `test` | Adding/updating tests |
| `refactor` | Code restructuring |
| `chore` | Build, CI, tooling |

### Real Examples from This Project

```
feat(agents): add supervisor graph with intent classification
feat(agents): implement CX agent with order lookup and RAG
feat(agents): add Internal Ops agent with KPI extraction
feat(tools): add CX tools (order_status, customer_info, create_ticket)
feat(api): add /chat endpoint for supervisor entrypoint
feat(api): add /reports/daily and /kpis/branches endpoints
feat(qdrant): implement vector store with collection management
feat(odoo): add XML-RPC read-only client with retry logic
test(agents): add agent integration tests with mocked LLM
test(services): add domain service unit tests
docs: finalize Phase 1 architecture documentation
docs: add n8n workflow JSONs with error handling
chore: configure pyproject.toml with dev dependencies
```

## PR Guidelines

### Title
Use conventional commit format: `feat(agents): add analytical agent`

### Description Template
```markdown
## Summary
Brief description of changes.

## Changes
- Change 1
- Change 2

## Testing
- [ ] Unit tests pass
- [ ] Manual testing completed

## Documentation
- [ ] Relevant docs updated
```

### Review Checklist
- [ ] Clean Architecture: no framework imports in domain layer
- [ ] Type hints complete (mypy-friendly)
- [ ] Tests cover new code
- [ ] Documentation updated
- [ ] No secrets in code

## Release Tagging

| Change | Version | Example |
|--------|---------|---------|
| New agent/feature | Minor | v0.2.0 |
| Bug fix | Patch | v0.1.1 |
| Breaking API change | Major | v1.0.0 |

## Phase 1 Branches Used

| Branch | Purpose | Status |
|--------|---------|--------|
| `feature/project-scaffold` | Initial project structure | Merged |
| `feature/data-layer` | Odoo client + repositories | Merged |
| `feature/qdrant-rag` | Qdrant vector store + retriever | Merged |
| `feature/analytical-agent` | Analytical Agent + tools | Merged |
| `feature/supervisor-graph` | LangGraph supervisor + /chat | Merged |
| `feature/cx-agent` | CX Agent + tools | Merged |
| `feature/ops-agent` | Internal Ops Agent + tools | Merged |
| `feature/n8n-workflows` | n8n workflow JSONs | Merged |
| `feature/phase4-tests` | Agent integration tests | Merged |
