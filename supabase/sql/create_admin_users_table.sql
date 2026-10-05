-- ZEVQYN admin credentials table.
--
-- Stores the dedicated admin-panel login (username + PBKDF2 password hash).
-- This is SEPARATE from Supabase Auth users: it gates /api/v1/admin/* only.
--
-- Seeding: the backend seeds one row on startup when the table is empty AND
-- the ADMIN_ID / ADMIN_PASSWORD environment variables are set. The password
-- can later be changed from the admin UI (change-password endpoint); the
-- seed never overwrites an existing row.
--
-- Apply once in the Supabase SQL editor (or via your migration flow).

create table if not exists public.admin_users (
    id uuid primary key default gen_random_uuid(),
    username text not null unique,
    password_hash text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Only the backend service-role key may touch this table. Revoke any
-- permissive grants if they were ever added.
revoke all on public.admin_users from anon, authenticated;
