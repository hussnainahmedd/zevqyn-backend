"""Tests for document/workspace representative sampling strategy."""

import uuid
from unittest.mock import MagicMock, patch

from app.services.retrieval import get_representative_chunks

FAKE_USER = str(uuid.uuid4())
FAKE_WS = str(uuid.uuid4())

class MockQuery:
    def __init__(self, table_name):
        self.table_name = table_name
        self.filters = {}
        self._select = None
        self._order = None
        self._limit = None
        self._in_col = None
        self._in_vals = None

    def select(self, cols):
        self._select = cols
        return self

    def eq(self, col, val):
        self.filters[col] = val
        return self

    def order(self, col, desc=False):
        self._order = col
        return self

    def limit(self, l):
        self._limit = l
        return self
        
    def in_(self, col, vals):
        self._in_col = col
        self._in_vals = vals
        return self

    def execute(self):
        res = MagicMock()
        
        if self.table_name == "documents":
            res.data = [{"id": str(uuid.uuid5(uuid.NAMESPACE_OID, f"doc_{i}"))} for i in range(3)]
            return res
            
        if self.table_name == "document_chunks":
            if self._in_col == "id":
                res.data = []
                for vid in self._in_vals:
                    # Retrieve the mapped idx and doc_id (we will embed it in a side dict or rely on a deterministic UUID)
                    # Let's just lookup. We will have a global map.
                    pass
                return res
            else:
                pass
                
# Better approach: Just use uuid.uuid5 to generate deterministic UUIDs based on doc and chunk index
def make_uuid(s):
    return str(uuid.uuid5(uuid.NAMESPACE_OID, s))

class MockQuery:
    def __init__(self, table_name):
        self.table_name = table_name
        self.filters = {}
        self._select = None
        self._order = None
        self._limit = None
        self._in_col = None
        self._in_vals = None

    def select(self, cols):
        self._select = cols
        return self

    def eq(self, col, val):
        self.filters[col] = val
        return self

    def order(self, col, desc=False):
        self._order = col
        return self

    def limit(self, l):
        self._limit = l
        return self
        
    def in_(self, col, vals):
        self._in_col = col
        self._in_vals = vals
        return self

    def execute(self):
        res = MagicMock()
        
        if self.table_name == "documents":
            res.data = [{"id": make_uuid(f"doc_{i}")} for i in range(3)]
            return res
            
        if self.table_name == "document_chunks":
            if self._in_col == "id":
                res.data = []
                # In order to know what chunk this was, we can just search all our possible chunks
                # We know there are 3 docs with 10, 100, 5 chunks
                chunk_map = {}
                for d, c in [(0, 10), (1, 100), (2, 5)]:
                    doc_id = make_uuid(f"doc_{d}")
                    for i in range(c):
                        cid = make_uuid(f"chunk_{doc_id}_{i}")
                        chunk_map[cid] = (doc_id, i)
                        
                for vid in self._in_vals:
                    doc_id, idx = chunk_map[vid]
                    res.data.append({
                        "id": vid,
                        "document_id": doc_id,
                        "content": f"Text {idx}",
                        "chunk_index": idx,
                        "page_number": idx if idx % 2 == 0 else None
                    })
                return res
            else:
                doc_id = self.filters.get("document_id")
                if doc_id == make_uuid("doc_0"):
                    count = 10
                elif doc_id == make_uuid("doc_1"):
                    count = 100
                else:
                    count = 5
                    
                res.data = [{"id": make_uuid(f"chunk_{doc_id}_{i}"), "chunk_index": i} for i in range(count)]
                return res

@patch("app.services.retrieval.get_admin_client")
def test_sampling_algorithms(mock_db):
    mock_client = mock_db.return_value
    mock_client.table = lambda t: MockQuery(t)
    
    # 1. Test Small Document (Doc 0 has 10 chunks < 50)
    doc_0_id = make_uuid("doc_0")
    results = get_representative_chunks(uuid.UUID(FAKE_USER), uuid.UUID(FAKE_WS), doc_0_id, limit=50)
    assert len(results) == 10
    assert results[0].page_number == 0
    assert results[1].page_number is None # tests null page_number
    assert all(r.similarity is None for r in results) # no fabricated similarity
    
    # 2. Test Large Document (Doc 1 has 100 chunks > 10)
    doc_1_id = make_uuid("doc_1")
    results = get_representative_chunks(uuid.UUID(FAKE_USER), uuid.UUID(FAKE_WS), doc_1_id, limit=10)
    assert len(results) == 10
    
    # Map back the returned chunk IDs to indices using our deterministic generation
    def get_idx(cid, d_id):
        for i in range(100):
            if make_uuid(f"chunk_{d_id}_{i}") == str(cid):
                return i
        return -1
        
    indices = [get_idx(r.chunk_id, doc_1_id) for r in results]
    assert indices == [0, 11, 22, 33, 44, 55, 66, 77, 88, 99]
    
    # 3. Test Workspace Budget Distribution (3 docs: 10, 100, 5 chunks. Limit: 12)
    # Docs count = 3. limit_per_doc = 12 // 3 = 4
    # Doc 0 (10 chunks) -> step 9/3=3 -> 0, 3, 6, 9
    # Doc 1 (100 chunks) -> step 99/3=33 -> 0, 33, 66, 99
    # Doc 2 (5 chunks) -> step 4/3=1.33 -> 0, 1, 3, 4
    results = get_representative_chunks(uuid.UUID(FAKE_USER), uuid.UUID(FAKE_WS), None, limit=12)
    
    assert len(results) == 12
    # Verify the first 4 are from doc_0, next 4 from doc_1, last 4 from doc_2
    docs = [str(r.document_id) for r in results]
    doc_0_id = make_uuid("doc_0")
    doc_1_id = make_uuid("doc_1")
    doc_2_id = make_uuid("doc_2")
    
    assert docs[0:4] == [doc_0_id] * 4
    assert docs[4:8] == [doc_1_id] * 4
    assert docs[8:12] == [doc_2_id] * 4
    
    # Verify indices
    idx_0 = [get_idx(r.chunk_id, doc_0_id) for r in results[0:4]]
    assert idx_0 == [0, 3, 6, 9]
    
    idx_1 = [get_idx(r.chunk_id, doc_1_id) for r in results[4:8]]
    assert idx_1 == [0, 33, 66, 99]
    
    idx_2 = [get_idx(r.chunk_id, doc_2_id) for r in results[8:12]]
    assert idx_2 == [0, 1, 3, 4]
