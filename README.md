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

## Running Tests

```bash
pip install pytest httpx
pytest
```

## Security

> **⚠️ Never commit your `.env` file or expose API keys in source code.**
>
> The `.env` file is listed in `.gitignore` and must remain excluded from version control. Use `.env.example` as a template — it contains variable names only, with no real values.
