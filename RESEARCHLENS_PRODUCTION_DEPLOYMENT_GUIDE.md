# ResearchLens — Production Deployment & Operations Guide

**Document ID:** `RESEARCHLENS_PRODUCTION_DEPLOYMENT_GUIDE.md`  
**Target Architecture:** Linux (Ubuntu 22.04 LTS / Fedora 40 / RHEL 9), Nginx, Gunicorn + Uvicorn Workers, PostgreSQL 16, Podman/Docker, Ollama  
**Version:** 1.0.0 (Production Release Candidate)

---

## 1. Production Architecture Overview

In production, ResearchLens separates the presentation layer, application server, persistent relational database, vector index, and local AI daemon into isolated, resilient services.

```
                      Internet / Campus Network
                                 │
                                 ▼ (HTTPS: 443)
                      ┌──────────────────────┐
                      │  Nginx Reverse Proxy │
                      │  TLS Termination     │
                      └──────────┬───────────┘
                                 │
               ┌─────────────────┴─────────────────┐
               │                                   │
               ▼ /                                 ▼ /api/v1/
   ┌──────────────────────┐             ┌──────────────────────┐
   │ Frontend Static Site │             │ FastAPI Backend      │
   │ (Vite Production     │             │ Gunicorn + Uvicorn   │
   │  Build: HTML/JS/CSS) │             │ (4 Worker Processes) │
   └──────────────────────┘             └──────────┬───────────┘
                                                   │
                  ┌────────────────────────────────┼────────────────────────────────┐
                  │                                │                                │
                  ▼ (Port 5432)                    ▼ (Local Filesystem)             ▼ (Port 11434)
      ┌──────────────────────┐         ┌──────────────────────┐         ┌──────────────────────┐
      │ PostgreSQL 16        │         │ FAISS Vector Index   │         │ Ollama Local AI      │
      │ (Podman / Systemd)   │         │ (768-dim SPECTER2)   │         │ (qwen2.5:3b)         │
      └──────────────────────┘         └──────────────────────┘         └──────────────────────┘
```

> [!IMPORTANT]
> Never expose the Vite development server (`npm run dev`) or an unauthenticated PostgreSQL port to the public internet. The production bundle must be compiled and served via Nginx.

---

## 2. Environment Configuration

### 2.1 Production `.env` Specification
Create `/opt/researchlens/backend/.env` with production permissions (`chmod 600`):

```bash
# Environment Mode
ENVIRONMENT=production
APP_NAME=research-paper-recommender
VERSION=1.0.0

# Database Configuration (PostgreSQL 16)
DATABASE_URL=postgresql+psycopg2://researchlens_prod:SECURE_PASSWORD@127.0.0.1:5432/research_papers_prod

# Cryptographic Security (Must be >= 32 high-entropy characters)
JWT_SECRET_KEY=c47f89d31a5e92b0e6371c56b798e21f480ad12389cf7b44a29081e7d23a105f
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Local AI Engine (Ollama)
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:3b

# Strict Research Privacy Invariant
RESEARCHLENS_ALLOW_CLOUD_RESEARCH_CONTENT=false

# CORS & Domain Boundaries
CORS_ORIGINS=["https://researchlens.institution.edu"]
ALLOWED_HOSTS=["researchlens.institution.edu", "127.0.0.1"]

# Rate Limiting & Resource Caps
RATE_LIMIT_PER_MINUTE=120
MAX_UPLOAD_SIZE_BYTES=26214400  # 25 MB
```

---

## 3. Build & Compilation Procedures

### 3.1 Backend Virtual Environment
```bash
cd /opt/researchlens/backend
python3 -m venv venv
./venv/bin/pip install --upgrade pip setuptools wheel
./venv/bin/pip install -r requirements.txt
```

### 3.2 Frontend Production Bundle
```bash
cd /opt/researchlens/frontend
npm ci
npm run build
# Verified output generated in frontend/dist/ (HTML, JS, CSS)
```

---

## 4. Service Supervision & Systemd Units

