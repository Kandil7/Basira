# Pilot Deployment Guide — Branch 1

## Pilot Overview

**Duration**: 4 weeks
**Scope**: First branch pilot
**Goal**: Validate Basira platform with real users and data

## Pre-Pilot Checklist

### Infrastructure Setup

- [ ] Server provisioned (minimum: 4 CPU, 8GB RAM, 50GB SSD)
- [ ] Docker & Docker Compose installed
- [ ] Domain/SSL configured (if external access needed)
- [ ] Firewall rules configured (ports 80, 443, 8000, 8501)
- [ ] Backup schedule configured

### Credentials & Configuration

- [ ] Groq API key obtained (groq.com)
- [ ] Odoo credentials configured
- [ ] Internal API key set (strong, unique)
- [ ] Redis password set
- [ ] PostgreSQL password set
- [ ] `.env` file created with all credentials

### Data Preparation

- [ ] Odoo user created for Basira (read-only permissions)
- [ ] Company policies collected (PDF/Word files)
- [ ] FAQ document prepared
- [ ] Product catalog exported (if needed)
- [ ] Branch list documented

### Staff Preparation

- [ ] Pilot users identified (3-5 people)
- [ ] Training session scheduled
- [ ] User guide distributed
- [ ] Feedback form created
- [ ] Support contact established

---

## Day 1: Deployment

### Step 1: Clone and Configure

```bash
# Clone repository
git clone https://github.com/Kandil7/Basira.git
cd basira

# Configure environment
cp .env.example .env
nano .env  # Edit with production credentials
```

### Step 2: Start Services

```bash
# Start all services
docker compose up -d

# Verify services are running
docker compose ps

# Check API health
curl http://localhost:8000/api/v1/health
```

### Step 3: Ingest Company Documents

```bash
# Create policies directory
mkdir -p /path/to/company-policies

# Copy company documents
cp /path/to/policies/*.pdf /path/to/company-policies/
cp /path/to/faqs/*.txt /path/to/company-policies/

# Ingest into Qdrant
docker compose exec api python -c "
import asyncio
from src.infrastructure.rag.ingest import DocumentIngester
from src.infrastructure.rag.vectorstore import QdrantVectorStore
from src.config.settings import get_settings

settings = get_settings()
vector_store = QdrantVectorStore(settings)
ingester = DocumentIngester(vector_store)

count = asyncio.run(ingester.ingest_policies('/path/to/company-policies'))
print(f'Ingested {count} documents')
"
```

### Step 4: Test Basic Functionality

```bash
# Test chat
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Internal-Key: your-api-key" \
  -d '{"query": "مرحباً، كيف حالك؟", "channel": "web"}'

# Test analytics
curl -X POST http://localhost:8000/api/v1/reports/daily \
  -H "Content-Type: application/json" \
  -H "X-Internal-Key: your-api-key" \
  -d '{"date": "2025-01-15"}'

# Test pricing
curl -X POST http://localhost:8000/api/v1/pricing/products \
  -H "Content-Type: application/json" \
  -H "X-Internal-Key: your-api-key" \
  -d '{"product_ids": []}'
```

### Step 5: Start Dashboard

```bash
# Start Streamlit dashboard
docker compose exec api streamlit run src/dashboard/app.py --server.port 8501

# Access dashboard at http://localhost:8501
```

---

## Week 1: Initial Testing

### Day 2-3: Staff Training

**Training Session Agenda (1 hour)**

1. **Introduction** (10 min)
   - What is Basira?
   - What can it do?
   - How to access it

2. **Chat Interface** (20 min)
   - How to ask questions
   - Example queries for each agent
   - Understanding responses

3. **Dashboard Walkthrough** (15 min)
   - Chat page
   - Analytics page
   - Documents page

4. **Q&A** (15 min)
   - Common questions
   - Troubleshooting

**Example Queries to Practice**

```
# Analytics
ما هي مبيعات اليوم؟
ما هي الفروع الأعلى أداءً؟
كم مخزون الصنف X؟

# Customer Service
أين طلبي رقم 12345؟
ما هي سياسة الإرجاع؟
كيف أتصل بالفروع؟

# Pricing
ما هي أسعار المنتجات؟
هل هناك خصومات حالياً؟

# Supply Chain
كم مخزون المورد X؟
هل هناك طلبات شراء معلقة؟
```

### Day 4-5: Initial Feedback

- [ ] Collect feedback from pilot users
- [ ] Document any issues encountered
- [ ] Note feature requests
- [ ] Adjust configurations if needed

---

## Week 2: Expansion

### Expand Usage

- [ ] Add more test queries
- [ ] Test all 6 agents
- [ ] Verify data accuracy
- [ ] Monitor system performance

### Metrics to Track

| Metric | Target | Actual |
|--------|--------|--------|
| Response time | < 5 seconds | _____ |
| Accuracy | > 80% | _____ |
| User satisfaction | > 4/5 | _____ |
| System uptime | > 99% | _____ |

---

## Week 3: Optimization

### Based on Feedback

- [ ] Update prompts if responses are poor
- [ ] Add more documents to RAG if needed
- [ ] Adjust guardrails if too restrictive
- [ ] Fine-tune agent routing

### Performance Monitoring

```bash
# Check system health
curl http://localhost:8000/api/v1/health

# View metrics
docker compose logs api | grep -E "(ERROR|WARNING)"

# Check resource usage
docker stats
```

---

## Week 4: Evaluation

### Final Evaluation

- [ ] Collect final feedback
- [ ] Calculate success metrics
- [ ] Document lessons learned
- [ ] Plan expansion to next branches

### Success Criteria

| Criteria | Target | Status |
|----------|--------|--------|
| Response time | < 5 seconds | ☐ Pass ☐ Fail |
| Accuracy | > 80% | ☐ Pass ☐ Fail |
| User satisfaction | > 4/5 | ☐ Pass ☐ Fail |
| System uptime | > 99% | ☐ Pass ☐ Fail |
| Staff adoption | > 80% | ☐ Pass ☐ Fail |

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| API won't start | Check `.env` file and service logs |
| Slow responses | Check Groq API status and network |
| Poor accuracy | Add more documents to RAG |
| Agent misrouting | Update supervisor prompt |
| Dashboard not loading | Check Streamlit is running |

### Support Contacts

- **Technical Issues**: [Your IT Team]
- **Basira Support**: [Your Contact]
- **Emergency**: [Emergency Contact]

---

## Post-Pilot Actions

### If Pilot Succeeds

- [ ] Plan expansion to 2-3 more branches
- [ ] Schedule next training sessions
- [ ] Set up automated monitoring
- [ ] Document best practices

### If Pilot Fails

- [ ] Analyze failure reasons
- [ ] Address critical issues
- [ ] Consider re-pilot with changes
- [ ] Document lessons learned

---

## Resources

- [Basira README](../README.md)
- [API Reference](API_REFERENCE.md)
- [Deployment Guide](DEPLOYMENT.md)
- [Architecture](ARCHITECTURE.md)
