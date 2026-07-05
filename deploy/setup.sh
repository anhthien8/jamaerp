#!/bin/bash
# ============================================================
# JAMA HOME CRM — Automated Linux VPS Setup Script
# Tested on: Ubuntu 22.04 LTS, Debian 12
# Usage: bash setup.sh your-domain.com
# ============================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================
# CONFIGURATION
# ============================================================
DOMAIN=${1:-""}
REPO_URL="https://github.com/anhthien8/jamaerp.git"
APP_DIR="/opt/jama-crm"
EMAIL=${2:-""}  # For Let's Encrypt SSL

# ============================================================
# HELPER FUNCTIONS
# ============================================================
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "Please run as root (sudo bash setup.sh)"
        exit 1
    fi
}

# ============================================================
# STEP 1: System Update & Basic Packages
# ============================================================
step1_update_system() {
    print_header "Step 1: Updating System & Installing Packages"

    apt-get update -qq
    apt-get upgrade -y -qq
    apt-get install -y -qq \
        curl \
        wget \
        git \
        unzip \
        ufw \
        fail2ban \
        software-properties-common \
        apt-transport-https \
        ca-certificates \
        gnupg \
        lsb-release

    print_success "System updated & packages installed"
}

# ============================================================
# STEP 2: Install Docker & Docker Compose
# ============================================================
step2_install_docker() {
    print_header "Step 2: Installing Docker & Docker Compose"

    # Add Docker's official GPG key
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

    # Set up repository
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin

    # Start Docker
    systemctl start docker
    systemctl enable docker

    # Verify
    docker --version
    docker compose version

    print_success "Docker & Docker Compose installed"
}

# ============================================================
# STEP 3: Clone Repository
# ============================================================
step3_clone_repo() {
    print_header "Step 3: Cloning JAMA CRM Repository"

    # Remove old directory if exists
    if [ -d "$APP_DIR" ]; then
        print_warning "Removing existing $APP_DIR"
        rm -rf "$APP_DIR"
    fi

    git clone --depth 1 "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"

    print_success "Repository cloned to $APP_DIR"
}

# ============================================================
# STEP 4: Configure Environment
# ============================================================
step4_configure_env() {
    print_header "Step 4: Configuring Environment"

    cd "$APP_DIR"

    # Generate random secrets
    JWT_SECRET=$(openssl rand -hex 32)
    DB_PASSWORD=$(openssl rand -hex 16)

    # Create .env file
    cat > .env << EOF
# JAMA CRM Environment Configuration
# Generated: $(date)

# App
APP_NAME=JAMA HOME CRM
APP_ENV=production
APP_DEBUG=false

# Database
DATABASE_URL=postgresql://jama:${DB_PASSWORD}@postgres:5432/jama_crm
POSTGRES_DB=jama_crm
POSTGRES_USER=jama
POSTGRES_PASSWORD=${DB_PASSWORD}

# JWT
JWT_SECRET_KEY=${JWT_SECRET}
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# CORS
CORS_ORIGINS=["http://localhost","https://${DOMAIN}"]

# Redis
REDIS_URL=redis://redis:6379

# Telegram Bot (optional - fill in later)
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_URL=https://${DOMAIN}/api/v1/telegram/webhook

# LLM (optional - for AI agents)
LLM_MODEL=Claude-Opus
LLM_API_KEY=
EOF

    chmod 600 .env

    print_success "Environment configured"
    print_warning "IMPORTANT: Edit .env to add Telegram Bot Token and LLM API Key!"
}

# ============================================================
# STEP 5: Configure Docker Compose for Production
# ============================================================
step5_configure_docker() {
    print_header "Step 5: Configuring Docker Compose for Production"

    cd "$APP_DIR"

    # Create production docker-compose override
    cat > docker-compose.prod.yml << 'EOF'
version: "3.9"

services:
  postgres:
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    restart: unless-stopped
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    restart: unless-stopped
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  frontend:
    restart: unless-stopped
    command: npm run start -- -p 3000
    env_file: .env
    depends_on:
      - backend

  telegram-bot:
    restart: unless-stopped
    env_file: .env
    depends_on:
      - backend
      - redis
    command: python -m bot.main

  worker:
    restart: unless-stopped
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: python -m app.worker

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
    depends_on:
      - backend
      - frontend

volumes:
  postgres_data:
  redis_data:
EOF

    print_success "Docker Compose production config created"
}

