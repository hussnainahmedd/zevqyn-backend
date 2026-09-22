# ZEVQYN V1.1 Frontend Integration Guide

This guide provides the exact integration contracts for the new endpoints introduced in ZEVQYN Backend V1.1.

---

## 1. Resume Item Reordering

Resumes contain verified career records (projects, skills, education, certificates) attached as `resume_items`. V1.1 provides two ways to update item ordering: single-item update and bulk reorder.

### A. Bulk Reorder (Recommended for Drag-and-Drop)

When a user drags and drops items within a resume, send a single bulk update rather than individual requests.

- **Endpoint**: `PATCH /api/v1/resumes/{resume_id}/items/reorder`
- **Method**: `PATCH`
- **Authentication**: Required (`Authorization: Bearer <supabase_access_token>`)
- **Request Body**:
  ```json
  {
    "items": [
      {
        "id": "c1f7a2d3-1111-4444-8888-123456789abc",
        "sort_order": 0
      },
      {
        "id": "b8a9e4f1-2222-4444-8888-abcdef123456",
        "sort_order": 1
      },
      {
        "id": "d9e8f7a6-3333-4444-8888-987654321fed",
        "sort_order": 2
      }
    ]
  }
  ```
- **Validation Constraints**:
  - `items`: non-empty array of items (`min_length=1`).
  - `id`: valid UUID string.
  - `sort_order`: integer >= 0.
  - Duplicate IDs within the same payload are rejected (`422 Unprocessable Entity`).
  - All supplied item IDs must belong to the target `resume_id`. If any item belongs to another resume or does not exist, the request is rejected *before* any database changes are made.
- **Success Response** (`200 OK`):
  Returns the complete updated list of resume items in their effective sorted order:
  ```json
  [
    {
      "id": "c1f7a2d3-1111-4444-8888-123456789abc",
      "resume_id": "9a8b7c6d-5555-4444-8888-000011112222",
      "section_type": "project",
      "title": "ZEVQYN AI Platform",
      "subtitle": "Python, FastAPI, pgvector",
      "description": "Full-stack AI workspace platform",
      "metadata": {
        "source_id": "...",
        "source_type": "project"
      },
      "sort_order": 0,
      "created_at": "2026-01-01T00:00:00Z",
      "updated_at": "2026-01-01T00:00:00Z"
    },
    {
      "id": "b8a9e4f1-2222-4444-8888-abcdef123456",
      "resume_id": "9a8b7c6d-5555-4444-8888-000011112222",
      "section_type": "project",
      "title": "Autonomous Agent System",
      "subtitle": "TypeScript, React",
      "description": "Agent coordination framework",
      "metadata": {
        "source_id": "...",
        "source_type": "project"
      },
      "sort_order": 1,
      "created_at": "2026-01-01T00:00:00Z",
      "updated_at": "2026-01-01T00:00:00Z"
    }
  ]
  ```
- **Error Responses**:
  - `400 Bad Request`: Item belongs to another resume, or duplicate IDs.
  - `401 Unauthorized`: Missing or invalid Bearer token.
  - `404 Not Found`: Resume does not exist or is not owned by the user, or item ID does not exist.
  - `422 Unprocessable Entity`: Validation failure (negative sort_order, empty items array).
- **Recommended UI Interaction**:
  1. Optimistically update local UI state when the user drags and drops items.
  2. Send `PATCH /api/v1/resumes/{resume_id}/items/reorder` with the new indices.
  3. On success, replace local items array with the returned list.
  4. On failure, revert local UI state to previous order and show an error notification.

---

### B. Single Item Update

Use this when modifying a single item's sort_order directly without reordering the entire list.

- **Endpoint**: `PATCH /api/v1/resumes/{resume_id}/items/{item_id}`
- **Method**: `PATCH`
- **Authentication**: Required (`Authorization: Bearer <supabase_access_token>`)
- **Request Body**:
  ```json
  {
    "sort_order": 3
  }
  ```
- **Success Response** (`200 OK`):
  ```json
  {
    "id": "c1f7a2d3-1111-4444-8888-123456789abc",
    "resume_id": "9a8b7c6d-5555-4444-8888-000011112222",
    "section_type": "project",
    "title": "ZEVQYN AI Platform",
    "subtitle": "Python, FastAPI, pgvector",
    "description": "Full-stack AI workspace platform",
    "metadata": { ... },
    "sort_order": 3,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z"
  }
  ```
- **Error Responses**:
  - `400 Bad Request`: Item belongs to another resume.
  - `401 Unauthorized`: Missing or invalid token.
  - `404 Not Found`: Resume or item not found/unowned.
  - `422 Unprocessable Entity`: Negative sort_order or unrecognized fields.

---

## 2. Research Conversation Deletion

