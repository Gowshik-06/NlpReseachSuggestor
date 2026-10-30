# ResearchLens Hybrid Deployment Architecture Guide

This document details the configuration, security boundaries, and operational procedures for running ResearchLens in a **Hybrid Architecture**:
- **Frontend:** Hosted globally on **Vercel** (`https://nlp-reseach-suggestor.vercel.app`).
- **Backend & Data:** Kept securely on your **Local Laptop** running in Docker (`localhost:8000`).
- **Authentication:** **Firebase Authentication** (Google Sign-In + Backend JWKS Verification).

---

## 1. Architectural Overview

```
                      +---------------------------------------+
                      |            Browser Client             |
                      +---------------------------------------+
                         /                                 \
      1. Serves App Bundle                                2. Auth Flow (Popup)
      (HTTPS / CDN)                                       (OAuth 2.0 / ID Token)
                       /                                     \
                      v                                       v
    +----------------------------------+          +-----------------------+
    |         Vercel Cloud             |          |     Firebase Auth     |
    |  nlp-reseach-suggestor.vercel.app |          |   Project: nlpbased   |
    +----------------------------------+          +-----------------------+
                                                              |
                                                              | 3. ID Token verification
                                                              v    (via Google JWKS)
                                              +-------------------------------+
                                              |       Local Laptop Docker     |
                                              |       (http://localhost:8000) |
                                              |-------------------------------|
                                              | - FastAPI Backend             |
                                              | - PostgreSQL (162 Papers)     |
                                              | - FAISS Vector Index          |
                                              | - SPECTER-2 Embeddings        |
                                              | - Ollama (Local AI Engine)    |
                                              +-------------------------------+
```

---

## 2. Vercel Cloud Frontend Setup

### Project Settings
- **Repository:** `https://github.com/Gowshik-06/NlpReseachSuggestor.git`
- **Branch:** `main`
- **Root Directory:** `frontend`
- **Framework Preset:** `Vite`
- **Build Command:** `npm run build`
- **Output Directory:** `dist`
- **Install Command:** `npm install`

### SPA Deep-Link Rewrites (`frontend/vercel.json`)
The repository contains `vercel.json` configured to route all deep links to `index.html`:
```json
{
  "framework": "vite",
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "cleanUrls": true,
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

### Vercel Environment Variables (All 7 required)
Configure these in **Vercel Dashboard &rarr; Project Settings &rarr; Environment Variables**:

| Variable Name | Value | Purpose |
| :--- | :--- | :--- |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Points frontend calls to your laptop's backend |
| `VITE_FIREBASE_API_KEY` | `AIzaSyDf3UCj3bxxKEywUCXTHKu1oX3yHhbmgEY` | Firebase Web API Key |
| `VITE_FIREBASE_AUTH_DOMAIN` | `nlpbased.firebaseapp.com` | Firebase Auth Domain |
| `VITE_FIREBASE_PROJECT_ID` | `nlpbased` | Firebase Project ID |
| `VITE_FIREBASE_STORAGE_BUCKET` | `nlpbased.firebasestorage.app` | Firebase Storage Bucket |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | `1004577971834` | Firebase Cloud Messaging Sender ID |
| `VITE_FIREBASE_APP_ID` | `1:1004577971834:web:f8887d07d00aa12077e5c3` | Firebase App ID |

---

## 3. Local Laptop Backend Setup

### Preserving Existing Containers & Database
The local backend continues running inside Docker without modification:
```powershell
cd F:\ResearchLens-Share\research-paper-recommender
docker compose up -d
```

### CORS Configuration
The backend explicitly permits cross-origin API calls from the Vercel domain.
In `F:\ResearchLens-Share\research-paper-recommender\.env`:
```env
CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000","http://localhost:3001","http://127.0.0.1:3001","https://nlp-reseach-suggestor.vercel.app"]
```

---

## 4. Firebase Authentication Configuration

### Authorized Domains (Required)
Google OAuth popups enforce domain whitelisting to prevent phishing.

1. Open [Firebase Console](https://console.firebase.google.com/).
2. Select the **nlpbased** project.
3. Navigate to **Authentication** &rarr; **Settings** &rarr; **Authorized domains**.
4. Ensure both of the following domains are present:
   - `localhost`
   - `nlp-reseach-suggestor.vercel.app`

### How Authentication Operates in Hybrid Mode
1. User clicks **Sign In with Google** on `https://nlp-reseach-suggestor.vercel.app`.
2. Firebase client library opens Google OAuth popup on `nlpbased.firebaseapp.com`.
3. Upon approval, Firebase returns a signed JWT ID token (RS256).
4. The frontend includes this token in API requests as an `Authorization: Bearer <ID_TOKEN>` header.
5. When `FIREBASE_AUTH_ENABLED=true` on the local backend, FastAPI verifies the token against Google's public JWKS (`https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com`).

---

## 5. Localhost & Browser Security (Hybrid Demonstration Reality)

### Mixed Content & Private Network Access (PNA)
When a public HTTPS page (`https://nlp-reseach-suggestor.vercel.app`) communicates with an HTTP localhost service (`http://localhost:8000`), modern browsers apply security rules:

1. **Loopback Scope:** `http://localhost:8000` **always resolves to the local loopback of the machine running the browser**.
   - **On your laptop:** The browser routes requests to your laptop's Docker container on port 8000. Full functionality works seamlessly.
   - **On external visitors' devices:** The browser attempts to connect to port 8000 on *their* phone or laptop, resulting in `ERR_CONNECTION_REFUSED`.
2. **Mixed-Content In Chrome / Edge:**
   - Chrome allows HTTPS-to-localhost connections under the W3C Private Network Access specification.
   - If blocked or warned by browser security settings, click the Site Settings icon (lock / sliders) in the address bar for `nlp-reseach-suggestor.vercel.app` and set **Insecure content** to **Allow**.

---

## 6. Feature Availability Matrix

| Feature | Standalone Vercel | Requires Local Backend |
| :--- | :---: | :---: |
| **Landing UI & Component Library** | YES | - |
| **Client-Side SPA Routing** | YES | - |
| **PDF Client Parsing & Preview** | YES (`pdfjs-dist`) | - |
| **Google Sign-In Popup** | YES (Firebase SDK) | - |
| **162 Papers Database Catalog** | - | YES (`GET /api/v1/papers/...`) |
| **Vector Semantic Search** | - | YES (`POST /api/v1/papers/search`) |
| **12-Paper Comparative Matrix** | - | YES (`POST /api/v1/papers/compare`) |
| **DRIUT Dynamic Citation Tracker** | - | YES (`GET /api/v1/research/driut/alerts`) |
| **AI Synthesis / Local Ollama** | - | YES (`POST /api/v1/research/assistant`) |

---

## 7. Verification & Troubleshooting Commands

### 1. Test Local Backend Health
```powershell
curl.exe -s http://localhost:8000/health
# Expected: {"status":"ok","service":"research-paper-recommender","version":"0.1.0"}

curl.exe -s http://localhost:8000/api/v1/health
# Expected: {"status":"ok","database":"connected",...}
```

### 2. Verify CORS Preflight
```powershell
curl.exe -I -X OPTIONS http://localhost:8000/api/v1/health `
  -H "Origin: https://nlp-reseach-suggestor.vercel.app" `
  -H "Access-Control-Request-Method: GET"
# Expected response header:
# access-control-allow-origin: https://nlp-reseach-suggestor.vercel.app
```

### 3. Verify Frontend Tests
```powershell
cd F:\ResearchLens-Share\research-paper-recommender\frontend
npm test -- --run
# Expected: 76 tests passed
```