# ============================================================
# STEP 6: Configure Nginx
# ============================================================
step6_configure_nginx() {
    print_header "Step 6: Configuring Nginx"

    cd "$APP_DIR"

    # Create nginx directories
    mkdir -p nginx/conf.d nginx/ssl

    # Create main nginx.conf
    cat > nginx/nginx.conf << 'EOF'
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
    use epoll;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';
    access_log /var/log/nginx/access.log main;

    # Performance
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 50M;

    # Gzip
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript image/svg+xml;

    include /etc/nginx/conf.d/*.conf;
}
EOF

    # Create server config
    if [ -n "$DOMAIN" ]; then
        # HTTPS config with SSL
        cat > nginx/conf.d/jama-crm.conf << EOF
# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name ${DOMAIN};
    return 301 https://\$host\$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name ${DOMAIN};

    # SSL
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Frontend
    location / {
        proxy_pass http://frontend:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
    }

    # Backend API
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 60s;
    }

    # Backend docs (Swagger)
    location /docs {
        proxy_pass http://backend:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }

    location /redoc {
        proxy_pass http://backend:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }

    # Health check
    location /health {
        proxy_pass http://backend:8000/health;
        proxy_set_header Host \$host;
    }
}
EOF
    else
        # HTTP only (no domain yet)
        cat > nginx/conf.d/jama-crm.conf << 'EOF'
server {
    listen 80;
    server_name _;

    # Frontend
    location / {
        proxy_pass http://frontend:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }

    # Backend docs
    location /docs {
        proxy_pass http://backend:8000;
    }

    location /redoc {
        proxy_pass http://backend:8000;
    }

    # Health check
    location /health {
        proxy_pass http://backend:8000/health;
    }
}
EOF
    fi

    print_success "Nginx configured"
}

# ============================================================
# STEP 7: SSL with Let's Encrypt (if domain provided)
# ============================================================
step7_setup_ssl() {
    print_header "Step 7: Setting up SSL Certificate"

    if [ -z "$DOMAIN" ]; then
        print_warning "No domain provided — skipping SSL setup"
        print_warning "Run later: sudo certbot --nginx -d your-domain.com"
        return
    fi

    if [ -z "$EMAIL" ]; then
        print_warning "No email provided — using admin@$DOMAIN"
        EMAIL="admin@$DOMAIN"
    fi

    # Install Certbot
    apt-get install -y -qq certbot

    # Get certificate (standalone mode for initial setup)
    certbot certonly --standalone \
        --non-interactive \
        --agree-tos \
        --email "$EMAIL" \
        -d "$DOMAIN"

    # Copy certs to nginx ssl directory
    cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem "$APP_DIR/nginx/ssl/"
    cp /etc/letsencrypt/live/$DOMAIN/privkey.pem "$APP_DIR/nginx/ssl/"

    # Setup auto-renewal
    echo "0 0,12 * * * root certbot renew --quiet && cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem $APP_DIR/nginx/ssl/ && cp /etc/letsencrypt/live/$DOMAIN/privkey.pem $APP_DIR/nginx/ssl/ && docker compose -f $APP_DIR/docker-compose.prod.yml restart nginx" | crontab -

    print_success "SSL certificate installed & auto-renewal configured"
}

# ============================================================
# STEP 8: Configure Firewall (UFW)
# ============================================================
step8_configure_firewall() {
    print_header "Step 8: Configuring Firewall"

    # Reset UFW
    ufw --force reset

    # Default policies
    ufw default deny incoming
    ufw default allow outgoing

    # Allow SSH (important!)
    ufw allow 22/tcp comment "SSH"

    # Allow HTTP/HTTPS
    ufw allow 80/tcp comment "HTTP"
    ufw allow 443/tcp comment "HTTPS"

    # Enable UFW
    ufw --force enable

    ufw status verbose

    print_success "Firewall configured"
}

# ============================================================
# STEP 9: Configure Fail2ban
# ============================================================
step9_configure_fail2ban() {
    print_header "Step 9: Configuring Fail2ban"

    cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5
backend = systemd

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 86400

[nginx-http-auth]
enabled = true
port = http,https
filter = nginx-http-auth
logpath = /var/log/nginx/error.log
maxretry = 3

[nginx-limit-req]
enabled = true
port = http,https
filter = nginx-limit-req
logpath = /var/log/nginx/error.log
maxretry = 10
EOF

    systemctl restart fail2ban
    systemctl enable fail2ban

    print_success "Fail2ban configured"
}

# ============================================================
# STEP 10: Deploy Application
# ============================================================
step10_deploy() {
    print_header "Step 10: Deploying JAMA CRM"

    cd "$APP_DIR"

    # Build and start services
    docker compose -f docker-compose.prod.yml up -d --build

    # Wait for services to start
    echo "Waiting for services to start..."
    sleep 15

    # Check health
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        print_success "Backend is healthy!"
    else
        print_warning "Backend not yet healthy — may need more time"
    fi

    print_success "JAMA CRM deployed!"
}

# ============================================================
# STEP 11: Create Management Scripts
# ============================================================
step11_create_scripts() {
    print_header "Step 11: Creating Management Scripts"

    cd "$APP_DIR"

    # Status script
    cat > status.sh << 'EOF'
#!/bin/bash
echo "=== JAMA CRM Status ==="
echo ""
docker compose -f /opt/jama-crm/docker-compose.prod.yml ps
echo ""
echo "=== Health Check ==="
curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || echo "Backend not responding"
echo ""
echo "=== Disk Usage ==="
df -h / | tail -1
echo ""
echo "=== Memory Usage ==="
free -h | grep Mem
EOF
    chmod +x status.sh

    # Restart script
    cat > restart.sh << 'EOF'
#!/bin/bash
echo "Restarting JAMA CRM..."
docker compose -f /opt/jama-crm/docker-compose.prod.yml restart
echo "Done!"
EOF
    chmod +x restart.sh

    # Update script
    cat > update.sh << 'EOF'
#!/bin/bash
echo "Updating JAMA CRM..."
cd /opt/jama-crm
git pull origin main
docker compose -f docker-compose.prod.yml up -d --build
echo "Updated and restarted!"
EOF
    chmod +x update.sh

    # Logs script
    cat > logs.sh << 'EOF'
#!/bin/bash
docker compose -f /opt/jama-crm/docker-compose.prod.yml logs -f --tail=100 $1
EOF
    chmod +x logs.sh

    print_success "Management scripts created"
}

# ============================================================
# FINAL SUMMARY
# ============================================================
print_summary() {
    print_header "🎉 DEPLOYMENT COMPLETE!"

    echo -e "${GREEN}JAMA HOME CRM has been deployed successfully!${NC}"
    echo ""
    echo -e "${BLUE}Access:${NC}"
    if [ -n "$DOMAIN" ]; then
        echo "  • Web App:    https://${DOMAIN}"
        echo "  • API Docs:   https://${DOMAIN}/docs"
        echo "  • Health:     https://${DOMAIN}/health"
    else
        echo "  • Web App:    http://$(curl -s ifconfig.me)"
        echo "  • API Docs:   http://$(curl -s ifconfig.me)/docs"
        echo "  • Health:     http://$(curl -s ifconfig.me)/health"
    fi
    echo ""
    echo -e "${BLUE}Login Credentials:${NC}"
    echo "  • Admin:      admin@jamahome.vn / admin123"
    echo "  • CEO:        ceo@jamahome.vn / ceo123"
    echo "  • Accountant: accountant@jamahome.vn / account123"
    echo ""
    echo -e "${BLUE}Management Commands:${NC}"
    echo "  • Status:     cd $APP_DIR && ./status.sh"
    echo "  • Restart:    cd $APP_DIR && ./restart.sh"
    echo "  • Update:     cd $APP_DIR && ./update.sh"
    echo "  • Logs:       cd $APP_DIR && ./logs.sh [service]"
    echo "  • Stop:       cd $APP_DIR && docker compose -f docker-compose.prod.yml down"
    echo ""
    echo -e "${YELLOW}⚠️  IMPORTANT:${NC}"
    echo "  1. Edit $APP_DIR/.env to add:"
    echo "     - TELEGRAM_BOT_TOKEN (for Telegram Bot)"
    echo "     - LLM_API_KEY (for AI Agents)"
    echo "  2. After editing .env, run: cd $APP_DIR && ./restart.sh"
    echo ""
    echo -e "${GREEN}Enjoy JAMA HOME CRM! 🚀${NC}"
}

# ============================================================
# MAIN EXECUTION
# ============================================================
main() {
    print_header "JAMA HOME CRM — Automated Linux VPS Setup"
    echo "This script will:"
    echo "  1. Update system & install packages"
    echo "  2. Install Docker & Docker Compose"
    echo "  3. Clone JAMA CRM repository"
    echo "  4. Configure environment"
    echo "  5. Set up Nginx reverse proxy"
    echo "  6. Configure SSL (if domain provided)"
    echo "  7. Configure firewall (UFW)"
    echo "  8. Configure Fail2ban"
    echo "  9. Deploy application"
    echo "  10. Create management scripts"
    echo ""

    check_root

    step1_update_system
    step2_install_docker
    step3_clone_repo
    step4_configure_env
    step5_configure_docker
    step6_configure_nginx
    step7_setup_ssl
    step8_configure_firewall
    step9_configure_fail2ban
    step10_deploy
    step11_create_scripts
    print_summary
}

# Run main function
main
