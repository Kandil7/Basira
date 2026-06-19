# Deployment Guide

This guide covers deploying Basira to production environments.

## Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Groq API key (groq.com)
- Odoo instance (optional)

## Environment Variables

Create a `.env` file with the following variables:

```bash
# ── Groq LLM ──────────────────────────────────────────────────────────
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_BASE_URL=https://api.groq.com/openai/v1

# ── Qdrant ────────────────────────────────────────────────────────────
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=company_docs

# ── Redis ─────────────────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0
REDIS_SESSION_TTL=3600
REDIS_MAX_CONNECTIONS=20

# ── PostgreSQL ────────────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://basira:basira@localhost:5432/basira
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20

# ── Odoo (Optional) ──────────────────────────────────────────────────
ODOO_URL=https://your-odoo-instance.com
ODOO_DB=your_database
ODOO_USERNAME=api_user
ODOO_PASSWORD=api_password

# ── Application ───────────────────────────────────────────────────────
APP_ENV=production
APP_LOG_LEVEL=INFO
APP_SECRET_KEY=your-secret-key-here
INTERNAL_API_KEY=your-internal-api-key-here
```

## Docker Deployment

### 1. Start All Services

```bash
# Start all services
docker compose up -d

# Check service status
docker compose ps

# View logs
docker compose logs -f api
```

### 2. Initialize Database

```bash
# Run database migrations (if needed)
docker compose exec api python -c "
from src.infrastructure.database.models import create_tables
import asyncio
asyncio.run(create_tables())
"
```

### 3. Ingest Documents (Optional)

```bash
# Ingest company policies
docker compose exec api python -c "
from src.infrastructure.rag.ingest import DocumentIngester
from src.infrastructure.rag.vectorstore import QdrantVectorStore
from src.config.settings import get_settings

settings = get_settings()
vector_store = QdrantVectorStore(settings)
ingester = DocumentIngester(vector_store)

import asyncio
count = asyncio.run(ingester.ingest_policies('/path/to/policies'))
print(f'Ingested {count} documents')
"
```

## Production Configuration

### Security Hardening

```bash
# 1. Change default API key
INTERNAL_API_KEY=your-secure-random-key

# 2. Enable HTTPS (use reverse proxy)
# nginx.conf or traefik.yml

# 3. Restrict CORS
# Edit src/api/main.py to allow specific origins
```

### Performance Tuning

```bash
# 1. Increase connection pools
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
REDIS_MAX_CONNECTIONS=50

# 2. Enable uvicorn workers
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4

# 3. Use Redis for caching
REDIS_URL=redis://redis:6379/0
```

### Monitoring

```bash
# 1. Check health endpoint
curl http://localhost:8000/api/v1/health

# 2. View metrics
curl http://localhost:8000/api/v1/health | jq .services

# 3. Monitor logs
docker compose logs -f api | grep -E "(ERROR|WARNING)"
```

## Reverse Proxy (Nginx)

```nginx
server {
    listen 80;
    server_name basira.yourdomain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name basira.yourdomain.com;

    ssl_certificate /etc/ssl/certs/basira.crt;
    ssl_certificate_key /etc/ssl/private/basira.key;

    # API proxy
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Dashboard proxy
    location / {
        proxy_pass http://localhost:8501;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Backup & Recovery

### Database Backup

```bash
# Backup PostgreSQL
docker compose exec postgres pg_dump -U basira basira > backup.sql

# Restore PostgreSQL
docker compose exec postgres psql -U basira basira < backup.sql
```

### Redis Backup

```bash
# Backup Redis
docker compose exec redis redis-cli BGSAVE

# Copy dump file
docker compose cp redis:/data/dump.rdb ./redis-backup.rdb
```

### Qdrant Backup

```bash
# Backup Qdrant
docker compose exec qdrant tar -czf /tmp/qdrant-backup.tar.gz /qdrant/storage
docker compose cp qdrant:/tmp/qdrant-backup.tar.gz ./qdrant-backup.tar.gz
```

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| API won't start | Check `.env` file and service dependencies |
| Qdrant connection failed | Ensure Qdrant is running: `docker compose ps` |
| Redis connection failed | Check Redis is running and URL is correct |
| PostgreSQL connection failed | Check PostgreSQL is running and credentials are correct |
| Odoo connection failed | Verify Odoo URL and credentials |

### Logs

```bash
# View API logs
docker compose logs api

# View all service logs
docker compose logs

# Follow logs in real-time
docker compose logs -f
```

## Scaling

### Horizontal Scaling

```bash
# Scale API instances
docker compose up -d --scale api=3

# Use load balancer (nginx, traefik, etc.)
```

### Vertical Scaling

```yaml
# docker-compose.yml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
```

## CI/CD Pipeline

The GitHub Actions pipeline automatically:

1. Runs linting (ruff, mypy)
2. Runs unit tests
3. Runs integration tests
4. Builds Docker image
5. Deploys to production (on main branch)

## Support

For issues and questions:
- Check the [Documentation](docs/)
- Review [API Reference](docs/API_REFERENCE.md)
- Check [GitHub Issues](https://github.com/your-org/basira/issues)
