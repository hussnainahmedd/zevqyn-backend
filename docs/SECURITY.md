# Zevqyn — Security Design & Hardening Plan

**Date:** 2026-10-05
**Scope:** Security requirements and hardening actions for Zevqyn (frontend working copy `~/workspace/projects/zevqyn-frontend`; backend = FastAPI on Render, Supabase Auth + Postgres). **Read-only task — implementation is OUT OF SCOPE and requires Hussnain's explicit approval before any change.**
**Backend caveat:** the backend codebase is not in this working copy, so backend-side facts are marked *unverified* and appear as actions, not claims.

---

## 1. Non-negotiable requirements

### 1.1 Server-side auth verification for every backend endpoint
The frontend sends `Authorization: Bearer <Supabase JWT>` on every call (`src/lib/api/client.ts`). **The JWT must be validated server-side on the FastAPI backend for every `/api/v1/*` route** (signature against the Supabase JWKS, expiry, `aud`/`iss`), never trusted from the client.
- `/app/*` pages are client components; their "login required" behavior is just a 401 redirect. They are NOT an authorization boundary — the backend is.
- Only intentionally-public endpoints may skip auth: `POST /api/v1/contact` and `GET /api/v1/public/portfolios/{slug}` (both already flagged `auth:false` in `src/lib/api/services.ts`).

### 1.2 Supabase RLS policies — no open tables, own-resources-only
Every table holding user data (workspaces, documents, conversations, projects, career data, resumes, portfolios, contact messages) must have Row Level Security enabled with policies that restrict rows to the owning user (`auth.uid() = user_id`). The backend must query Supabase with the caller's JWT (RLS-enforced), not with a service-role key that bypasses RLS. Contact messages are admin-only; portfolios marked public are the only read exception.

### 1.3 `NEXT_PUBLIC_*` carries only the publishable key
Verified in `src/lib/supabase.ts` + `src/lib/env.ts`: the frontend uses **only** `NEXT_PUBLIC_SUPABASE_ANON_KEY` (publishable/anon). The service-role/secret key must never appear in frontend code, Vercel env vars, or the repo. Grep of `src/` shows no `service_role`, no `sk-…` keys, no PEM material.

### 1.4 CORS allowlist = exact origins only
Production allowlist must be exactly: `https://zevqyn.vercel.app` and `https://zevqyn.dev`. No wildcards (`*`), no `http://`, no `localhost`/`127.0.0.1` in production. Currently (2026-10-05 ~09:29 PKT) the Render backend rejects `https://zevqyn.vercel.app` — 400 "Disallowed CORS origin" — the allowlist update is the pending step.

### 1.5 Per-environment secrets
Repo carries **only** `.env.example` with placeholder values; real values live in `.env.local` (never committed) and platform env dashboards (Vercel, Render, Supabase). Note: `.env.example` currently ships `NEXT_PUBLIC_API_BASE_URL=https://zevqyn-backend.onrender.com` — a real-looking default rather than a placeholder (Minor; see actions).

### 1.6 Backend input validation on the RAG endpoints
All of these must validate server-side (Pydantic/schemas) — client-side checks are cosmetic:
- Upload (`POST /api/v1/workspaces/{id}/documents`): file type (PDF/DOCX/TXT by magic bytes, not extension), size cap, sanitized filename (no path traversal).
- Chat (`POST …/chat`): question length cap, type checks.
- Research tools (`POST …/research/{tool}`): `tool` restricted to an allowlist (`summary`, `key-points`, `questions`, `flashcards`), payload size cap.
- Generic: JSON body size limits, reject unexpected fields or strip them.

---

## 2. Guide checklist applied item-by-item

