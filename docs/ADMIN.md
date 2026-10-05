# ZEVQYN Admin Panel — setup & operations

The admin panel (`/app/admin` on the frontend) is gated by its own credential
system, separate from end-user Supabase Auth. This document explains how to
set it up and operate it.

## How it works

- Table `public.admin_users` holds `username` + a PBKDF2-HMAC-SHA256 password
  hash. Only the backend service-role key can read/write it (RLS revoked for
  `anon`/`authenticated`). Apply `supabase/sql/create_admin_users_table.sql`
  once in the Supabase SQL editor.
- On every backend startup, if the table is **empty** and the env vars below
  are set, the backend seeds the first admin. It never overwrites an existing
  row — so changing the password later in the UI is permanent.
- `POST /api/v1/admin/login` returns a 12-hour JWT (HS256). The frontend
  stores it separately from the Supabase session and sends it as
  `Authorization: Bearer <admin-token>` to `/api/v1/admin/*`.
- `POST /api/v1/admin/change-password` changes the password (current password
  required). Use this right after first login instead of leaving the seeded
  password in env vars.

## Required Render environment variables

Set these on the `zevqyn-backend` Render service (Environment tab), then
**Manual Deploy** (or push) so the seed runs:

| Variable           | Purpose                                              |
|--------------------|------------------------------------------------------|
| `ADMIN_ID`         | Admin login ID you choose (e.g. `hussnain`)          |
| `ADMIN_PASSWORD`   | Initial admin password (change it in the UI after)   |
| `ADMIN_JWT_SECRET` | Long random string signing admin tokens — generate with `openssl rand -hex 32` |

If these are missing, the admin table stays empty and `/login` returns
`401 Invalid admin credentials` (generic on purpose).

## Endpoints (all except /login need the admin token)

| Method | Path                              | Purpose                          |
|--------|-----------------------------------|----------------------------------|
| POST   | `/api/v1/admin/login`             | ID + password → session token (10/min/IP) |
| POST   | `/api/v1/admin/change-password`   | Change admin password            |
| GET    | `/api/v1/admin/users`             | List users (paginated)           |
| POST   | `/api/v1/admin/users`             | Manually create a user (email pre-confirmed) |
| PATCH  | `/api/v1/admin/users/{id}`        | Update email / password / ban    |
| DELETE | `/api/v1/admin/users/{id}`        | Delete a user permanently        |
| GET    | `/api/v1/admin/stats`             | Platform totals for the dashboard |

## Notes

- The contact inbox (`/api/v1/contact/messages*`) accepts **either** the new
  admin JWT **or** the legacy Supabase `app_metadata.role == "admin"` user —
  nothing that worked before breaks.
- Deleting a user removes their Supabase Auth record; their workspace rows
  remain orphaned (listed under their old user id). This is v1 behavior.
- Banning sets `ban_duration` to 1 year via the Supabase Auth admin API;
  unban sets it back to `none`.
