import os
import httpx

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SECRET_KEY")

query = """
SELECT
    c.conname AS constraint_name
FROM
    pg_constraint c
JOIN
    pg_class t ON c.conrelid = t.oid
JOIN
    pg_attribute a ON a.attnum = ANY(c.conkey) AND a.attrelid = t.oid
WHERE
    t.relname = 'portfolios' AND a.attname = 'slug' AND c.contype = 'u';
"""

# The RPC might not be available, let's just attempt to insert a duplicate and see what happens.
import json

data = {
    "user_id": "00000000-0000-0000-0000-000000000000",
    "slug": "test-slug-123",
    "display_name": "Test",
    "theme": "light"
}

# Insert first
httpx.post(f"{url}/rest/v1/portfolios", headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Prefer": "return=minimal"}, json=data)

# Insert duplicate
r2 = httpx.post(f"{url}/rest/v1/portfolios", headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Prefer": "return=minimal"}, json=data)

print(r2.status_code, r2.text)

# Cleanup
httpx.delete(f"{url}/rest/v1/portfolios?slug=eq.test-slug-123", headers={"apikey": key, "Authorization": f"Bearer {key}"})
