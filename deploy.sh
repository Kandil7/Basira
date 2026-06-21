#!/bin/bash
# ── Basira Production Deployment Script ─────────────────────────────────
# This script deploys Basira to a Linux server with Docker Compose.
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh
#
# Prerequisites:
#   - Docker & Docker Compose installed
#   - SSH access to the server
#   - Domain name pointed to the server (optional)
# ────────────────────────────────────────────────────────────────────────

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="basira"
APP_DIR="/opt/basira"
BACKUP_DIR="/opt/basira-backups"
LOG_FILE="/var/log/basira-deploy.log"

# Functions
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

# ── Step 1: Check Prerequisites ────────────────────────────────────────
check_prerequisites() {
    log "Checking prerequisites..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker first."
    fi

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        error "Docker Compose is not installed."
    fi

    # Check if running as root
    if [ "$EUID" -ne 0 ]; then
        warning "Not running as root. Some operations may require sudo."
    fi

    success "Prerequisites check passed"
}

# ── Step 2: Create Directories ─────────────────────────────────────────
create_directories() {
    log "Creating directories..."

    mkdir -p "$APP_DIR"
    mkdir -p "$BACKUP_DIR"
    mkdir -p "$APP_DIR/logs"

    success "Directories created"
}

# ── Step 3: Clone or Update Repository ─────────────────────────────────
setup_repository() {
    log "Setting up repository..."

    cd "$APP_DIR"

    if [ -d ".git" ]; then
        log "Repository exists. Pulling latest changes..."
        git pull origin main
    else
        log "Cloning repository..."
        git clone https://github.com/Kandil7/Basira.git .
    fi

    success "Repository ready"
}

# ── Step 4: Configure Environment ──────────────────────────────────────
configure_environment() {
    log "Configuring environment..."

    if [ ! -f ".env" ]; then
        log "Creating .env from template..."
        cp .env.example .env

        # Generate random secrets
        APP_SECRET=$(openssl rand -hex 32)
        INTERNAL_API_KEY=$(openssl rand -hex 32)
        POSTGRES_PASSWORD=$(openssl rand -hex 16)

        # Update .env with generated secrets
        sed -i "s/change-me-in-production/$APP_SECRET/" .env
        sed -i "s/change-me-in-production/$INTERNAL_API_KEY/" .env
        sed -i "s/POSTGRES_PASSWORD=basira/POSTGRES_PASSWORD=$POSTGRES_PASSWORD/" .env

        # Set production values
        sed -i "s/APP_ENV=development/APP_ENV=production/" .env
        sed -i "s/APP_LOG_LEVEL=INFO/APP_LOG_LEVEL=WARNING/" .env

        warning "Please edit .env file with your API keys:"
        warning "  - GROQ_API_KEY"
        warning "  - OPENAI_API_KEY (for embeddings)"
        warning "  - ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD"
        warning ""
        warning "Run: nano $APP_DIR/.env"

        read -p "Press Enter after editing .env file..."
    else
        log ".env file already exists. Skipping..."
    fi

    success "Environment configured"
}

# ── Step 5: Backup Existing Data ───────────────────────────────────────
backup_data() {
    log "Creating backup..."

    BACKUP_NAME="basira-backup-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$BACKUP_DIR/$BACKUP_NAME"

    # Backup volumes if they exist
    if docker volume ls | grep -q "basira_redis_data"; then
        docker run --rm -v basira_redis_data:/data -v "$BACKUP_DIR/$BACKUP_NAME":/backup alpine tar czf /backup/redis.tar.gz -C /data .
    fi

    if docker volume ls | grep -q "basira_postgres_data"; then
        docker run --rm -v basira_postgres_data:/var/lib/postgresql/data -v "$BACKUP_DIR/$BACKUP_NAME":/backup alpine tar czf /backup/postgres.tar.gz -C /var/lib/postgresql/data .
    fi

    # Keep only last 7 backups
    cd "$BACKUP_DIR"
    ls -dt */ | tail -n +8 | xargs -r rm -rf

    success "Backup created: $BACKUP_NAME"
}

# ── Step 6: Build and Deploy ───────────────────────────────────────────
deploy_services() {
    log "Building and deploying services..."

    cd "$APP_DIR"

    # Build images
    log "Building Docker images..."
    docker compose build --no-cache

    # Stop existing services
    log "Stopping existing services..."
    docker compose down

    # Start services
    log "Starting services..."
    docker compose up -d

    # Wait for health checks
    log "Waiting for services to be healthy..."
    sleep 30

    # Check service status
    docker compose ps

    success "Services deployed"
}

# ── Step 7: Initialize Database ────────────────────────────────────────
initialize_database() {
    log "Initializing database..."

    cd "$APP_DIR"

    # Run database initialization
    docker compose exec -T api python -c "
import asyncio
from src.infrastructure.database.models import create_tables
asyncio.run(create_tables())
print('Database tables created')
" || warning "Database initialization skipped (tables may already exist)"

    success "Database initialized"
}

# ── Step 8: Verify Deployment ──────────────────────────────────────────
verify_deployment() {
    log "Verifying deployment..."

    cd "$APP_DIR"

    # Check health endpoint
    HEALTH=$(curl -s http://localhost:8000/api/v1/health 2>/dev/null || echo "Failed")

    if echo "$HEALTH" | grep -q '"status"'; then
        success "API is healthy"
    else
        warning "API health check failed. Checking logs..."
        docker compose logs api --tail=20
    fi

    # Check all services
    log "Service status:"
    docker compose ps

    success "Deployment verification complete"
}

# ── Step 9: Setup Log Rotation ─────────────────────────────────────────
setup_log_rotation() {
    log "Setting up log rotation..."

    cat > /etc/logrotate.d/basira << EOF
$APP_DIR/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 basira basira
    sharedscripts
    postrotate
        docker compose -f $APP_DIR/docker-compose.yml restart api > /dev/null 2>&1 || true
    endscript
}
EOF

    success "Log rotation configured"
}

# ── Main Deployment Flow ───────────────────────────────────────────────
main() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "         Basira Production Deployment"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""

    check_prerequisites
    create_directories
    setup_repository
    configure_environment
    backup_data
    deploy_services
    initialize_database
    verify_deployment
    setup_log_rotation

    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "         Deployment Complete!"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    echo "  API:         http://localhost:8000"
    echo "  Dashboard:   http://localhost:8501"
    echo "  Health:      http://localhost:8000/api/v1/health"
    echo ""
    echo "  Logs:        docker compose -f $APP_DIR/docker-compose.yml logs -f"
    echo "  Status:      docker compose -f $APP_DIR/docker-compose.yml ps"
    echo "  Stop:        docker compose -f $APP_DIR/docker-compose.yml down"
    echo "  Restart:     docker compose -f $APP_DIR/docker-compose.yml restart"
    echo ""
    echo "  Edit config: nano $APP_DIR/.env"
    echo "  Backup:      $BACKUP_DIR"
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
}

# Run main function
main "$@"
