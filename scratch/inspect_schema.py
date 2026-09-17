import os
from dotenv import load_dotenv
import httpx
import json

load_dotenv()
url = os.getenv("SUPABASE_URL").rstrip("/")
if url.endswith("rest/v1"): url = url[:-7]
key = os.getenv("SUPABASE_SECRET_KEY")

r = httpx.get(f"{url}/rest/v1/", headers={"apikey": key, "Authorization": f"Bearer {key}"})
data = r.json()
definitions = data.get("definitions", {})

tables_to_check = ["flashcards", "questions", "documents", "document_chunks", "workspaces", "conversations", "messages"]
for table in tables_to_check:
    if table in definitions:
        print(f"\n--- {table} ---")
        for k, v in definitions[table].get("properties", {}).items():
            print(f"{k}: {v.get('type')} {v.get('format', '')}")
    else:
        print(f"\n--- {table} NOT FOUND ---")
