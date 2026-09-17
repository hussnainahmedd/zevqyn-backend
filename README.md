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

### Document Extraction

After a document is uploaded, you can trigger text extraction via:
* `POST /api/v1/workspaces/{ws_id}/documents/{doc_id}/extract`

This endpoint securely retrieves the document from the private Storage bucket, parses the content based on file type, normalizes the text, and returns a structured representation of the text chunks (e.g. by page or paragraph). The document status is updated to `processing`, and then to `processed` (or `failed` if extraction errors occur).

**Supported formats for extraction:**
* **PDF**: Extracted page by page using `PyMuPDF`. Empty pages are skipped. Does **not** perform OCR (scanned/image-only PDFs will fail to extract text). Password-protected PDFs are rejected.
* **DOCX**: Logical paragraphs and basic tables are extracted using `python-docx`. Does not provide page numbers.
* **TXT / MD**: Extracted safely with UTF-8 support (handles BOM). Markdown is treated as plain text with structural headings retained.

### Document Indexing (Phase 5)

The indexing pipeline combines extraction, chunking, and semantic embeddings into a single process:
* `POST /api/v1/workspaces/{ws_id}/documents/{doc_id}/index`

1. **Extraction**: Retreives and parses the document (same as the extract endpoint).
2. **Chunking**: Text is split into overlapping chunks (configured via `CHUNK_SIZE` and `CHUNK_OVERLAP`). Critically, chunks never cross page boundaries to ensure accurate citations.
3. **Embeddings**: Uses `gemini-embedding-001` (retrieval-document task type) via the Google GenAI SDK to generate 768-dimensional embeddings.
4. **Persistence**: Embedded chunks are stored in the Supabase `document_chunks` table via `pgvector`. This step is idempotent (re-indexing safely replaces old chunks).

### Search & Retrieval (Phase 5)

Test semantic search across a workspace:
* `POST /api/v1/workspaces/{ws_id}/search`

Provides a query string and returns semantically relevant chunks based on cosine similarity, using the `match_document_chunks` Supabase RPC. All retrieval is strictly scoped to the authenticated user.

### RAG Chat & Grounded Answers (Phase 6)

The core research chat pipeline is available via:
* `POST /api/v1/workspaces/{ws_id}/chat`
* `GET /api/v1/workspaces/{ws_id}/conversations`
* `GET /api/v1/workspaces/{ws_id}/conversations/{conv_id}/messages`

**RAG Pipeline Behavior:**
1. **Context Construction**: Retrieves chunks via Phase 5 semantic search. Only retrieves from documents the authenticated user owns within the specified workspace.
2. **Grounding**: Gemini (`gemini-2.5-flash` by default) is explicitly instructed to answer *only* based on the retrieved context, and to state clearly when information is insufficient.
3. **Citations**: Returns deterministic citations mapping generated references like `[SOURCE_1]` back to original files, page numbers, and UUIDs. Citations are extracted safely on the backend (not hallucinated by the model) and persisted in the `messages` table via the `sources` JSONB column.
4. **Insufficient Context**: If retrieval returns nothing useful, the pipeline safely short-circuits to avoid model hallucination.

**Example Request:**
```json
{
  "message": "What does the research say about X?",
  "conversation_id": "optional-uuid-to-continue-thread"
}
```

**Example Response:**
```json
{
  "answer": "According to the study, X is important [SOURCE_1].",
  "citations": [
    {
      "source_id": "SOURCE_1",
      "document_id": "uuid",
      "document_name": "paper.pdf",
      "page_number": 7,
      "source_label": "Page 7",
      "chunk_id": "uuid",
      "similarity": 0.84
    }
  ],
  "retrieved_chunks": 5,
  "conversation_id": "uuid",
  "message_id": "uuid"
}
```

### Research AI Features (Phase 7)

ZEVQYN offers AI-powered generation for study and analysis based directly on the uploaded documents. These features can be scoped to a single document or across an entire workspace, ensuring broader coverage by intelligently retrieving chunks across available files.

Endpoints under `/api/v1/workspaces/{workspace_id}/research/`:
* `POST /summary` — Generate a comprehensive research summary.
* `POST /key-points` — Extract the most important insights (returns structured JSON array).
* `POST /questions` — Generate grounded study/research questions.
* `POST /flashcards` — Generate flashcards (front/back) for quick revision.

**Example Request:**
```json
{
  "document_id": "optional-uuid",
  "count": 5
}
```

**Example Flashcard Response:**
```json
{
  "flashcards": [
    {
      "front": "What is ...?",
      "back": "...",
      "citations": [
        {
          "source_id": "SOURCE_1",
          "document_id": "uuid",
          "document_name": "paper.pdf",
          "page_number": 3,
          "source_label": "Page 3",
          "similarity": 1.0
        }
      ]
    }
  ],
  "scope": "workspace"
}
```
*Note on Persistence*: Questions and Flashcards are returned to the client and currently unpersisted on the backend, ensuring schema consistency as current tables do not natively support complex JSONB citation arrays without manual SQL migrations.

### Project AI Features (Phase 8A)

ZEVQYN allows you to seamlessly transition from unstructured research into a structured project proposal.

* `POST /api/v1/workspaces/{workspace_id}/research/create-project`
  * Generates a **preview** of a project proposal from your document or workspace research.
  * Preview includes grounded problem statements, AI-suggested features, technologies, and skills.
  * Preview must be explicitly saved via standard Project CRUD to persist.

Standard Project CRUD (`/api/v1/projects`) enforces strictly authenticated ownership and supports defining `technologies`, `skills`, `visibility`, and `source_document_id`.

### Career AI Assistant (Phase 8B)

ZEVQYN includes a secure, grounded Career AI Assistant (`POST /api/v1/career/assistant`).

* **Profile Grounding**: The AI has strict access only to your authenticated Career Profile (Projects, Skills, Education, Certificates). It will **never** hallucinate or invent qualifications, jobs, or degrees you have not explicitly saved.
* **General Guidance**: The AI can provide generic advice (e.g. "To become a backend engineer, you need...") but clearly separates this from your actual profile facts.
* **Security First**: Your profile is stored securely via Standard Career CRUD endpoints (`/api/v1/career/skills`, etc.). No client-provided user IDs are accepted; everything is inferred natively from your signed Supabase JWT.

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
