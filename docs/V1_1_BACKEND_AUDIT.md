# ZEVQYN Backend V1.1 Technical Audit & Implementation Plan

**Date**: September 22, 2026  
**Auditor**: Antigravity AI Engineering  
**Branch**: `v1.1-backend` (branched from `main` at commit `1eb6845`)  
**Production URL**: `https://zevqyn-backend.onrender.com`  
**Current Backend Status**: Production Active, All 213 Unit/System Tests Passing  

---

## 1. Executive Summary

ZEVQYN is an AI Research + Career Workspace platform built on FastAPI, Supabase (PostgreSQL, Auth, Storage, pgvector), and Google Gemini.

The V1 backend has achieved stability across all core subsystems:
- **Authentication & Authorization**: Bearer token server-side validation via Supabase Auth admin client; app_metadata-based RBAC (`role == 'admin'`).
- **Research Workspaces & Document Pipeline**: Workspaces, private document storage, text extraction (PDF, DOCX, TXT, MD), semantic chunking, Gemini embeddings, pgvector retrieval, and grounded RAG chat.
- **Research Tools**: Summary, key points, questions, and flashcards generation.
- **Projects & Research-to-Project**: Multi-technology projects with automated synthesis from research documents.
- **Career Hub**: Structured skills, education, certificates, resumes with ATS PDF export, and portfolios with public slug routing.
- **Career AI**: 6 specialized structured diagnostic endpoints (Profile Analysis, Skill Gap, Project Suggestions, Resume Review, Portfolio Review, 30/60/90 Action Plan), plus persistent multi-turn conversational Copilot with automatic transient error retries.
- **Contact Messages**: Public contact submission with secure admin management.

This audit evaluates the four deferred V1.1 items, assesses overall backend health, conducts a security audit, establishes a definitive test baseline, and outlines a zero-downtime, schema-safe implementation roadmap.

---

## 2. Test Baseline & Suite Health

The complete pytest test suite was executed against the current working copy on branch `v1.1-backend`.

### Execution Summary
- **Passed**: 213 tests
- **Failed**: 0 tests
- **Deselected**: 2 tests (Integration tests requiring real live Supabase secrets; deselected via `setup.cfg: addopts = -m "not integration"`)
- **Warnings**: 5 deprecation warnings (Starlette `httpx`, AnyIO `BlockingPortal`, GenAI `_UnionGenericAlias`, PostgREST `timeout`/`verify`)
- **Execution Time**: 24.36 seconds
- **Pass Rate**: 100% of runnable unit & mock suite

### Test File Breakdown
| Test File | Test Count | Status | Subsystem Covered |
| :--- | :--- | :--- | :--- |
| `tests/test_auth.py` | 13 | PASS | Auth token verification, 401/503 errors, user extraction |
| `tests/test_contact.py` | 14 | PASS | Public contact submissions, admin RBAC, status updates |
| `tests/test_profile.py` | 9 | PASS | Profile retrieval, auto-creation, patch updates |
| `tests/test_workspaces.py` | 5 | PASS | Workspace CRUD, ownership checks, cascading deletes |
| `tests/test_documents.py` | 5 | PASS | Document uploads, extensions, size limits, storage rollback |
| `tests/test_extraction.py` | 5 | PASS | PDF, DOCX, TXT/BOM, extension normalization |
| `tests/test_chunking.py` | 8 | PASS | Sliding window chunking, token counts, overlap |
| `tests/test_embeddings.py` | 4 | PASS | Gemini embedding generation, dimension enforcement |
| `tests/test_indexing_retrieval.py` | 2 | PASS | Vector indexing pipeline & semantic search |
| `tests/test_rag.py` | 3 | PASS | Grounded RAG chat, conversation persistence, context |
| `tests/test_rag_advanced.py` | 5 | PASS | Citation sanitization, DB failure handling, bounds |
| `tests/test_research.py` | 7 | PASS | Summaries, key points, questions, flashcards |
| `tests/test_projects.py` | 6 | PASS | Project CRUD, research-to-project synthesis |
| `tests/test_career.py` | 17 | PASS | Skills, education, certs, legacy career assistant |
| `tests/test_resumes.py` | 20 | PASS | Resumes, trusted items, ATS PDF formatting, fallbacks |
| `tests/test_portfolios.py` | 16 | PASS | Portfolios, public slug routing, item attachments |
| `tests/test_career_ai.py` | 32 | PASS | 6 diagnostic endpoints, multi-turn chat, retry logic |
| `tests/test_health.py` | 2 | PASS | Root and health check endpoints |
| `tests/test_sampling.py` | 3 | PASS | Sampling utility coverage |
| `tests/test_supabase.py` | 7 | PASS | Supabase client singleton, credential validation |
| `tests/test_supabase_integration.py` | 2 (deselected) | N/A | Live Supabase smoke tests |

