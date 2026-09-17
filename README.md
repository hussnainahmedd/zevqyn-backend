# ZEVQYN Backend

**AI Research + Career Workspace API**

ZEVQYN is an AI-powered platform for academic research, career development, and portfolio building. This repository contains the FastAPI backend that powers the workspace.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend framework | FastAPI + Uvicorn |
| Database | Supabase (PostgreSQL + pgvector) |
| Auth & Storage | Supabase Auth + Storage |
| LLM & Embeddings | Google Gemini API |
| Frontend | WordPress (separate repo) |
| Deployment | Render |

## Quick Start

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

See [Environment Variables](#environment-variables) below.

### 4. Run the development server

```bash
uvicorn app.main:app --reload
```

The server starts at **http://127.0.0.1:8000**.

## API Documentation

FastAPI auto-generates interactive docs:

| Format | URL |
|--------|-----|
| Swagger UI | http://127.0.0.1:8000/docs |
| ReDoc | http://127.0.0.1:8000/redoc |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_PUBLISHABLE_KEY` | Supabase anon / publishable key |
| `SUPABASE_SECRET_KEY` | Supabase service-role secret key |
| `GEMINI_API_KEY` | Google Gemini API key |

### Publishable key vs Secret key

| Key | Purpose | Audience |
|-----|---------|----------|
| `SUPABASE_PUBLISHABLE_KEY` | Client-side / user-scoped operations (respects RLS) | Frontend & future auth flows |
| `SUPABASE_SECRET_KEY` | Server-side admin operations (bypasses RLS) | Backend only — **never** expose |

## Supabase Integration

ZEVQYN uses Supabase for:

* **PostgreSQL database** — stores profiles, workspaces, documents, projects, resumes, portfolios, conversations, and more.
* **pgvector** — powers RAG similarity search via the `match_document_chunks` RPC function.
* **Storage** — holds uploaded research documents in the private `research-documents` bucket.
* **Auth** — user authentication via Supabase Auth + Bearer token validation.

The backend connects to Supabase using the **service-role (secret) key** for privileged server-side operations. This client is created lazily — it is only initialized when a Supabase-dependent operation is called, so the basic health-check server starts without credentials.

## Authentication

Clients authenticate with Supabase Auth and receive an access token. Protected FastAPI endpoints require:

```
Authorization: Bearer <SUPABASE_ACCESS_TOKEN>
```

The backend validates the token server-side via `supabase.auth.get_user()` — it does **not** trust local JWT decoding alone.

### `GET /api/v1/me`

Returns the authenticated user's identity:

```json
{
  "id": "<user-uuid>",
  "email": "<email-or-null>"
}
```

Unauthenticated requests receive **401 Unauthorized**.

### Security rules

* **Client-supplied user IDs are never trusted.** User identity always comes from the verified Supabase token.
* Access tokens are never stored in user models or returned in API responses.
* The service-role key is never exposed to clients.
* **Strict ownership checks** — Database operations explicitly enforce `user_id = <authenticated_user_id>`.

## Workspaces & Documents

ZEVQYN manages research documents within user-owned Workspaces.

### Workspace Endpoints

* `POST /api/v1/workspaces` — Create a workspace
* `GET /api/v1/workspaces` — List user's workspaces
* `GET /api/v1/workspaces/{id}` — Get a specific workspace
* `PATCH /api/v1/workspaces/{id}` — Update workspace metadata (name/description)
* `DELETE /api/v1/workspaces/{id}` — Delete a workspace (must be empty)

### Document Endpoints

Documents are uploaded via multipart/form-data.

* `POST /api/v1/workspaces/{id}/documents` — Upload a new document
* `GET /api/v1/workspaces/{id}/documents` — List documents in a workspace
* `GET /api/v1/workspaces/{ws_id}/documents/{doc_id}` — Get document metadata
* `DELETE /api/v1/workspaces/{ws_id}/documents/{doc_id}` — Delete a document and its storage file
* `GET /api/v1/workspaces/{ws_id}/documents/{doc_id}/download` — Get a short-lived (60s) signed URL to download the private file

### File Upload Constraints

* **Allowed types:** PDF, DOCX, TXT, Markdown (.md)
* **Size limit:** Configurable via `MAX_UPLOAD_MB` (default: 10MB)
* **Storage:** Files are securely stored in the private `research-documents` bucket.
* **Path structure:** `<user_uuid>/<workspace_uuid>/<document_uuid>/<safe_filename>`
* **Rollback:** If metadata insertion fails, the uploaded storage object is automatically cleaned up to prevent orphaned files.

## CORS

Allowed origins are configured via the `CORS_ORIGINS` environment variable (comma-separated):

```
CORS_ORIGINS=https://zevqyn.com,http://localhost:3000
```

Default (development): `http://localhost:3000,http://localhost:8000`

## Running Tests

### Unit tests (offline, no credentials needed)

```bash
pytest
```

### Integration tests (requires .env with real Supabase credentials)

```bash
pytest -m integration -v
```

This runs read-only connectivity checks against your Supabase project:
- Verifies database access via a harmless query on `profiles`
- Verifies access to the `research-documents` Storage bucket

No data is modified.

### Manual auth verification

To test authentication against real Supabase Auth:

1. Obtain a valid Supabase access token (e.g. via Supabase dashboard or client login).
2. Run the dev server: `uvicorn app.main:app --reload`
3. Call the protected endpoint:
   ```bash
   curl -H "Authorization: Bearer <YOUR_TOKEN>" http://localhost:8000/api/v1/me
   ```
4. **Never** commit, log, or share the token.

## Security

> **⚠️ Never commit your `.env` file or expose API keys in source code.**
>
> The `.env` file is listed in `.gitignore` and must remain excluded from version control. Use `.env.example` as a template — it contains variable names only, with no real values.
>
> The `SUPABASE_SECRET_KEY` bypasses Row Level Security — it must only be used in trusted backend code and must never appear in API responses, logs, or frontend code.