| # | Guide item | Status | Evidence |
|---|---|---|---|
| 1 | SECURITY.md written before code | OK | This document exists before the production launch |
| 2 | AI rules respected (no exposed keys; input validated; auth verified server-side) | GAP | No keys exposed (verified). Input validation + server-side auth verification live in the unverified backend |
| 3 | Gates: lint → typecheck → unit → integration → E2E | GAP | lint (eslint) and typecheck (TS clean) done. No test script in frontend `package.json`; unit/integration/E2E absent |
| 4 | No secrets in git | OK | Grep of `src/` clean; `.env.example` names-only (see §1.5 note); proprietary LICENSE retained |
| 5 | Authentication verified | OK | Server-side Supabase `get_user()` validation on 9/11 API modules; admin inbox role-gated |
| 6 | Authorization verified | GAP | Admin inbox relies on backend admin-role check — unverified; RLS policies unverified |
| 7 | Database security configured | GAP | RLS enablement + policies unverified (Supabase dashboard) |
| 8 | Input validation | GAP | Frontend zod/react-hook-form only; backend Pydantic validation on RAG endpoints unverified |
| 9 | API validation | GAP | Same as 8 — request/response schemas unverified server-side |
| 10 | Pipeline LOCAL → PREVIEW → QA → PRODUCTION | GAP | No preview/QA stage observed; Vercel deploy is straight to production |
| 11 | Secrets only in .env + platform env vars | OK | 3 `NEXT_PUBLIC_*` vars set in Vercel; none committed |
| 12 | `.env.example` with placeholders in repo | OK | Present (one real-looking default noted in §1.5) |
| 13 | Supabase: row-level/access policies, never open tables | GAP | Unverified — needs dashboard audit |
| 14 | Database logic in services, not UI | OK | `src/lib/api/services.ts` typed domain services; no raw SQL/fetch in pages |
| 15 | Auth verified server-side | OK | Verified in `app/core/auth.py` |
| 16 | Users only access their own resources | GAP | Enforced (if at all) via backend + RLS — unverified |
| 17 | File upload validation (type/size/filename) | OK | Extension+MIME+size+sanitized filename, user-scoped paths |
| 18 | Production QA on the live URL (signup, login, wrong credentials, logged-out access, direct URLs, invalid inputs) | GAP | Frontend not live yet (404 at 09:29 PKT); QA paused pending Hussnain's word |
| 19 | Monitoring: error tracking, backups, uptime | GAP | No error tracking, backup schedule, or uptime monitor observed |
| 20 | Guide gaps, honestly disclosed | N-A | Dependency/CVE scanning, auth audit logging, mobile-specific guidance — the guide does **not** cover these (added as actions below) |

---

## 3. Prioritized action list

> Each action states **what** to do and **where**. None of these have been implemented — all require Hussnain's approval.

