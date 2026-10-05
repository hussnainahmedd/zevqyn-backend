# Zevqyn — Product Requirements Document

**Date:** 2026-10-05
**Status:** Draft — describes the product *as it exists today* (verified against the working copy at `~/workspace/projects/zevqyn-frontend`; backend surface taken from the frontend's typed API services + README).
**License:** Proprietary — © 2025–2026 ZEVQYN. No license is granted for use, modification, or distribution.

---

## 1. Purpose

Zevqyn is an AI workspace for students that follows one journey: **Research → Project → Resume → Portfolio → Career Growth**. A student uploads study material, researches it with cited AI answers, turns learning into projects, then builds resumes and shareable portfolios and gets AI career guidance — all in one place.

## 2. Users

- **Primary:** BSCS / university students preparing coursework, quizzes, resumes, and portfolios.
- **Secondary (admin):** the project owner, who triages contact-form submissions from the Admin Inbox.

## 3. Current feature list (as it exists TODAY)

### Marketing site (public, no login)
| Route | What it does |
|---|---|
| `/` | Landing page |
| `/features` | Feature overview |
| `/how-it-works` | Product journey explainer |
| `/about` | About page |
| `/contact` | Contact form → `POST /api/v1/contact` (unauthenticated by design) |

### Auth
| Route | What it does |
|---|---|
| `/login`, `/register` | Email auth via Supabase Auth; session persisted and auto-refreshed client-side (`src/lib/supabase.ts`) |

### App shell (`/app/*`, requires session — 401s redirect to `/login`)
| Route | What it does |
|---|---|
| `/app/dashboard` | Overview of workspaces, documents, projects, resumes |
| `/app/workspaces` | Workspace CRUD |
| `/app/workspaces/[id]` | Research studio: upload PDF/DOCX/TXT → index for RAG → ask with page-number citations; one-click tools: `summary`, `key-points`, `questions`, `flashcards` (this is the **quiz-prep** surface); conversation history with delete |
| `/app/documents` | Library of all uploaded documents |
| `/app/projects` + `/app/projects/[id]` | Project CRUD; can create a project from research output |
| `/app/career` | Career profile data: skills, education, certificates (CRUD) |
| `/app/resume` | Resume builder: multiple resumes, resume items, drag-equivalent reorder |
| `/app/portfolio` | Portfolios linking projects, skills, education, certificates |
| `/app/career-ai` | Six AI tools (`analyze`, `skill-gap`, `suggest-projects`, `review-resume`, `review-portfolio`, `action-plan`) + career chat, all run against the user's real career data; conversation history |
| `/app/settings` | Profile/account settings |
| `/app/admin/inbox` | Contact-message inbox (read / replied / archived); visible only if the **backend** grants admin role |

### Public share
| Route | What it does |
|---|---|
| `/p/[slug]` | Public portfolio page, server-rendered, no login required (`GET /api/v1/public/portfolios/{slug}`, `auth:false`) |

### Architecture facts (verified in code)
- Next.js 16.3.8 (App Router) + TypeScript + Tailwind CSS v4; `@tanstack/react-query`, `react-hook-form` + `zod`, `@supabase/supabase-js`, `lucide-react`. 20 routes total.
- All backend calls go through a single typed client: `src/lib/api/client.ts` (`apiFetch` — Bearer JWT injection, 401 → `/login`, error normalization) and `src/lib/api/services.ts` (~45 typed endpoints under `/api/v1/*`). No scattered raw fetch.
- Backend: FastAPI on Render (`https://zevqyn-backend.onrender.com`); frontend authenticates with the Supabase session's access token as `Authorization: Bearer <JWT>`. Gemini/LLM calls happen **only** on the backend — the frontend has no AI key.
- Secrets: three `NEXT_PUBLIC_*` env vars (`NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`). `.env.example` in repo carries names only.
- No grep hits in `src/` for `service_role`, `sk-…` keys, PEM private keys, or JWT-shaped secrets.

### Deployment state (verified 2026-10-05 ~09:29 PKT)
- Backend: **online** — `https://zevqyn-backend.onrender.com` returns `{"name":"ZEVQYN","status":"online"}` (200, ~2s).
- Frontend: **not yet deployed** — `https://zevqyn.vercel.app` returns 404 `DEPLOYMENT_NOT_FOUND` (quota blocked the auto-deploy; awaiting Hussnain's manual Create Deployment from `main` @ `4ec207b`).
- Backend CORS: currently rejects `https://zevqyn.vercel.app` (400 "Disallowed CORS origin") — Render `CORS_ORIGINS` update pending.
- Supabase redirect URLs for both `zevqyn.vercel.app` and `zevqyn.dev` — pending.
- `zevqyn.dev` DNS not yet pointed at Vercel (later, on Hussnain's word).

## 4. Non-goals (out of scope for this PRD)

- UI/UX redesign or new features — this document describes only what exists.
- Backend rewrite, database migrations, or model/training work.
- Custom domain DNS cutover steps beyond listing them as pending (that's the goal's separate step).
- Social sign-in, payments, mobile apps, offline mode, multi-language UI.
- The full page-by-page QA of the live site (paused earlier work, resumes only on Hussnain's word).

## 5. Success criteria

1. `https://zevqyn.vercel.app` loads the home page with zero console CORS errors.
2. Register → login works via Supabase Auth; an authenticated user can load dashboard/workspaces and see real backend data.
3. Upload → index → cited Q&A works on at least one document (research studio round-trip).
4. Resume builder and public portfolio share link (`/p/[slug]`) both render.
5. No secrets in git; proprietary `LICENSE` retained; `package.json` stays `private: true`, `license: UNLICENSED`.

## 6. Known limitations

- Frontend deployment not live yet (see §3); everything after "login" depends on the pending CORS + redirect-URL steps.
- Server-side security (JWT verification per endpoint, RLS policies, upload validation, rate limits) lives in the backend, which is **not in this working copy** — covered as gaps in `SECURITY.md`.
- Research/quiz-prep quality depends on documents being indexed first; un-indexed docs return a "chat failed, index first" error.
- Upload file-type filtering (`accept=".pdf,.docx,.txt"`) is client-side only; server-side enforcement unverified.
- Contact form and public portfolio endpoints are unauthenticated by design (abuse surface — see SECURITY.md).
- No test suite ships with the frontend (`package.json` has no test script).
- Supabase Data API change on 2026-10-30 (new public tables need explicit grants) — does not affect existing tables, but applies to any future table.
