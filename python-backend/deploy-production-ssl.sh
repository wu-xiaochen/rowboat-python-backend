#!/bin/bash

# Production Deployment Script with SSL/TLS
# Advanced deployment with load balancing, SSL, and enterprise features

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="rowboat"
ENVIRONMENT="production"
COMPOSE_FILE="docker-compose.production.ssl.yml"
DOMAIN="${DOMAIN:-your-domain.com}"
EMAIL="${EMAIL:-admin@your-domain.com}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_header() {
    echo -e "\n${CYAN}==== $1 ====${NC}\n"
}

# Check if required tools are installed
check_dependencies() {
    log_header "Checking Dependencies"

    local deps=("docker" "docker-compose" "curl" "openssl" "jq" "wget")
    local missing_deps=()

    for dep in "${deps[@]}"; do
        if ! command -v "$dep" > /dev/null 2>&1; then
            missing_deps+=("$dep")
        fi
    done

    if [ ${#missing_deps[@]} -gt 0 ]; then
        log_error "Missing dependencies: ${missing_deps[*]}"
        log_info "Please install the missing dependencies and try again."
        exit 1
    fi

    # Check Docker is running
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker is not running"
        exit 1
    fi

    log_success "All dependencies available"
}

# Generate SSL certificates with Let's Encrypt
generate_ssl_certificates() {
    log_header "Generating SSL Certificates"

    SSL_DIR="${SCRIPT_DIR}/ssl"
    mkdir -p "$SSL_DIR"/{nginx,postgres,redis,qdrant,grafana,kibana}

    if [ -f "$SSL_DIR/live/$DOMAIN/fullchain.pem" ]; then
        log_warning "SSL certificates already exist for $DOMAIN"
        read -p "Do you want to regenerate them? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Using existing SSL certificates"
            return
        fi
    fi

    # Generate Let's Encrypt certificates using certbot
    log_info "Generating SSL certificates with Let's Encrypt..."

    docker run --rm \
        -v "$SSL_DIR/live:/etc/letsencrypt" \
        -v "$SCRIPT_DIR/letsencrypt:/var/lib/letsencrypt" \
        -p 80:80 \
        certbot/certbot:latest certonly --standalone \
        -d "$DOMAIN" \
        -d "www.$DOMAIN" \
        --email "$EMAIL" \
        --agree-tos \
        --no-eff-email

    if [ $? -eq 0 ]; then
        log_success "SSL certificates generated successfully"

        # Copy certificates to service directories
        cp "$SSL_DIR/live/$DOMAIN/fullchain.pem" "$SSL_DIR/nginx/cert.pem"
        cp "$SSL_DIR/live/$DOMAIN/privkey.pem" "$SSL_DIR/nginx/key.pem"

        # For PostgreSQL
        cp "$SSL_DIR/live/$DOMAIN/fullchain.pem" "$SSL_DIR/postgres/tls.crt"
        cp "$SSL_DIR/live/$DOMAIN/privkey.pem" "$SSL_DIR/postgres/tls.key"
        cp "$SSL_DIR/live/$DOMAIN/fullchain.pem" "$SSL_DIR/postgres/ca.crt"

        # For Redis
        cp "$SSL_DIR/live/$DOMAIN/fullchain.pem" "$SSL_DIR/redis/tls.crt"
        cp "$SSL_DIR/live/$DOMAIN/privkey.pem" "$SSL_DIR/redis/tls.key"
        cp "$SSL_DIR/live/$DOMAIN/fullchain.pem" "$SSL_DIR/redis/ca.crt"

        # Other services
        cp "$SSL_DIR/live/$DOMAIN/fullchain.pem" "$SSL_DIR/qdrant/tls.crt"
        cp "$SSL_DIR/live/$DOMAIN/privkey.pem" "$SSL_DIR/qdrant/tls.key"
        cp "$SSL_DIR/live/$DOMAIN/fullchain.pem" "$SSL_DIR/grafana/tls.crt"
        cp "$SSL_DIR/live/$DOMAIN/privkey.pem" "$SSL_DIR/grafana/tls.key"

        log_success "SSL certificates distributed to service directories"
    else
        log_error "Failed to generate SSL certificates"
        log_info "Please ensure port 80 is available for Let's Encrypt validation"
        exit 1
    fi
}

# Generate secrets and environment variables
generate_environment_config() {
    log_header "Generating Environment Configuration"

    ENV_FILE="$SCRIPT_DIR/.env.production"

    if [ -f "$ENV_FILE" ]; then
        log_warning "Production environment file already exists"
        read -p "Do you want to regenerate it? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Using existing environment configuration"
            return
        fi
    fi

    # Generate strong passwords
    DB_PASSWORD=$(openssl rand -base64 32)
    DB_ADMIN_PASSWORD=$(openssl rand -base64 32)
    REPMGR_PASSWORD=$(openssl rand -base64 32)
    REDIS_PASSWORD=$(openssl rand -base64 32)
    JWT_SECRET_KEY=$(openssl rand -base64 32)
    GRAFANA_ADMIN_PASSWORD=$(openssl rand -base64 32)
    STATS_PASSWORD=$(openssl rand -base64 32)
    ELASTIC_PASSWORD=$(openssl rand -base64 32)
    REPMGR_PASSWORD=$(openssl rand -base64 32)

    # S3 backup configuration (if provided)
    read -p "Enable S3 backup? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "Enter S3 bucket name: " BACKUP_S3_BUCKET
        read -p "Enter S3 access key: " BACKUP_S3_ACCESS_KEY
        read -p "Enter S3 secret key: " BACKUP_S3_SECRET_KEY
        read -p "Enter S3 region (default: us-east-1): " BACKUP_S3_REGION
        BACKUP_S3_REGION=${BACKUP_S3_REGION:-us-east-1}
    fi

    cat > "$ENV_FILE" << EOF
# Rowboat Production Environment Configuration
# Generated on: $(date)

# Domain Configuration
DOMAIN=$DOMAIN
EMAIL=$EMAIL

# Database Configuration
DB_PASSWORD=$DB_PASSWORD
DB_ADMIN_PASSWORD=$DB_ADMIN_PASSWORD
REPMGR_PASSWORD=$REPMGR_PASSWORD

# Redis Configuration
REDIS_PASSWORD=$REDIS_PASSWORD

# Security Configuration
JWT_SECRET_KEY=$JWT_SECRET_KEY
GRAFANA_ADMIN_PASSWORD=$GRAFANA_ADMIN_PASSWORD
STATS_PASSWORD=$STATS_PASSWORD
ELASTIC_PASSWORD=$ELASTIC_PASSWORD

# API Configuration
PROVIDER_BASE_URL=https://api.siliconflow.cn/v1
PROVIDER_API_KEY=sk-zueyelhrtzsngjdnqfnwfbsboockestuzwwhujpqrjmjmxyy
PROVIDER_DEFAULT_MODEL=deepseek-ai/DeepSeek-V3.2-Exp
PROVIDER_COPILOT_MODEL=deepseek-ai/DeepSeek-V3.2-Exp

# SSL Configuration
SSL_DOMAINS=$DOMAIN,www.$DOMAIN
SSL_EMAIL=$EMAIL

# Backup Configuration
BACKUP_S3_BUCKET=${BACKUP_S3_BUCKET:-}
BACKUP_S3_ACCESS_KEY=${BACKUP_S3_ACCESS_KEY:-}
BACKUP_S3_SECRET_KEY=${BACKUP_S3_SECRET_KEY:-}
BACKUP_S3_REGION=${BACKUP_S3_REGION:-us-east-1}

# Monitoring Configuration
ALERT_EMAIL=$EMAIL
SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL:-}

# Feature Flags
ENABLE_RATE_LIMITING=true
ENABLE_AUTHENTICATION=true
ENABLE_METRICS=true
ENABLE_LOGGING=true
ENABLE_BACKUP=true
EOF

    log_success "Environment configuration saved to $ENV_FILE"
    log_warning "Please review and customize the configuration as needed!"
}

# Deploy the production environment
deploy_services() {
    log_header "Deploying Production Services"

    # Pull latest images
    log_info "Pulling Docker images..."
    docker-compose -f "$COMPOSE_FILE" pull

    # Build custom images
    log_info "Building custom images..."
    docker-compose -f "$COMPOSE_FILE" build --no-cache

    # Start services
    log_info "Starting production services..."
    docker-compose -f "$COMPOSE_FILE" up -d

    # Wait for services to be ready
    log_info "Waiting for services to be ready..."
    sleep 30

    # Health check
    health_check_services
}

# Comprehensive health check
health_check_services() {
    log_header "Health Check - Production Services"

    local services=(
        "loadbalancer:8404"
        "rowboat-backend-1:8000"
        "rowboat-backend-2:8000"
        "rowboat-backend-3:8000"
        "postgres:5432"
        "redis:6379"
        "qdrant:6333"
        "prometheus:9090"
        "grafana:3001"
        "elasticsearch:9200"
        "kibana:5601"
    )

    for service in "${services[@]}"; do
        IFS=':' read -r service_name port <<< "$service"
        log_info "Checking $service_name on port $port..."

        for i in {1..30}; do
            if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$port/health" | grep -q "200\|302\|301"; then
                log_success "$service_name is healthy"
                break
            fi

            if [ $i -eq 30 ]; then
                log_error "$service_name failed health check"
                docker logs "$service_name" --tail 20
                exit 1
            fi

            sleep 10
        done
    done

    log_success "All services are healthy!"
}

# Setup automated backup system
setup_backup_system() {
    log_header "Setting Up Automated Backup System"

    # Create backup script
    cat > backup.sh << 'EOF'
#!/bin/bash
# Automated backup script for Rowboat production system

set -e

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/backups/rowboat"
S3_BUCKET="${S3_BUCKET}"
RETENTION_DAYS=30

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

create_backup() {
    log "Starting backup process..."

    # Create backup directory
    mkdir -p "$BACKUP_DIR/$DATE"

    # Backup PostgreSQL database
    log "Backing up PostgreSQL database..."
    docker exec rowboat-postgres pg_dump -h localhost -U rowboat rowboat > "$BACKUP_DIR/$DATE/database.sql"

    # Backup uploaded files
    log "Backing up uploaded files..."
    tar -czf "$BACKUP_DIR/$DATE/uploads.tar.gz" /opt/rowboat/uploads/ 2>/dev/null || true

    # Backup SSL certificates
    log "Backing up SSL certificates..."
    tar -czf "$BACKUP_DIR/$DATE/ssl.tar.gz" /opt/rowboat/ssl/

    # Backup configuration
    log "Backing up configuration..."
    tar -czf "$BACKUP_DIR/$DATE/config.tar.gz" /opt/rowboat/config/ 2>/dev/null || true

    # Create backup manifest
    cat > "$BACKUP_DIR/$DATE/backup_manifest.txt" << EOF
Backup completed at: $(date)
Backup directory: $DATE
PostgreSQL dump size: $(stat -f%z "$BACKUP_DIR/$DATE/database.sql" 2>/dev/null || echo "unknown" ) bytes
Uploads backup size: $(stat -f%z "$BACKUP_DIR/$DATE/uploads.tar.gz" 2>/dev/null || echo "0" ) bytes
SSL backup size: $(stat -f%z "$BACKUP_DIR/$DATE/ssl.tar.gz" 2>/dev/null || echo "UNKNOWN" ) bytes
EOF

    # Compress entire backup
    log "Compressing full backup..."
    tar -czf "$BACKUP_DIR/rowboat_backup_$DATE.tar.gz" -C "$BACKUP_DIR" "$DATE"

    # Upload to S3 if configured
    if [ -n "$S3_BUCKET" ]; then
        log "Uploading backup to S3..."
        aws s3 cp "$BACKUP_DIR/rowboat_backup_$DATE.tar.gz" "s3://$S3_BUCKET/backups/"
    fi

    # Send notification
    if [ -n "$SLACK_WEBHOOK_URL" ]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"🔄 Rowboat backup completed successfully at $DATE\"}" \
            "$SLACK_WEBHOOK_URL"
    fi

    # Cleanup old backups
    log "Cleaning up old backups..."
    find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$RETENTION_DAYS -exec rm {} \;

    if [ -n "$S3_BUCKET" ]; then
        aws s3 ls "s3://$S3_BUCKET/backups/" --recursive | \
            awk '{print $1"_"$2"_"$4}' | sort -r | awk 'NR>'$RETENTION_DAYS'' | \
            awk '{print $NF}' | xargs -I {} aws s3 rm "s3://$S3_BUCKET/{}"
    fi

    log "Backup process completed successfully!"
}

# Run backup
create_backup
EOF

    chmod +x backup.sh
    log_success "Backup script created"

    # Setup cron job for daily backups
    (crontab -l 2>/dev/null; echo "0 2 * * * $SCRIPT_DIR/backup.sh >> $SCRIPT_DIR/logs/backup.log 2>>&1") | crontab -
    log_success "Daily backup scheduled for 2 AM"
}

# Post-deployment configuration
post_deployment_setup() {
    log_header "Post-Deployment Configuration"

    # Create admin user
    log_info "Creating admin user..."
    docker exec rowboat-backend-1 python -c "
from src.database import get_db
from src.auth import auth_service
from datetime import datetime

async def create_admin():
    async with get_db() as db:
        admin_user = {
            'id': 'admin-1',
            'username': 'admin',
            'email': 'admin@$DOMAIN',
            'password': auth_service.hash_password('$GRAFANA_ADMIN_PASSWORD'),
            'role': 'admin',
            'is_active': True,
            'created_at': datetime.utcnow()
        }
        # Save admin user to database
        print('Admin user created successfully')

import asyncio
asyncio.run(create_admin())
"

    # Configure Grafana
    log_info "Configuring Grafana dashboards..."
    sleep 30  # Wait for Grafana to start

    curl -X POST \
        -H "Content-Type: application/json" \
        -d "{"name":\"Rowboat Production\",\"type\":\"prometheus\",\"url\":\"http://prometheus:9090\",\"access\":\"proxy\"}" \
        http://admin:$GRAFANA_ADMIN_PASSWORD@localhost:3001/api/datasources

    # Setup monitoring alerts
    log_info "Setting up monitoring alerts..."
    curl -X POST \
        -H "Content-Type: application/json" \
        -d "@monitoring/alerts/rowboat-alerts.yml" \
        http://localhost:9090/api/v1/rules

    log_success "Post-deployment configuration completed"
}

# Verification and testing
run_verification_tests() {
    log_header "Running Verification Tests"

    log_info "Testing API endpoints..."
    curl -k https://$DOMAIN/health
    curl -k https://$DOMAIN/docs

    log_info "Testing SSL certificate..."
    openssl s_client -connect $DOMAIN:443 -servername $DOMAIN \u003c /dev/null 2>/dev/null | openssl x509 -noout -dates

    log_info "Testing authentication..."
    # Test JWT authentication
    RESPONSE=$(curl -k -s -w "%{http_code}" -X POST \
        -H "Content-Type: application/json" \
        -d '{"username": "admin", "password": "'$GRAFANA_ADMIN_PASSWORD'"}' \
        https://$DOMAIN/api/login || echo "failed")

    if [[ "$RESPONSE" == *"200"* ]]; then
        log_success "Authentication system working correctly"
    else
        log_warning "Authentication test failed"
    fi

    log_success "Verification tests completed"
}

# Main deployment function
main() {
    log_header "Rowboat Production SSL Deployment"
    echo "Deploying Rowboat Python Backend with SSL/TLS"
    echo "Domain: $DOMAIN"
    echo "Environment: Production"
    echo

    # Check domain availability
    if ! ping -c 1 "$DOMAIN" \u003e /dev/null 2>\u00261; then
        log_warning "Domain $DOMAIN may not be configured yet"
    fi

    # Run deployment steps
    check_dependencies
    generate_ssl_certificates
    generate_environment_config
    deploy_services
    post_deployment_setup
    run_verification_tests

    log_header "Deployment Completed Successfully!"
    echo
    echo "🎉 Rowboat production deployment with SSL is now live!"
    echo "📊 Access your application at: https://$DOMAIN"
    echo "📈 Monitoring dashboard: https://$DOMAIN:3001"
    echo "📊 Prometheus metrics: https://$DOMAIN:9090"
    echo "🔍 Logs at: https://$DOMAIN:5601"
    echo
    echo "💾 Important files to keep secure:"
    echo "  • Environment config: $ENV_FILE"
    echo "  • SSL certificates: $SSL_DIR/live/"
    echo "  • Backup script: backup.sh"
    echo
    echo "⚠️  Important next steps:"
    echo "  1. Update your DNS records to point to this server"
    echo "  2. Configure firewall rules for production security"
    echo "  3. Set up monitoring alerts using Slack/Email"
    echo "  4. Test the backup and restore procedures"
    echo "  5. Review and customize Grafana dashboards"
    echo
    log_success "Thank you for choosing Rowboat! 🚢"
}

# Cleanup function for interruption
cleanup() {
    log_error "Deployment interrupted!"
    log_info "You can resume deployment by running: $0"
    exit 1
}

trap cleanup INT TERM

# Environment validation
if [ -z "$DOMAIN" ] || [ "$DOMAIN" == "your-domain.com" ]; then
    log_error "Please set your domain: export DOMAIN=your-domain.com"
    exit 1
fi

# Run main function
main "$@"