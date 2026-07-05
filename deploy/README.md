# 🚀 JAMA CRM Deployment Guide

## Quick Start (1 Command)

### Setup New VPS
```bash
# SSH into your VPS, then:
curl -sL https://raw.githubusercontent.com/anhthien8/jamaerp/main/deploy/setup.sh | sudo bash -s your-domain.com your-email@gmail.com
```

### Or clone & run locally
```bash
git clone https://github.com/anhthien8/jamaerp.git
cd jamaerp/deploy
sudo bash setup.sh your-domain.com your-email@gmail.com
```

## What the Script Does

| Step | Action |
|------|--------|
| 1 | Updates system & installs packages |
| 2 | Installs Docker & Docker Compose |
| 3 | Clones JAMA CRM repository |
| 4 | Configures environment (.env) |
| 5 | Sets up Nginx reverse proxy |
| 6 | Configures SSL with Let's Encrypt |
| 7 | Configures firewall (UFW) |
| 8 | Configures Fail2ban (security) |
| 9 | Deploys all services |
| 10 | Creates management scripts |

## Prerequisites

- **VPS Provider:** DigitalOcean, Vultr, Hetzner, Linode, or any Linux VPS
- **OS:** Ubuntu 22.04 LTS or Debian 12
- **RAM:** Minimum 2GB (4GB recommended)
- **Domain:** Optional but recommended (for SSL)

## After Deployment

### 1. Configure Telegram Bot (Optional)
```bash
cd /opt/jama-crm
nano .env
# Add: TELEGRAM_BOT_TOKEN=your_token_here
./restart.sh
```

### 2. Configure AI Agents (Optional)
```bash
cd /opt/jama-crm
nano .env
# Add: LLM_API_KEY=your_api_key_here
./restart.sh
```

## Management Commands

| Command | Description |
|---------|-------------|
| `./status.sh` | Check service status & health |
| `./restart.sh` | Restart all services |
| `./update.sh` | Pull latest code & rebuild |
| `./logs.sh backend` | View backend logs |
| `./logs.sh frontend` | View frontend logs |
| `./logs.sh telegram-bot` | View bot logs |

## Service URLs

| Service | URL |
|---------|-----|
| Web App | `https://your-domain.com` |
| API Docs | `https://your-domain.com/docs` |
| Health Check | `https://your-domain.com/health` |
| Backend Direct | `http://your-vps-ip:8000` |

## Troubleshooting

### Services won't start
```bash
cd /opt/jama-crm
docker compose -f docker-compose.prod.yml logs
```

### Port 80/443 already in use
```bash
# Stop nginx/apache if installed
sudo systemctl stop nginx
sudo systemctl stop apache2
# Then restart JAMA CRM
./restart.sh
```

### Database issues
```bash
# Check postgres
docker compose -f docker-compose.prod.yml exec postgres psql -U jama -d jama_crm
```

### Reset everything
```bash
cd /opt/jama-crm
docker compose -f docker-compose.prod.yml down -v  # Remove volumes too
sudo bash setup.sh your-domain.com your-email@gmail.com
```

## VPS Providers (Recommended)

| Provider | Starting Price | Best For |
|----------|---------------|----------|
| [Hetzner](https://hetzner.com) | €3.29/mo | Best value |
| [Vultr](https://vultr.com) | $2.50/mo | Global locations |
| [DigitalOcean](https://digitalocean.com) | $4/mo | Easy to use |
| [Linode](https://linode.com) | $5/mo | Stable & support |