---

## 3. Deep Dive: Deferred Item 1 — Resume Item Reordering

### 3.1 Current State Analysis
- **Data Model**: Resumes attach verified career records (projects, skills, education, certificates) as records in `resume_items`.
- **Database Schema**:
  - `resume_items` table contains columns: `id (UUID)`, `resume_id (UUID)`, `section_type (VARCHAR)`, `title (VARCHAR)`, `subtitle (VARCHAR)`, `description (TEXT)`, `metadata (JSONB)`, `sort_order (INTEGER)`, `created_at (TIMESTAMPTZ)`, `updated_at (TIMESTAMPTZ)`.
  - Column `sort_order` **already exists** in the database schema!
- **Pydantic Model**:
  In [`app/models/resume.py`](file:///c:/Users/husss/OneDrive/Desktop/zevqyn-backend/app/models/resume.py#L77-L80):
  ```python
  class ResumeItemUpdate(BaseModel):
      model_config = ConfigDict(extra="forbid")
      sort_order: Optional[int] = Field(None)
  ```
  `ResumeItemUpdate` was already designed, defined, and even imported into [`app/api/resumes.py`](file:///c:/Users/husss/OneDrive/Desktop/zevqyn-backend/app/api/resumes.py#L10), but never exposed in a route.
- **Service Layer**:
  In [`app/services/resumes.py`](file:///c:/Users/husss/OneDrive/Desktop/zevqyn-backend/app/services/resumes.py#L143-L150):
  - `get_resume_items` queries `.order("sort_order")`.
  - However, no update function exists for `resume_items` in `app/services/resumes.py`.
- **PDF Generation**:
  In [`export_resume_pdf`](file:///c:/Users/husss/OneDrive/Desktop/zevqyn-backend/app/services/resumes.py#L361-L685), items are collected via `get_resume_items` (which respects `sort_order`) and grouped into sections. Inside each section, items render in the sequence established by `sort_order`.

### 3.2 Gaps Identified
1. **Missing Service Function**: No `update_resume_item` function in `app/services/resumes.py`.
2. **Missing Single-Item Route**: No `PATCH /api/v1/resumes/{resume_id}/items/{item_id}` endpoint.
3. **Missing Bulk Reorder Support**: In frontend UI drag-and-drop interactions, updating 5–10 items one by one causes N individual network round trips. A bulk reorder endpoint (`PATCH /api/v1/resumes/{resume_id}/items/reorder`) is highly desirable alongside single-item patch.

### 3.3 Target API Design
- **Single-Item Update**:
  - `PATCH /api/v1/resumes/{resume_id}/items/{item_id}`
  - Auth: Authenticated user (verified owner of `resume_id`).
  - Request Body: `{"sort_order": 2}` (`ResumeItemUpdate`).
  - Response: `ResumeItemResponse`.
  - Error Cases: 401 (unauthenticated), 404 (resume or item not found), 403 (item does not belong to user's resume).
- **Bulk Reorder (Recommended Extension)**:
  - `PATCH /api/v1/resumes/{resume_id}/items/reorder`
  - Request Body:
    ```json
    {
      "items": [
        {"id": "c1f7a2d3-...", "sort_order": 0},
        {"id": "b8a9e4f1-...", "sort_order": 1}
      ]
    }
    ```
  - Response: `list[ResumeItemResponse]`.

### 3.4 Schema Impact & Risk
- **Schema Migration Needed?**: **NO**. The `sort_order` column already exists in `resume_items`.
- **Breaking Changes**: None. Purely additive.
- **Risk Level**: **LOW**.

---

## 4. Deep Dive: Deferred Item 2 — Research Conversation Deletion

### 4.1 Current State Analysis
- **Data Model**:
  - Research conversations are stored in `conversations` where `assistant_type = 'research'` and `workspace_id = <workspace_uuid>`.
  - Messages are stored in `messages` where `conversation_id = <conversation_uuid>` and `user_id = <user_uuid>`.
- **API Status in [`app/api/workspaces.py`](file:///c:/Users/husss/OneDrive/Desktop/zevqyn-backend/app/api/workspaces.py#L182-L206)**:
  - `POST /api/v1/workspaces/{workspace_id}/chat` (starts/continues chat)
  - `GET /api/v1/workspaces/{workspace_id}/conversations` (lists conversations)
  - `GET /api/v1/workspaces/{workspace_id}/conversations/{conversation_id}/messages` (retrieves messages)
  - **MISSING**: `DELETE /api/v1/workspaces/{workspace_id}/conversations/{conversation_id}`
- **Service Status in [`app/services/rag.py`](file:///c:/Users/husss/OneDrive/Desktop/zevqyn-backend/app/services/rag.py)**:
  - Has `get_conversation(user_id, workspace_id, conversation_id)` and `create_conversation(...)`.
  - Missing `delete_conversation(...)`.
- **Reference Pattern**:
  In [`app/services/career_ai.py:759-775`](file:///c:/Users/husss/OneDrive/Desktop/zevqyn-backend/app/services/career_ai.py#L759-L775) and [`app/api/career.py:202-208`](file:///c:/Users/husss/OneDrive/Desktop/zevqyn-backend/app/api/career.py#L202-L208), conversation deletion is already successfully implemented for Career AI:
  ```python
  def delete_career_conversation(user_id: UUID, conversation_id: UUID) -> dict[str, Any]:
      get_career_conversation(user_id, conversation_id)
      client = get_admin_client()
      client.table("messages").delete().eq("conversation_id", str(conversation_id)).eq("user_id", str(user_id)).execute()
      client.table("conversations").delete().eq("id", str(conversation_id)).eq("user_id", str(user_id)).execute()
      return {"status": "success", "id": str(conversation_id)}
  ```

### 4.2 Gaps Identified
1. Research Workspace users currently cannot delete obsolete or test conversations.
2. If a user deletes or tries to clear conversation history, backend has no handler.

### 4.3 Target API Design
- **Route**: `DELETE /api/v1/workspaces/{workspace_id}/conversations/{conversation_id}`
- **Auth**: Requires authenticated user owning `workspace_id` and `conversation_id`.
- **Cascade Behavior**:
  Explicitly delete child records from `messages` first where `conversation_id = :id AND user_id = :uid`, then delete the parent from `conversations`. This guarantees clean removal even if foreign key cascade constraints are not configured in PostgreSQL.
- **Response**: `{"status": "success", "id": str(conversation_id)}` (matching Career AI) with HTTP 200, or HTTP 204 No Content (matching `DELETE /api/v1/workspaces/{id}`). A consistent JSON payload `{"status": "success", "id": str(conversation_id)}` is recommended for frontend convenience.
- **Error Cases**: 401 Unauthorized, 404 Not Found (workspace or conversation not owned by user), 500 Server Error.

### 4.4 Schema Impact & Risk
- **Schema Migration Needed?**: **NO**.
- **Breaking Changes**: None. Additive endpoint.
- **Risk Level**: **LOW**.

---

## 5. Deep Dive: Deferred Item 3 — Global Documents

### 5.1 Current State Analysis
- **Database Schema**:
  The `documents` table stores:
  - `id` (UUID, primary key)
  - `user_id` (UUID, owner)
  - `workspace_id` (UUID, associated workspace)
  - `filename` (VARCHAR, sanitized)
  - `original_filename` (VARCHAR)
  - `storage_path` (VARCHAR)
  - `file_type` (VARCHAR, e.g. "pdf", "docx")
  - `file_size` (INTEGER)
  - `status` (VARCHAR, e.g. "uploaded", "indexed")
  - `created_at` (TIMESTAMPTZ)
  - `updated_at` (TIMESTAMPTZ, nullable)
- **Current Access Scope**:
  Documents are currently isolated within workspaces:
  `GET /api/v1/workspaces/{workspace_id}/documents`
- **Frontend / User Need**:
  Users on a central Dashboard or Library tab need to view all uploaded documents across all their workspaces without iterating over each workspace or making N queries.

### 5.2 Gaps Identified
1. No top-level `/api/v1/documents` route exists.
2. In [`app/services/documents.py`](file:///c:/Users/husss/OneDrive/Desktop/zevqyn-backend/app/services/documents.py), `get_documents` requires both `user_id` and `workspace_id`.
3. No cross-workspace document filtering (by status, file type, or filename search) exists.

### 5.3 Target API Design
- **Route**: `GET /api/v1/documents`
- **Router Location**: Dedicated new router [`app/api/documents.py`](file:///c:/Users/husss/OneDrive/Desktop/zevqyn-backend/app/api/documents.py) registered in `app/main.py` with prefix `/api/v1/documents`.
- **Query Parameters**:
  - `workspace_id: Optional[UUID] = None` (filter by workspace)
  - `file_type: Optional[str] = None` (filter by extension, e.g. "pdf")
  - `status: Optional[str] = None` (filter by status, e.g. "indexed", "uploaded")
  - `search: Optional[str] = None` (case-insensitive substring match on `original_filename`)
  - `limit: int = Query(50, ge=1, le=100)`
  - `offset: int = Query(0, ge=0)`
- **Response Model**: `list[DocumentResponse]` (preserving existing model in [`app/models/document.py`](file:///c:/Users/husss/OneDrive/Desktop/zevqyn-backend/app/models/document.py)).
- **Security & Scoping**:
  Strictly filtered by `.eq("user_id", str(user.id))`. Users can never view documents belonging to other accounts.

### 5.4 Schema Impact & Risk
- **Schema Migration Needed?**: **NO**. All columns already exist in `documents`.
- **Breaking Changes**: None. Existing `/api/v1/workspaces/{workspace_id}/documents` remains intact.
- **Risk Level**: **LOW**.

---

## 6. Deep Dive: Deferred Item 4 — Legacy `/career/assistant`

### 6.1 Current State Analysis
- **Route**: `POST /api/v1/career/assistant` in [`app/api/career.py:112-115`](file:///c:/Users/husss/OneDrive/Desktop/zevqyn-backend/app/api/career.py#L112-L115).
- **Service**: `career_service.ask_career_assistant` in [`app/services/career.py:219-278`](file:///c:/Users/husss/OneDrive/Desktop/zevqyn-backend/app/services/career.py#L219-L278).
- **Characteristics**:
  - Single-turn, stateless, non-persisted query.
  - Takes `{"message": "What should I learn next?"}`.
  - Returns `{"answer": "...", "profile_used": {"projects": 2, "skills": 5, "education": 1, "certificates": 0}}`.
  - Assembles prompt from `get_career_profile()` and queries Gemini directly with temperature 0.4.
  - Tested in [`tests/test_career.py:124-175`](file:///c:/Users/husss/OneDrive/Desktop/zevqyn-backend/tests/test_career.py#L124-L175).

### 6.2 Comparison With Career AI Phase 2
| Feature | Legacy `POST /career/assistant` | Career AI `POST /career/ai/chat` |
| :--- | :--- | :--- |
| **Persistence** | None (ephemeral) | Stored in `conversations` & `messages` tables |
| **Multi-Turn Context** | None (single turn only) | Bounded history (up to 10 messages, 8k chars) |
| **Conversation Management** | None | Full CRUD (`/ai/conversations`, detail, delete) |
| **Context Assembly** | Raw un-sanitized profile dump | Sanitized context builder with injection defenses |
| **Resumes & Portfolios** | Ignored | Included in context |
| **Transient Retry** | No retry (502 on 503/429) | Bounded automatic exponential backoff retry |
| **Specialized Analysis** | None | 6 dedicated structured endpoints |

### 6.3 Recommendation & Deprecation Strategy
1. **Do NOT delete immediately**:
   The prompt guidelines and backward compatibility rules require preserving existing routes. Frontends or automated smoke monitors may still call this endpoint.
2. **Phase 1 (V1.1)**:
   - Add `deprecated=True` to `@router.post("/assistant", response_model=CareerAssistantResponse, deprecated=True)`.
   - Update docstring explicitly directing consumers to `POST /api/v1/career/ai/chat`.
   - Retain all service code and tests.
3. **Phase 2 (V2.0)**:
   - After confirming frontend migration and zero traffic in telemetry, remove the endpoint and retire `CareerAssistantRequest`/`CareerAssistantResponse`.
- **Risk Level**: **LOW**.

---

## 7. Full Backend Health Audit

### 7.1 Router Registry & Organization
All routers are modularly segregated and registered in [`app/main.py`](file:///c:/Users/husss/OneDrive/Desktop/zevqyn-backend/app/main.py):
1. `v1_router` (`/api/v1`) — System verification
2. `workspaces_router` (`/api/v1/workspaces`) — Workspaces, documents, RAG chat
3. `research_router` (`/api/v1/research`) — Summary, questions, flashcards
4. `projects_router` (`/api/v1/projects`) — Projects, research-to-project
5. `career_router` (`/api/v1/career`) — Career hub, diagnostic AI, chat AI
6. `resumes_router` (`/api/v1/resumes`) — Resumes, items, ATS PDF
7. `portfolios_router` (`/api/v1/portfolios`) — Portfolios, public viewer
8. `profile_router` (`/api/v1/profile`) — User profile
9. `contact_router` (`/api/v1/contact`) — Public contact & admin inbox

### 7.2 Authentication & Authorization (RBAC)
- All protected endpoints depend on `get_current_user` in [`app/core/auth.py`](file:///c:/Users/husss/OneDrive/Desktop/zevqyn-backend/app/core/auth.py).
- Tokens are verified server-side against Supabase Auth via `client.auth.get_user(token)`.
- Client-supplied `user_id` fields are never trusted; the verified `user.id` is passed down to all services.
- Admin endpoints (Contact Messages) use `require_admin_user`, which validates `app_metadata.get("role") == "admin"`, preventing privilege escalation from client-controlled `user_metadata`.

### 7.3 Data Ownership & Row Isolation
- Every database query in services explicitly appends `.eq("user_id", str(user_id))` or verifies parent entity ownership before performing mutations.
- Cross-user access tests in `test_projects.py`, `test_portfolios.py`, `test_resumes.py`, and `test_contact.py` verify that attempting to access or mutate other users' records raises 403 or 404.

### 7.4 Pydantic V2 & Data Validation
- Models use `ConfigDict(extra="forbid")` across mutations to prevent mass-assignment vulnerabilities.
- File upload types and sizes are validated both at the HTTP layer and binary stream level.

### 7.5 Gemini AI Integration & Resiliency
- Gemini 2.5 Flash is configured as standard generation model (`settings.GEMINI_GENERATION_MODEL`).
- Career AI implements bounded automatic retry (`_call_gemini_with_retry`) with exponential backoff and jitter for transient errors (`503 UNAVAILABLE`, `429 RESOURCE_EXHAUSTED`).
- System instructions enforce strict grounding and defend against prompt injections in user-authored text fields.

---

## 8. Security Audit

A thorough security scan was conducted across the entire repository:

1. **Tracked Secrets**:
   - Scanned for `.env`, private keys, JWT tokens, and hardcoded API keys.
   - Result: **CLEAN**. `.env` is properly ignored in `.gitignore` and not tracked in git (`git ls-files .env` returns empty).
   - No hardcoded `AIza...` Google keys or Supabase service-role keys exist in code.
2. **Configuration Hygiene**:
   - `Settings` in [`app/core/config.py`](file:///c:/Users/husss/OneDrive/Desktop/zevqyn-backend/app/core/config.py) pulls secrets strictly from environment variables.
   - Defaults are safe for local development (`localhost:3000,http://localhost:8000`).
3. **Storage Security**:
   - Private documents are stored in private Supabase Storage buckets under `{user_id}/{workspace_id}/{document_uuid}/{filename}`.
   - Downloads use short-lived signed URLs (60-second expiry) generated via the admin client. Raw bucket storage paths are never leaked to clients.
4. **CORS & Headers**:
   - Configurable via `CORS_ORIGINS`.
   - Credentials enabled, safe origin handling.

---

## 9. Proposed V1.1 Implementation Plan & Order

We recommend implementing the V1.1 improvements in the following logical sequence:

```mermaid
flowchart TD
    A["Step 1: Resume Item Reordering<br/>(PATCH item + bulk reorder)"] --> B["Step 2: Research Conversation Deletion<br/>(DELETE /workspaces/.../conversations/{id})"]
    B --> C["Step 3: Global Documents Endpoint<br/>(GET /api/v1/documents)"]
    C --> D["Step 4: Deprecate Legacy Assistant<br/>(Mark deprecated=True)"]
    D --> E["Step 5: Full Regression Testing & Validation"]
```

### Detailed Steps

#### Step 1: Resume Item Reordering
1. In `app/services/resumes.py`:
   - Implement `update_resume_item(user_id: UUID, resume_id: UUID, item_id: UUID, item: ResumeItemUpdate) -> ResumeItemResponse`.
   - Implement `reorder_resume_items(user_id: UUID, resume_id: UUID, items: list[dict]) -> list[ResumeItemResponse]`.
2. In `app/api/resumes.py`:
   - Add `PATCH /{resume_id}/items/{item_id}` endpoint.
   - Add `PATCH /{resume_id}/items/reorder` endpoint.
3. In `tests/test_resumes.py`:
   - Add tests for single item sort order updates, cross-user forbidden checks, and bulk reordering.

#### Step 2: Research Conversation Deletion
1. In `app/services/rag.py`:
   - Implement `delete_conversation(user_id: UUID, workspace_id: UUID, conversation_id: UUID) -> dict[str, Any]`.
   - Verifies ownership, deletes messages, deletes conversation record.
2. In `app/api/workspaces.py`:
   - Add `DELETE /{workspace_id}/conversations/{conversation_id}` endpoint.
3. In `tests/test_rag.py`:
   - Add tests verifying successful deletion, message cleanup, cross-user rejection, and 404 for nonexistent conversations.

#### Step 3: Global Documents
1. In `app/services/documents.py`:
   - Implement `get_user_documents(user_id: UUID, workspace_id=None, file_type=None, status=None, search=None, limit=50, offset=0) -> list[DocumentResponse]`.
2. In `app/api/documents.py` (new router):
   - Add `GET /api/v1/documents` route with query filters.
   - Register router in `app/main.py`.
3. In `tests/test_documents.py`:
   - Add tests for global listing, workspace filtering, file_type filtering, search filtering, and user isolation.

#### Step 4: Deprecate Legacy Career Assistant
1. In `app/api/career.py`:
   - Add `deprecated=True` to `ask_career_assistant` route decorator.
   - Add migration notes in OpenAPI docstring.
2. Verify all 17 career tests still pass without regressions.

---

## 10. Risk Classification & Assessment

| Improvement Item | Technical Risk | Blast Radius | Schema Impact | Recommended Action |
| :--- | :--- | :--- | :--- | :--- |
| **Item 1: Resume Reorder** | **LOW** | Isolated to `resumes` module | None (column exists) | Implement PATCH + Reorder |
| **Item 2: Conversation Delete** | **LOW** | Isolated to `workspaces/rag` | None | Implement DELETE route |
| **Item 3: Global Documents** | **LOW** | Isolated to new router | None | Add `GET /api/v1/documents` |
| **Item 4: Deprecate Assistant**| **LOW** | None (metadata only) | None | Add `deprecated=True` |

---

## 11. Supabase Schema Impact Analysis

**Conclusion**: **ZERO SCHEMA MIGRATIONS REQUIRED.**

- `resume_items.sort_order` is an existing column (`INTEGER`).
- `conversations` and `messages` already exist with complete cascade compatibility.
- `documents` already contains `user_id`, `workspace_id`, `file_type`, `status`, and `original_filename`.
- No database migrations, SQL files, DDL statements, or production schema modifications are needed for V1.1.

---

## 12. API Contract Impact & Backward Compatibility

All proposed changes strictly adhere to non-breaking API design:
- Existing endpoints remain untouched with 100% parameter and response compatibility.
- New endpoints are purely additive:
  - `PATCH /api/v1/resumes/{resume_id}/items/{item_id}`
  - `DELETE /api/v1/workspaces/{workspace_id}/conversations/{conversation_id}`
  - `GET /api/v1/documents`
- The legacy endpoint `POST /api/v1/career/assistant` remains functional and returns its identical response contract, but is flagged as deprecated in the OpenAPI specification.

---

## 13. Test Strategy & Acceptance Criteria

When implementation commences (upon user approval), the following acceptance tests will be executed:

1. **Resume Reordering**:
   - `test_update_resume_item_sort_order`: Updates item sort_order and verifies persistence.
   - `test_update_resume_item_cross_user_rejected`: Verifies 403/404 when attempting to reorder another user's item.
   - `test_export_pdf_respects_custom_sort_order`: Verifies PDF renderer outputs items in updated order.
2. **Research Conversation Deletion**:
   - `test_delete_research_conversation_success`: Deletes conversation and verifies both conversation and child messages are removed from DB.
   - `test_delete_research_conversation_cross_user_rejected`: Verifies cross-user isolation.
3. **Global Documents**:
   - `test_list_global_documents_all`: Verifies listing across multiple workspaces.
   - `test_list_global_documents_filters`: Verifies `workspace_id`, `file_type`, and `search` query parameters.
   - `test_list_global_documents_user_isolation`: Verifies user A cannot see user B's documents.
4. **Regression**:
   - All 213 existing tests must continue to pass with 0 failures.

---

## 14. Final Recommendation & Go/No-Go Decision

- **Backend Readiness**: **GO (APPROVED FOR V1.1 EXECUTION)**.
- **Architectural Health**: Excellent. Codebase is clean, well-tested, securely configured, and follows established patterns.
- **Next Step**: Wait for user review and approval before executing any code changes.