Allows users to delete old or test RAG chat conversations within a research workspace.

- **Endpoint**: `DELETE /api/v1/workspaces/{workspace_id}/conversations/{conversation_id}`
- **Method**: `DELETE`
- **Authentication**: Required (`Authorization: Bearer <supabase_access_token>`)
- **Request Body**: None
- **Success Response** (`200 OK`):
  ```json
  {
    "status": "success",
    "id": "4cb194d4-e2f2-41cd-95da-2b3d0a18047b"
  }
  ```
- **Security & Scope Guard**:
  - Strictly restricted to Research conversations (`assistant_type == 'research'`).
  - Cannot be used to delete Career AI conversations. Attempting to delete a Career AI conversation through this route returns `404 Not Found or access denied`.
  - Both `workspace_id` and `conversation_id` must be owned by the authenticated user.
- **Backend Cascade**:
  - Deletes all associated messages from the `messages` table.
  - Deletes the conversation record from `conversations`.
- **Error Responses**:
  - `401 Unauthorized`: Missing or invalid token.
  - `404 Not Found`: Workspace not found, conversation not found, or conversation belongs to another user/workspace/type.
- **Recommended UI Interaction**:
  1. Show a confirmation dialog ("Are you sure you want to delete this conversation? This will delete all chat history.").
  2. Send the `DELETE` request.
  3. On success, remove the conversation from the sidebar list.
  4. If the deleted conversation was currently active in the chat pane, redirect or clear the chat view to prompt starting a new conversation.

---

## 3. Global Documents

Allows users to view, search, filter, and paginate all documents they have uploaded across all workspaces from a single dashboard view.

- **Endpoint**: `GET /api/v1/documents`
- **Method**: `GET`
- **Authentication**: Required (`Authorization: Bearer <supabase_access_token>`)
- **Query Parameters**:
  | Parameter | Type | Required | Default | Description |
  | :--- | :--- | :--- | :--- | :--- |
  | `workspace_id` | UUID | No | `null` | Filter by specific workspace |
  | `file_type` | string | No | `null` | Filter by extension (e.g. `pdf`, `docx`, `txt`, `md`). Leading dots are automatically stripped. |
  | `status` | string | No | `null` | Filter by status (e.g. `uploaded`, `indexed`, `extracting`) |
  | `search` | string | No | `null` | Case-insensitive substring search on `original_filename` |
  | `limit` | integer | No | `50` | Maximum results to return (`ge=1, le=100`) |
  | `offset` | integer | No | `0` | Number of records to skip (`ge=0`) |
- **Success Response** (`200 OK`):
  ```json
  [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "user_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "workspace_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "original_filename": "Q3_AI_Research_Report.pdf",
      "file_type": "pdf",
      "file_size": 2457600,
      "status": "indexed",
      "created_at": "2026-09-20T12:00:00Z",
      "updated_at": "2026-09-20T12:01:30Z"
    }
  ]
  ```
- **Default Ordering**: Always ordered newest first (`created_at DESC`).
- **User Scoping**: Automatically filtered by the authenticated user's ID. No user can see another user's documents.
- **Example Usage Scenarios**:
  1. *Global Library View*:
     `GET /api/v1/documents?limit=20&offset=0`
  2. *Live Filename Search in Dashboard*:
     `GET /api/v1/documents?search=contract`
  3. *Filter by Workspace and Type*:
     `GET /api/v1/documents?workspace_id=9b1deb4d-...&file_type=pdf`

---

## 4. Legacy Career Assistant Deprecation Notice

> [!WARNING]
> **Do NOT use `POST /api/v1/career/assistant` for new frontend features.**

- `POST /api/v1/career/assistant` is formally **deprecated** in V1.1 and scheduled for retirement in V2.0.
- It is a single-turn, unpersisted prompt that will not receive multi-turn memory or tool updates.
- **Use instead**:
  - For conversational Career AI: `POST /api/v1/career/ai/chat` (supports persistent conversations, multi-turn memory, bounded context, and automatic transient retries).
  - For conversation history: `GET /api/v1/career/ai/conversations` and `GET /api/v1/career/ai/conversations/{id}`.
  - For conversation deletion: `DELETE /api/v1/career/ai/conversations/{id}`.
  - For structured career analysis:
    - Profile Analysis: `POST /api/v1/career/ai/analyze`
    - Skill Gap: `POST /api/v1/career/ai/skill-gap`
    - Project Ideas: `POST /api/v1/career/ai/suggest-projects`
    - Resume Review: `POST /api/v1/career/ai/review-resume`
    - Portfolio Review: `POST /api/v1/career/ai/review-portfolio`
    - 30/60/90 Plan: `POST /api/v1/career/ai/action-plan`
