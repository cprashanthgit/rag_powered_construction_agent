# 🏗️ Construction RAG Assistant — Complete GCP Deployment Guide

**From zero to a working cloud system, step by step.**

> This document covers everything: what code changes were made to make the project cloud-ready, how to set up GCP from scratch, how to deploy all services, how to connect Streamlit Cloud, and how to verify the entire system is working end-to-end.

---

## 📋 Table of Contents

1. [What We Changed to Make It Cloud-Ready](#1-what-we-changed-to-make-it-cloud-ready)
2. [What Gets Deployed Where](#2-what-gets-deployed-where)
3. [Prerequisites — Before You Start](#3-prerequisites--before-you-start)
4. [Phase A — GCP Account Setup](#4-phase-a--gcp-account-setup)
5. [Phase B — Create the GCP VM](#5-phase-b--create-the-gcp-vm)
6. [Phase C — Set Up the VM](#6-phase-c--set-up-the-vm)
7. [Phase D — Configure Your Secrets](#7-phase-d--configure-your-secrets)
8. [Phase E — SSL Certificate](#8-phase-e--ssl-certificate)
9. [Phase F — Deploy All Services](#9-phase-f--deploy-all-services)
10. [Phase G — Deploy Streamlit Cloud](#10-phase-g--deploy-streamlit-cloud)
11. [Phase H — Post-Deployment Testing](#11-phase-h--post-deployment-testing)
12. [Troubleshooting](#12-troubleshooting)
13. [Monthly Maintenance](#13-monthly-maintenance)

---

## 1. What We Changed to Make It Cloud-Ready

Before touching any cloud infrastructure, these specific changes were made to the project codebase.

### Change 1 — `app.py` (Line 29): API URL is now configurable

**Before:**
```python
API_BASE = "http://localhost:8000"
```

**After:**
```python
def _get_api_base() -> str:
    try:
        return st.secrets["API_BASE_URL"]      # Streamlit Cloud secret
    except Exception:
        return os.environ.get("API_BASE_URL", "http://localhost:8000")

API_BASE = _get_api_base()
```

**Why this matters:** Streamlit Community Cloud is a completely different server from your GCP VM. The old hardcoded `localhost:8000` would never resolve. Now, Streamlit reads the backend URL from its secrets manager at runtime, while local development still defaults to localhost automatically.

---

### Change 2 — `deploy/` folder created (all cloud files in one place)

Six new files were created inside `deploy/`:

| File | Purpose |
|---|---|
| `deploy/Dockerfile` | Builds FastAPI + all Python dependencies into a Docker image |
| `deploy/docker-compose.cloud.yml` | Starts all 6 services: API, Nginx, Redis, PostgreSQL, Prometheus, Grafana |
| `deploy/nginx.conf` | Handles HTTPS termination, redirects HTTP → HTTPS, proxies to FastAPI |
| `deploy/prometheus.cloud.yml` | Prometheus scrapes `api:8000` (Docker network) not `localhost:8000` |
| `deploy/.env.cloud.example` | Template for all production secrets (you fill in real values on VM) |
| `deploy/streamlit-secrets.example.toml` | Template for Streamlit Cloud secrets (just the backend URL) |

**Why a separate `deploy/` folder:** Keeps cloud infrastructure completely separate from application code. Your project root stays clean. When you're done with cloud, you can deploy or ignore this folder independently.

---

### Change 3 — Prometheus scrape target changed

**Local `monitoring/prometheus.yml`:**
```yaml
targets: ['host.docker.internal:8000']   # reaches your laptop's FastAPI process
```

**Cloud `deploy/prometheus.cloud.yml`:**
```yaml
targets: ['api:8000']   # FastAPI is now a container on the same Docker network
```

**Why this matters:** In local dev, FastAPI runs as a bare Python process outside Docker. In cloud, FastAPI is a container. `host.docker.internal` doesn't exist inside GCP's Docker network — Prometheus would get no metrics at all without this fix.

---

### Change 4 — `deploy/docker-compose.cloud.yml` adds FastAPI as a container

In local dev, you ran FastAPI with `uvicorn api:app --port 8000` in a separate terminal. On cloud, there's no terminal to leave running — FastAPI must be a container managed by Docker Compose.

The cloud compose adds:
```yaml
api:
  build:
    context: ..              # project root
    dockerfile: deploy/Dockerfile
  env_file: ./deploy/.env.prod
  volumes:
    - ../vector_store:/app/vector_store:ro   # your chunks.pkl
    - model_cache:/root/.cache               # cross-encoder model cache
```

---

### Change 5 — Nginx added as HTTPS gateway

Locally, you accessed FastAPI directly on port 8000 over HTTP. In cloud:
- Streamlit Cloud **requires HTTPS** — browsers block HTTP calls from HTTPS pages
- Port 8000 is **not exposed to the internet** — only Nginx on port 443 is

Nginx sits in front of FastAPI, handles SSL certificates, and proxies requests internally:
```
Internet (HTTPS:443) → Nginx → FastAPI (HTTP:8000, internal Docker network)
```

---

## 2. What Gets Deployed Where

```
┌─────────────────────────────────────────────────────────────┐
│  STREAMLIT COMMUNITY CLOUD (free, hosted by Streamlit)      │
│  URL: https://your-app.streamlit.app                        │
│  File: app.py                                               │
│  Secret: API_BASE_URL = "https://your-gcp-domain.com"       │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS API calls
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  GCP VM — e2-standard-2 (2 vCPU, 8GB RAM)                  │
│  $0 for 90 days ($300 free credits)                         │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Nginx (port 443, HTTPS + SSL cert)                  │   │
│  │   └─→ FastAPI container (port 8000, internal)       │   │
│  │         ├── Redis container (semantic cache)        │   │
│  │         ├── PostgreSQL container (query logs)       │   │
│  │         ├── Prometheus container (metrics)          │   │
│  │         └── Grafana container (port 3000, you only) │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  External services (already cloud):                        │
│  ├── Pinecone (vector search) — no change needed           │
│  └── OpenAI API (LLM + embeddings) — no change needed      │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Prerequisites — Before You Start

Make sure you have these ready on your laptop:

- [ ] Your project pushed to GitHub (public or private)
- [ ] `vector_store/chunks.pkl` file exists locally (check: `dir vector_store\chunks.pkl`)
- [ ] OpenAI API key (from platform.openai.com)
- [ ] Pinecone API key (from pinecone.io)
- [ ] A Google account (Gmail is fine)
- [ ] Git installed on your laptop
- [ ] `gcloud` CLI installed (optional but recommended — download from cloud.google.com/sdk)

---

## 4. Phase A — GCP Account Setup

**Time: ~30 minutes**

### Step A1 — Create GCP Account and Claim Free Credits

1. Open your browser and go to: **https://console.cloud.google.com**
2. Sign in with your Google account
3. You'll see a banner: **"Try Google Cloud for free — $300 in credits"**
4. Click **"Try for free"**
5. Fill in the form:
   - Country: United States
   - Terms: Accept
   - Payment info: Enter a credit card (required for identity verification — you will NOT be charged during the free trial)
6. Click **"Start my free trial"**

> **Important:** GCP will NOT charge your card during the 90-day trial. Credits are consumed first. You'll get an email before charges begin.

### Step A2 — Create a New Project

1. Once logged in, click the **project dropdown** at the top-left (it says "My First Project" or similar)
2. Click **"New Project"**
3. Fill in:
   - **Project name:** `cnst-rag-assistant`
   - **Project ID:** auto-generated (leave as-is)
4. Click **"Create"**
5. Wait ~10 seconds, then click the notification to **"Select Project"**

### Step A3 — Enable Compute Engine API

1. In the GCP Console, click the **hamburger menu** (☰) at the top-left
2. Click **"APIs & Services"** → **"Enable APIs and Services"**
3. In the search box, type: `Compute Engine API`
4. Click on **"Compute Engine API"**
5. Click **"Enable"**
6. Wait ~1 minute for it to activate

---

## 5. Phase B — Create the GCP VM

**Time: ~15 minutes**

### Step B1 — Open VM Instances

1. Click ☰ → **"Compute Engine"** → **"VM Instances"**
2. Click **"Create Instance"** (blue button)

### Step B2 — Configure the VM

Fill in these exact settings:

**Basics:**
| Field | Value |
|---|---|
| Name | `cnst-backend` |
| Region | `us-central1 (Iowa)` — cheapest US region |
| Zone | `us-central1-a` |

**Machine Configuration:**
| Field | Value |
|---|---|
| Machine family | General purpose |
| Series | E2 |
| Machine type | **e2-standard-2** (2 vCPU, 8 GB RAM) |

> ⚠️ Do NOT choose e2-micro or e2-small — your system needs 8GB RAM comfortably.

**Boot Disk:**
1. Click **"Change"** next to Boot disk
2. OS: **Ubuntu**
3. Version: **Ubuntu 22.04 LTS**
4. Boot disk type: **SSD persistent disk**
5. Size: **50 GB**
6. Click **"Select"**

**Firewall:**
- ✅ Check **"Allow HTTP traffic"**
- ✅ Check **"Allow HTTPS traffic"**

Click **"Create"** at the bottom.

Wait ~2 minutes. You'll see your VM in the list with a green circle ✅.

### Step B3 — Note Your VM's External IP

In the VM Instances list, find `cnst-backend`. Under **"External IP"**, note the IP address (e.g., `34.123.45.67`). You'll need this later.

### Step B4 — Open Grafana Port (for your access only)

Grafana runs on port 3000. You want to access it but not expose it publicly.

1. Click ☰ → **"VPC Network"** → **"Firewall"**
2. Click **"Create Firewall Rule"**
3. Fill in:
   - Name: `allow-grafana-myip`
   - Targets: `All instances in the network`
   - Source IP ranges: Go to [whatismyip.com](https://whatismyip.com), enter your IP as `YOUR_IP/32`
   - Protocols and ports: Select **"Specified protocols and ports"** → TCP → `3000`
4. Click **"Create"**

---

## 6. Phase C — Set Up the VM

**Time: ~45 minutes**

### Step C1 — SSH Into the VM

**Option 1 — Via GCP Console (easiest, no setup needed):**
1. In VM Instances, click the **"SSH"** button next to `cnst-backend`
2. A browser terminal opens — you're inside the VM

**Option 2 — Via your laptop's terminal (requires gcloud CLI):**
```bash
gcloud compute ssh cnst-backend --zone us-central1-a --project cnst-rag-assistant
```

All commands below are run **inside the VM terminal**.

---

### Step C2 — Update the System

```bash
sudo apt-get update && sudo apt-get upgrade -y
```

Wait ~2 minutes. You'll see a lot of output — that's normal.

---

### Step C3 — Install Docker

```bash
# Download and run Docker's official install script
curl -fsSL https://get.docker.com | sudo sh

# Add your user to the docker group (so you don't need sudo every time)
sudo usermod -aG docker $USER

# Apply the group change in current session
newgrp docker

# Verify Docker is working
docker run hello-world
```

You should see: **"Hello from Docker! This message shows that your installation appears to be working correctly."**

---

### Step C4 — Install Docker Compose

```bash
sudo apt-get install -y docker-compose-plugin

# Verify
docker compose version
```

You should see: `Docker Compose version v2.x.x`

---

### Step C5 — Clone Your GitHub Repository

```bash
cd ~
git clone https://github.com/YOUR_GITHUB_USERNAME/Construction_RAG_Assistant-main.git
cd Construction_RAG_Assistant-main
```

> Replace `YOUR_GITHUB_USERNAME` with your actual GitHub username.
> If the repo is private, you'll need a GitHub Personal Access Token. Run:
> `git clone https://YOUR_TOKEN@github.com/YOUR_USERNAME/Construction_RAG_Assistant-main.git`

Verify the deploy folder is there:
```bash
ls deploy/
```
You should see: `Dockerfile  docker-compose.cloud.yml  nginx.conf  prometheus.cloud.yml  .env.cloud.example  streamlit-secrets.example.toml`

---

### Step C6 — Upload `chunks.pkl` From Your Laptop

The `vector_store/chunks.pkl` file is not in git (it's gitignored). You must transfer it manually.

**From your laptop (PowerShell):**

First, get your VM's external IP from the GCP Console.

**Option 1 — Using gcloud CLI:**
```powershell
$VM_IP = "YOUR_VM_EXTERNAL_IP"   # replace with actual IP

gcloud compute scp `
  "c:\Users\prash\OneDrive\Documents\Masters\CNST Project\Final\Construction_RAG_Assistant-main\vector_store\chunks.pkl" `
  cnst-backend:~/Construction_RAG_Assistant-main/vector_store/chunks.pkl `
  --zone us-central1-a `
  --project cnst-rag-assistant
```

**Option 2 — Using WinSCP (if you don't have gcloud CLI):**
1. Download WinSCP from [winscp.net](https://winscp.net)
2. Connect:
   - Host: `YOUR_VM_EXTERNAL_IP`
   - Port: `22`
   - Username: your Google account username (e.g., `john` if your email is `john@gmail.com`)
   - Authentication: Get the private key from GCP Console → Compute Engine → Metadata → SSH Keys
3. Navigate to `~/Construction_RAG_Assistant-main/vector_store/`
4. Upload `chunks.pkl`

**On the VM, verify the upload worked:**
```bash
ls -lh ~/Construction_RAG_Assistant-main/vector_store/chunks.pkl
```
You should see the file size (~10–50MB).

---

## 7. Phase D — Configure Your Secrets

**Time: ~15 minutes**

### Step D1 — Create the .env.prod File

```bash
cd ~/Construction_RAG_Assistant-main
cp deploy/.env.cloud.example deploy/.env.prod
```

### Step D2 — Edit .env.prod

```bash
nano deploy/.env.prod
```

You'll see the file in the terminal editor. Fill in every field marked `← REQUIRED`:

**1. OpenAI API Key:**
Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys) → Create new key → Copy it
```
OPENAI_API_KEY=sk-proj-YOUR_ACTUAL_KEY_HERE
```

**2. Pinecone API Key:**
Go to [app.pinecone.io](https://app.pinecone.io) → API Keys → Copy your key
```
PINECONE_API_KEY=pcsk_YOUR_ACTUAL_KEY_HERE
```

**3. PostgreSQL Password:**
Make up a strong password (20+ characters, mix of letters/numbers/symbols):
```
POSTGRES_PASSWORD=MyStr0ngP@ssw0rd2026!
```

**4. JWT Secret Key:**
Generate one on the VM:
```bash
# Run this in a separate terminal to get a key, then paste it
python3 -c "import secrets; print(secrets.token_hex(32))"
```
Copy the output and paste:
```
JWT_SECRET_KEY=a1b2c3d4e5f6...the64characterhexstring
```

**5. Grafana Password:**
Make up any password for the Grafana dashboard:
```
GRAFANA_PASSWORD=GrafanaAdmin2026!
```

**Save and exit nano:** Press `Ctrl+X`, then `Y`, then `Enter`

### Step D3 — Verify the File

```bash
cat deploy/.env.prod | grep -v "^#" | grep "="
```

All fields should have values — no empty `=` signs.

---

## 8. Phase E — SSL Certificate

**Time: ~20 minutes**

> SSL (HTTPS) is mandatory. Streamlit Cloud is served over HTTPS, and browsers block HTTP API calls from HTTPS pages (mixed content policy).

You have two options:

### Option A — Free Domain + Let's Encrypt SSL (Recommended)

**Step 1: Get a free domain**

Go to [duckdns.org](https://duckdns.org):
1. Sign in with Google
2. Choose a subdomain name, e.g.: `cnst-rag`
3. Enter your VM's External IP in the **"current ip"** field
4. Click **"update ip"**
5. Your domain is now: `cnst-rag.duckdns.org` pointing to your VM

**Step 2: Install Certbot on the VM**

```bash
sudo apt-get install -y certbot

# Create the webroot directory for ACME challenge
sudo mkdir -p /var/www/certbot
```

**Step 3: Get the SSL certificate**
```bash
# Replace with your actual DuckDNS domain
sudo certbot certonly --standalone \
  -d cnst-rag.duckdns.org \
  --non-interactive \
  --agree-tos \
  -m your-email@gmail.com
```

If successful, you'll see:
```
Successfully received certificate.
Certificate is saved at: /etc/letsencrypt/live/cnst-rag.duckdns.org/fullchain.pem
Key is saved at:         /etc/letsencrypt/live/cnst-rag.duckdns.org/privkey.pem
```

**Step 4: Update nginx.conf with your domain**
```bash
nano deploy/nginx.conf
```

Find and replace `YOUR_DOMAIN_HERE` (appears 3 times) with your actual domain:
```nginx
server_name cnst-rag.duckdns.org;
ssl_certificate     /etc/letsencrypt/live/cnst-rag.duckdns.org/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/cnst-rag.duckdns.org/privkey.pem;
```

Save: `Ctrl+X` → `Y` → `Enter`

---

### Option B — Quick Test Without SSL (HTTP only)

> ⚠️ Use this ONLY to verify the backend works before getting a domain. Streamlit Cloud won't work with HTTP.

1. Edit `deploy/docker-compose.cloud.yml`:
   ```bash
   nano deploy/docker-compose.cloud.yml
   ```
   - Remove the entire `nginx:` service block
   - Add `ports: ["8000:8000"]` to the `api:` service

2. Open port 8000 in GCP Firewall:
   - GCP Console → VPC Network → Firewall → Create Rule
   - Port: `8000`, Source: `0.0.0.0/0`

3. Test at: `http://YOUR_VM_IP:8000/health`

---

## 9. Phase F — Deploy All Services

**Time: ~20 minutes**

### Step F1 — Set Correct Permissions on letsencrypt

```bash
sudo chmod -R 755 /etc/letsencrypt/live/
sudo chmod -R 755 /etc/letsencrypt/archive/
```

### Step F2 — Build and Start Everything

From your project directory on the VM:
```bash
cd ~/Construction_RAG_Assistant-main

# Build the FastAPI image and start all 6 containers
docker compose -f deploy/docker-compose.cloud.yml up -d --build
```

The first time, this will:
1. Download base images (Ubuntu, Redis, PostgreSQL, Prometheus, Grafana) — ~5 minutes
2. Build your FastAPI image (install all Python packages) — ~5 minutes
3. Start all containers — ~30 seconds

### Step F3 — Watch the API Start Up

```bash
docker compose -f deploy/docker-compose.cloud.yml logs -f api
```

Watch for this startup message (may take ~60 seconds):
```
[API v5] Startup complete — status: ok
  LLM: openai  |  Embeddings: openai  |  VectorDB: pinecone
  Auth: JWT (HS256, 24hr)  |  Logging: PostgreSQL
```

Press `Ctrl+C` to stop watching logs (containers keep running).

### Step F4 — Verify All Containers Are Running

```bash
docker compose -f deploy/docker-compose.cloud.yml ps
```

Expected output:
```
NAME              STATUS
cnst_api          Up (healthy)
cnst_nginx        Up
cnst_redis        Up (healthy)
cnst_postgres     Up (healthy)
cnst_prometheus   Up
cnst_grafana      Up
```

All should show `Up`. If any shows `Exit` or `Restarting`, check logs:
```bash
docker compose -f deploy/docker-compose.cloud.yml logs cnst_FAILING_SERVICE_NAME
```

### Step F5 — Test the Backend Health Endpoint

```bash
# From inside the VM
curl http://localhost:8000/health
```

Or from your laptop browser (if you have a domain with SSL):
```
https://cnst-rag.duckdns.org/health
```

Expected response:
```json
{
  "status": "ok",
  "vector_store_loaded": true,
  "llm_backend": "openai",
  "embedding_backend": "openai",
  "vector_backend": "pinecone",
  "hybrid_search_enabled": true,
  "reranker_enabled": true,
  "redis_connected": true,
  "postgres_connected": true
}
```

> Every field should match. If `vector_store_loaded` is `false`, your chunks.pkl upload didn't work — recheck Step C6.
> If `redis_connected` or `postgres_connected` is `false`, check the container logs.

---

## 10. Phase G — Deploy Streamlit Cloud

**Time: ~20 minutes**

### Step G1 — Create Streamlit Cloud Account

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click **"Sign in with GitHub"**
3. Authorize Streamlit to access your GitHub account

### Step G2 — Create a New App

1. Click **"New app"** (top right)
2. Fill in:

| Field | Value |
|---|---|
| Repository | `YOUR_USERNAME/Construction_RAG_Assistant-main` |
| Branch | `main` |
| Main file path | `app.py` |

3. Choose an app URL (e.g., `cnst-rag-assistant`) — this becomes `https://cnst-rag-assistant.streamlit.app`

### Step G3 — Add the Backend Secret

Before clicking Deploy:

1. Click **"Advanced settings"**
2. Click the **"Secrets"** tab
3. Paste this (with your actual domain):
```toml
API_BASE_URL = "https://cnst-rag.duckdns.org"
```
4. Click **"Save"**

### Step G4 — Deploy

Click **"Deploy!"**

Streamlit will:
1. Clone your GitHub repo
2. Install all packages from `requirements.txt` (~3 minutes)
3. Start `app.py`

You'll see a progress bar. When complete, your app opens automatically.

### Step G5 — Verify Streamlit Connected to Backend

In the sidebar of your Streamlit app, you should see:
```
🟢 API Online
Redis ✓     PostgreSQL ✓
LLM: openai · Vectors: pinecone
```

If you see **🔴 API Offline** — your `API_BASE_URL` secret is wrong, or Nginx is not running. Double-check Step F4 and G3.

---

## 11. Phase H — Post-Deployment Testing

**Time: ~20 minutes**

Run these tests in order. All should pass before you consider the deployment complete.

---

### Test 1 — Health Check (Backend Direct)

From your laptop browser:
```
https://cnst-rag.duckdns.org/health
```

✅ **Pass:** Returns JSON with `"status": "ok"` and all components `true`
❌ **Fail:** Page won't load — Nginx not running or firewall issue

---

### Test 2 — API Documentation

```
https://cnst-rag.duckdns.org/docs
```

✅ **Pass:** FastAPI Swagger UI opens showing all endpoints
❌ **Fail:** 502 Bad Gateway — FastAPI container not healthy

---

### Test 3 — Anonymous Query (No Login)

In your Streamlit app, without logging in, type:

> **"What minimum fall protection distance is required in the USA according to the GTM Construction Safety Manual?"**

✅ **Pass:** You get an answer mentioning **60 centimetres (2 feet)** with source chunks from `gtm_construction_safety_manual.pdf`
❌ **Fail:** Spinner never stops → API timeout; check `docker compose logs api`

---

### Test 4 — Login and Role Verification

In the Streamlit sidebar:
1. Email: `admin@cnst.com`
2. Password: your admin password

✅ **Pass:** Sidebar shows `✅ Logged in` with `Role: 🔴 admin`
❌ **Fail:** "Invalid email or password" → PostgreSQL not seeded, or wrong password

> **Note:** Users are seeded in the database. If you didn't set up users yet, run this on the VM:
> ```bash
> docker exec -it cnst_postgres psql -U cnst_user -d cnst_rag
> # Then in psql:
> INSERT INTO users (email, password_hash, role)
> VALUES ('admin@cnst.com', 'YOUR_BCRYPT_HASH', 'admin');
> \q
> ```
> Generate a bcrypt hash on the VM:
> ```bash
> python3 -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
> ```

---

### Test 5 — Authenticated Query with Logging

While logged in, ask:

> **"What is the maximum water-to-cementitious ratio specified by WSDOT for concrete mix design?"**

✅ **Pass:** 
- Answer mentions **0.44**
- Source chunk from `wsdot_construction_manual.pdf` appears
- PostgreSQL logs the query (verify: `docker exec -it cnst_postgres psql -U cnst_user -d cnst_rag -c "SELECT query, user_role, cache_hit FROM query_log ORDER BY created_at DESC LIMIT 1;"`)

---

### Test 6 — Semantic Cache Verification

Ask the **same question again** immediately:

> **"What is the maximum water-to-cementitious ratio specified by WSDOT for concrete mix design?"**

✅ **Pass:** Response appears **instantly** and shows **⚡ Served from semantic cache**
❌ **Fail:** Takes same time as first query → Redis not working

---

### Test 7 — Feedback System

On any answer, click **👍** (thumbs up).

✅ **Pass:** Button changes to **"✅ Thanks for the feedback!"**
❌ **Fail:** Button stays — feedback endpoint error, check API logs

---

### Test 8 — Grafana Dashboard

Open in your browser:
```
http://YOUR_VM_EXTERNAL_IP:3000
```
Login: Username `admin`, Password: your `GRAFANA_PASSWORD`

✅ **Pass:** Dashboard loads, you can see query count metrics after your test queries
❌ **Fail:** Can't connect → Grafana port not in your firewall rule (Step B4)

---

### Test 9 — Construction Domain Question (Final Smoke Test)

This is your real-world validation. Ask a domain-specific construction question:

> **"What are the scaffold foundation requirements according to GTM Construction Safety Manual?"**

✅ **Pass:** Answer mentions scaffolds must be **"sound, rigid, and capable of carrying the imposed load without settling"**, with source from GTM manual
❌ **Fail:** Vague answer with no source chunks → retrieval problem

If this passes, **your system is fully working on cloud**. 🎉

---

## 12. Troubleshooting

### Problem: "API Offline" in Streamlit sidebar

**Check 1:** Is the API container running?
```bash
docker compose -f deploy/docker-compose.cloud.yml ps api
```

**Check 2:** Is Nginx running and proxying correctly?
```bash
curl http://localhost:8000/health      # bypasses nginx
curl https://cnst-rag.duckdns.org/health  # goes through nginx
```

**Check 3:** Are there API startup errors?
```bash
docker compose -f deploy/docker-compose.cloud.yml logs api --tail=50
```

---

### Problem: `vector_store_loaded: false`

The `chunks.pkl` file is missing or not mounted correctly.

```bash
# Check if file exists on VM
ls -lh ~/Construction_RAG_Assistant-main/vector_store/chunks.pkl

# Check if container can see it
docker exec cnst_api ls -lh /app/vector_store/chunks.pkl
```

If the container can't see it, restart after verifying the file is in place:
```bash
docker compose -f deploy/docker-compose.cloud.yml restart api
```

---

### Problem: First query takes 120+ seconds

The cross-encoder model (`ms-marco-MiniLM-L-6-v2`) is downloading on first use — this is normal. It downloads once, caches in the `model_cache` volume, and is fast from the second query onwards.

Check download progress:
```bash
docker compose -f deploy/docker-compose.cloud.yml logs api -f
```

---

### Problem: CORS error in browser console

The Streamlit Cloud domain must be allowed by the API. Current setting in `api.py`:
```python
allow_origins=["*"]
```
This allows all origins — CORS should not be the issue. If you still see CORS errors, verify `API_BASE_URL` uses `https://` (not `http://`).

---

### Problem: PostgreSQL connection error at startup

Check that `POSTGRES_HOST=postgres` in `.env.prod` (not `localhost`). Docker resolves service names, not `localhost`.

```bash
grep POSTGRES_HOST deploy/.env.prod
# Should output: POSTGRES_HOST=postgres
```

---

### Problem: Redis `Cannot connect to Redis`

Same as PostgreSQL — check `REDIS_HOST=redis` in `.env.prod`:
```bash
grep REDIS_HOST deploy/.env.prod
# Should output: REDIS_HOST=redis
```

---

### Useful Commands

```bash
# View logs for any container
docker compose -f deploy/docker-compose.cloud.yml logs -f api
docker compose -f deploy/docker-compose.cloud.yml logs -f nginx
docker compose -f deploy/docker-compose.cloud.yml logs -f postgres

# Restart a specific container
docker compose -f deploy/docker-compose.cloud.yml restart api

# Restart everything
docker compose -f deploy/docker-compose.cloud.yml down
docker compose -f deploy/docker-compose.cloud.yml up -d

# Check resource usage on VM
docker stats

# Check disk space
df -h
```

---

## 13. Monthly Maintenance

### Renew SSL Certificate (Every 90 Days)

Let's Encrypt certificates expire after 90 days:
```bash
sudo certbot renew
docker compose -f deploy/docker-compose.cloud.yml restart nginx
```

### Update the Application

When you push new code to GitHub:
```bash
git pull origin main
docker compose -f deploy/docker-compose.cloud.yml up -d --build api
```

Only the `api` container rebuilds — Redis, PostgreSQL, and other containers are unaffected.

### Stop VM to Save Credits

When not demoing, stop the VM to pause credit consumption:
- GCP Console → VM Instances → select `cnst-backend` → **Stop**

Data persists on the disk. Start it again when needed:
- GCP Console → VM Instances → select `cnst-backend` → **Start**

After starting, run:
```bash
docker compose -f deploy/docker-compose.cloud.yml up -d
```

---

## ✅ Deployment Complete Checklist

- [ ] GCP account created, $300 credits claimed
- [ ] VM `cnst-backend` (e2-standard-2, Ubuntu 22.04) running
- [ ] Docker + Docker Compose installed on VM
- [ ] Repo cloned on VM
- [ ] `vector_store/chunks.pkl` uploaded to VM
- [ ] `deploy/.env.prod` filled with all 5 required values
- [ ] DuckDNS domain created and pointing to VM IP
- [ ] SSL certificate from Certbot successfully generated
- [ ] `deploy/nginx.conf` updated with actual domain name
- [ ] All 6 containers running: api ✅ nginx ✅ redis ✅ postgres ✅ prometheus ✅ grafana ✅
- [ ] `GET /health` returns all fields `true`
- [ ] Streamlit app deployed on share.streamlit.io
- [ ] `API_BASE_URL` secret added in Streamlit Cloud
- [ ] Streamlit sidebar shows `🟢 API Online` with Redis ✓ and PostgreSQL ✓
- [ ] Anonymous query returns correct answer with source chunks
- [ ] Login works with correct role display
- [ ] Semantic cache returns ⚡ on repeated questions
- [ ] Feedback (👍) is accepted
- [ ] Grafana dashboard accessible at VM_IP:3000
- [ ] Final domain question returns factual construction answer

---

*Document prepared for Construction RAG Assistant Phase 7 — GCP + Streamlit Cloud Deployment*
*System: FastAPI + Redis + PostgreSQL + Prometheus + Grafana + Nginx on GCP e2-standard-2*