### 4.1 Backend Service: `/etc/systemd/system/researchlens-backend.service`
```ini
[Unit]
Description=ResearchLens FastAPI Backend Server
After=network.target postgresql.service ollama.service

[Service]
Type=exec
User=researchlens
Group=researchlens
WorkingDirectory=/opt/researchlens/backend
EnvironmentFile=/opt/researchlens/backend/.env
ExecStart=/opt/researchlens/backend/venv/bin/gunicorn app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000 \
    --access-logfile /var/log/researchlens/access.log \
    --error-logfile /var/log/researchlens/error.log \
    --graceful-timeout 30 \
    --timeout 120

Restart=always
RestartSec=5s
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
```

### 4.2 Nginx Reverse Proxy Configuration: `/etc/nginx/sites-available/researchlens.conf`
```nginx
server {
    listen 80;
    server_name researchlens.institution.edu;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name researchlens.institution.edu;

    ssl_certificate /etc/letsencrypt/live/researchlens.institution.edu/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/researchlens.institution.edu/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security Headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; img-src 'self' data: https:; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self';" always;

    # Frontend Static SPA
    root /opt/researchlens/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # API Reverse Proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_buffering off;
    }

    client_max_body_size 25M;
}
```

---

## 5. Backup, Restoration & Disaster Recovery

### 5.1 Relational Database Backup (PostgreSQL)
Execute automated daily backup via cron:
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/researchlens/postgres"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/researchlens_db_$TIMESTAMP.sql.gz"

podman exec -t postgres_container pg_dump -U postgres research_papers | gzip -9 > "$BACKUP_FILE"
chmod 600 "$BACKUP_FILE"

# Keep last 14 days of backups
find "$BACKUP_DIR" -type f -name "*.sql.gz" -mtime +14 -delete
```

### 5.2 FAISS Vector Store Backup
FAISS index and metadata files must be backed up concurrently:
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/researchlens/faiss"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DEST="$BACKUP_DIR/faiss_$TIMESTAMP"
mkdir -p "$DEST"

cp -p /opt/researchlens/backend/data/processed/faiss/research_index.faiss "$DEST/"
cp -p /opt/researchlens/backend/data/processed/faiss/papers_meta.json "$DEST/"

# Compute verification checksums
sha256sum "$DEST"/* > "$DEST/checksums.sha256"
```

### 5.3 Disaster Recovery Verification
To test restoration into an isolated staging database:
```bash
# 1. Create temporary test database
createdb -U postgres researchlens_restore_test

# 2. Restore snapshot
gunzip -c /var/backups/researchlens/postgres/researchlens_db_latest.sql.gz | psql -U postgres -d researchlens_restore_test

# 3. Verify record counts
psql -U postgres -d researchlens_restore_test -c "SELECT count(*) FROM papers; SELECT count(*) FROM users;"

# 4. Cleanup
dropdb -U postgres researchlens_restore_test
```

---

## 6. Health Monitoring & Observability

### 6.1 Readiness Probes
The backend exposes `/api/v1/health` providing immediate readiness assessment:
```bash
$ curl -s http://127.0.0.1:8000/api/v1/health
{"status":"ok","service":"research-paper-recommender","version":"0.1.0","environment":"production","database":"connected"}
```

### 6.2 Vector Index Status
Authenticated administrators can query synchronization metrics:
```bash
$ curl -s -H "Authorization: Bearer <ADMIN_TOKEN>" http://127.0.0.1:8000/api/v1/papers/index-status
```

---

## 7. Rollback Runbook

If a critical incident occurs post-deployment:
1. **Stop Application Server:**
   ```bash
   sudo systemctl stop researchlens-backend
   ```
2. **Revert Frontend Assets:**
   ```bash
   cp -r /opt/researchlens/frontend/dist.previous /opt/researchlens/frontend/dist
   sudo systemctl reload nginx
   ```
3. **Restore FAISS Index:**
   ```bash
   cp /var/backups/researchlens/faiss/latest/* /opt/researchlens/backend/data/processed/faiss/
   ```
4. **Restore PostgreSQL Database:**
   ```bash
   psql -U postgres -d research_papers < /var/backups/researchlens/postgres/latest.sql
   ```
5. **Restart & Validate:**
   ```bash
   sudo systemctl start researchlens-backend
   curl -f http://127.0.0.1:8000/api/v1/health || exit 1
   ```