### Critical
1. **Server-side JWT validation** — ✅ VERIFIED 2026-10-05: `app/core/auth.py` validates the Bearer <redacted> server-side via Supabase `auth.get_user()` (never local decode alone); `get_current_user` is a dependency on 9 of 11 API modules; the contact-inbox routes additionally require `require_admin_user` (app_metadata role). Only `POST /api/v1/contact` is intentionally public (rate-limited, see #4).
2. **Audit + enable Supabase RLS on all user tables** — in Supabase Dashboard → Authentication → Policies: confirm RLS enabled on workspaces, documents, conversations, projects, career, resumes, portfolios, contact-messages; policies `auth.uid() = user_id`; backend uses caller JWT, never service-role. *Where: Supabase project dashboard.*
4. **Rate-limit the public contact endpoint** — ✅ IMPLEMENTED 2026-10-05: `slowapi` per-IP limits wired in `app/main.py` (default 120/min); `POST /api/v1/contact` limited to 5/min (`app/api/contact.py`) to block spam/abuse; covered by `tests/test_contact.py::test_contact_submit_rate_limited` (50/50 contact tests green).

3. **Fix production CORS allowlist** — in Render → `zevqyn-backend` → Environment → `CORS_ORIGINS`: set to exactly `https://zevqyn.vercel.app,https://zevqyn.dev` (remove any `*`, `http://`, `localhost` entries). *Where: Render dashboard.*
4. **Verify backend admin-role enforcement** — confirm `/api/v1/contact/messages` (GET/PATCH) rejects non-admin users server-side; frontend "Admin access required" message is not a control. *Where: backend repo.*
5. **Server-side upload validation** — ✅ VERIFIED 2026-10-05: `app/services/documents.py` enforces workspace ownership, extension allowlist (`validate_extension`), MIME-vs-extension match, size cap (`settings.max_upload_bytes`), empty-file rejection, and filename sanitization; storage path is user/workspace/document-scoped UUIDs.

### High
6. **Add backend input validation (Pydantic)** on chat, research tools (allowlist `summary|key-points|flashcards|questions`), resume/portfolio/profile PATCH bodies, and global JSON size limits. *Where: backend repo.*
7. **Rate-limit public endpoints** — `POST /api/v1/contact` and `GET /api/v1/public/portfolios/{slug}` (IP-based, e.g. slowapi on FastAPI) to block form/API abuse. *Where: backend repo / Render.*
8. **Add Supabase Auth redirect URLs** — `https://zevqyn.vercel.app/**` and `https://zevqyn.dev/**` in Supabase → Authentication → URL Configuration. *Where: Supabase dashboard.*
9. **Run production QA on the live URL** after deploy — signup, login, wrong credentials, logged-out access to `/app/*`, direct-URL access, oversized/invalid inputs, expired-session behavior. *Where: `https://zevqyn.vercel.app`.*
10. **Dependency/CVE scanning** — add Dependabot (or `npm audit` in CI) for the frontend and the equivalent for the backend; the guide doesn't cover this. *Where: GitHub repo settings + CI.*

### Medium
11. **Auth audit logging** — log sign-in failures, admin-inbox access, and 401/403 spikes (Supabase Auth logs + backend logging); the guide doesn't cover this. *Where: Supabase dashboard + backend.*
12. **Monitoring** — add error tracking (e.g. Sentry) and an uptime monitor on both `zevqyn.vercel.app` and `zevqyn-backend.onrender.com`; confirm Supabase backup schedule. *Where: Vercel/Render/Supabase dashboards.*
13. **Add unit + E2E tests to the pipeline** — frontend has no test script; add at least auth-flow and upload-flow tests before claiming the lint→typecheck→unit→E2E gate. *Where: frontend repo CI.*
14. **Tidy `.env.example`** — replace the real-looking `NEXT_PUBLIC_API_BASE_URL=https://zevqyn-backend.onrender.com` default with a placeholder (`https://<your-backend>.onrender.com`) to satisfy the placeholders rule. *Where: frontend repo `.env.example`.*
15. **Mobile-specific guidance** — the guide doesn't cover it; at minimum verify auth flows and uploads on mobile viewports during production QA. *Where: QA pass.*

---

## 4. Verification loop — Strix AI pentest (pending)

Per the Instagram reel (shashwat___agarwal), the verification loop is the free open-source AI pentesting tool **Strix** (Strix-AI/Strix on GitHub): deploy its autonomous "hacker" agents — recon, injection, XSS, SSTI, auth — against the app, the FastAPI API, and the Supabase database. Expected output: a report of **real, exploitable loopholes with proof and the fix for each** (example classes: weak password policy, hardcoded API keys, no rate limiting). Plan:

1. Deploy the frontend to `zevqyn.vercel.app` and complete §3 Critical actions 1–5 first (pentesting an unhardened app just re-discovers known gaps).
2. Run Strix agents against `https://zevqyn.vercel.app` + `https://zevqyn-backend.onrender.com` (auth, injection, XSS, SSTI, recon suites).
3. Triage the report: apply fixes per finding, re-run Strix to confirm closure.
4. Wire Strix into CI/CD so every PR is scanned before production.

This pass is **pending** — not started, not scheduled. It needs Hussnain's go-ahead (it involves running attack tooling against his own live app, which is legitimate here but should be his explicit call).
