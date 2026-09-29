<div align="center">

# ZEVQYN Backend

### AI Research + Career Workspace API

*FastAPI backend powering ZEVQYN — RAG chat over your documents, AI study tools, resume & portfolio builders, and career AI.*

![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Uvicorn](https://img.shields.io/badge/Uvicorn-5B5B5B)
![Supabase](https://img.shields.io/badge/Supabase-3FCF8E?logo=supabase&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)
![Google Gemini](https://img.shields.io/badge/Google_Gemini-4285F4?logo=google&logoColor=white)
![Render](https://img.shields.io/badge/Render-46E3B7?logo=render&logoColor=black)
![Pytest](https://img.shields.io/badge/Pytest-0A9EDC?logo=pytest&logoColor=white)
![License](https://img.shields.io/badge/license-proprietary-red)

</div>

---

## Preview

<p align="center">
  <img src="assets/hero.webp" alt="ZEVQYN Backend — Python RAG API" width="100%">
</p>

---

## What is this?

This is the API behind **ZEVQYN** (frontend: [hussnainahmedd/zevqyn](https://github.com/hussnainahmedd/zevqyn)). The WordPress frontend calls this service over REST for everything AI and data-related: document ingestion, vector search, RAG chat, study tools, resumes, portfolios, and career guidance.

The pipeline in a nutshell: **upload a document → extract text → chunk → embed with Gemini → store in pgvector → retrieve relevant chunks → get grounded AI answers.**

---

## Features

### Auth & identity
- Supabase Auth integration — endpoints validate `Authorization: Bearer <token>` server-side via `supabase.auth.get_user()` (local JWT decoding is never trusted alone)
- `GET /api/v1/me` returns the authenticated user's identity; unauthenticated requests get 401
- Client-supplied user IDs are never trusted — ownership is enforced (`user_id = authenticated user`) on every operation

### Workspaces & documents
- Full workspace CRUD (`POST / GET / PATCH / DELETE /api/v1/workspaces`)
- Document upload via multipart form data — **PDF, DOCX, TXT** (extracted with PyMuPDF and python-docx), with a configurable size cap (`MAX_UPLOAD_MB`, default 10)
- Files stored in the private Supabase Storage bucket `research-documents`

### RAG pipeline
- **Extraction** — text extraction from uploaded files into structured units
- **Chunking** — configurable chunk size and overlap
- **Embeddings** — Gemini embeddings for documents and queries
- **Indexing** — vectors stored in PostgreSQL + pgvector, searched through the `match_document_chunks` RPC (SQL in `supabase/sql/`)
- **RAG chat** — conversations per workspace, retrieval of relevant chunks, and source-grounded answers with citations

### AI study tools
- `POST …/research/summary` — document summaries
- `POST …/research/key-points` — key points extraction
- `POST …/research/questions` — generated study questions (quiz prep)
- `POST …/research/flashcards` — flashcards

### Projects
- Project CRUD with research traceability
- AI project proposal generation from research content

### Resumes
- Resume CRUD with section reordering
- PDF export (fpdf2)

### Portfolios
- Portfolio CRUD with live preview data
- Public, no-auth portfolio viewing

### Career
- Career data CRUD: skills, education, certificates
- **Career AI** (Gemini): profile analysis, skill-gap analysis, project suggestions, resume review, portfolio review, action plans, and career conversations

### Misc
- Contact inbox endpoints (public message submission + admin management)
- Health checks: `GET /` and `GET /health`

---

## API overview

All routes live under `/api/v1` (interactive docs at `/docs` and `/redoc` when the server runs):

| Prefix | Area |
|--------|------|
| `/api/v1/me` | Authenticated identity |
| `/api/v1/workspaces` | Workspaces |
| `/api/v1/documents` | Global documents |
| `/api/v1/workspaces/{id}/documents` | Workspace documents (upload, list, metadata) |
| `/api/v1/workspaces/{id}/research` | RAG chat, summary, key points, questions, flashcards |
| `/api/v1` | Projects, portfolios, profile |
| `/api/v1/career` | Career data + career AI |
| `/api/v1/resumes` | Resumes + PDF export |
| `/api/v1/contact` | Contact messages |
| `GET /health` | Health check |

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Language | Python |
| API framework | FastAPI |
| Server | Uvicorn |
| Database | Supabase (PostgreSQL + pgvector) |
| Auth & storage | Supabase Auth + Supabase Storage |
| LLM & embeddings | Google Gemini API (`google-genai`) |
| Deployment | Render (`render.yaml` included) |
| Tests | Pytest (unit + integration) |

---

## Quick start

### 1. Create & activate a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the example file and fill in your credentials:

```bash
cp .env.example .env
```

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_PUBLISHABLE_KEY` | Supabase publishable key (client-side, RLS-respecting) |
| `SUPABASE_SECRET_KEY` | Supabase service-role key (backend only — **never** expose; bypasses RLS) |
| `GEMINI_API_KEY` | Google Gemini API key |
| `CORS_ORIGINS` | Comma-separated allowed origins (default `http://localhost:3000,http://localhost:8000`) |
| `MAX_UPLOAD_MB` | Max upload size in MB (default 10) |

### 4. Set up Supabase

Run the SQL in `supabase/sql/` on your Supabase project (creates `match_document_chunks` vector search, contact messages table, and portfolio/career junction tables).

### 5. Run the dev server

```bash
uvicorn app.main:app --reload
```

The API is live at **http://127.0.0.1:8000** — interactive docs at `/docs`, ReDoc at `/redoc`.

### Running tests

```bash
# Unit tests (offline, no credentials needed — integration tests deselected by default)
pytest -v

# Integration tests (read-only; needs .env with real Supabase credentials)
pytest -m integration -v
```

---

## Security notes

- The service-role (`SUPABASE_SECRET_KEY`) key bypasses Row Level Security — it stays in backend code only, never in responses, logs, or frontend code.
- `.env` is gitignored — use `.env.example` as the template and never commit real keys.
- Supabase access tokens are validated server-side on every protected request; they are never stored or returned.

## Deployment

Deploy config is in `render.yaml`: `pip install -r requirements.txt`, then `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, with `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `GEMINI_API_KEY`, and `CORS_ORIGINS` set as environment variables.

---

## Related

- **Frontend repo:** [hussnainahmedd/zevqyn](https://github.com/hussnainahmedd/zevqyn) — WordPress frontend (Blocksy + Greenshift + custom HTML/CSS/JS) that calls this API
- **Backend (production):** [zevqyn-backend.onrender.com](https://zevqyn-backend.onrender.com) (per project docs)

## License

© 2025–2026 ZEVQYN. All rights reserved.

Proprietary — no license is granted for use, modification, or distribution unless explicitly authorized by the project owner.

---

<div align="center">

Built by **Hussnain Ahmad** — [github.com/hussnainahmedd](https://github.com/hussnainahmedd)

</div>
