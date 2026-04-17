"""Wiki semantic search index using sqlite-vec + sentence-transformers."""
from __future__ import annotations
import os
import struct
from pathlib import Path
from core.logging import logger

_MODEL_NAME_DEFAULT = "paraphrase-multilingual-MiniLM-L12-v2"
_EMBED_DIM = 384  # MiniLM-L12 output dim


class WikiIndex:
    def __init__(self, db_path: str, model_name: str = _MODEL_NAME_DEFAULT):
        self.db_path = db_path
        self.model_name = model_name
        self._conn = None
        self._model = None
        self._ready = False
        try:
            self._open()
        except Exception as e:
            logger.warning(f"[WikiIndex] init failed: {e}")

    def _open(self):
        import sqlite3
        import sqlite_vec
        Path(os.path.dirname(self.db_path) or ".").mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.enable_load_extension(True)
        sqlite_vec.load(self._conn)
        self._conn.enable_load_extension(False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS pages ("
            "path TEXT PRIMARY KEY, mtime REAL, snippet TEXT)"
        )
        self._conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_pages USING vec0(embedding float[{_EMBED_DIM}])"
        )
        self._conn.commit()
        self._ready = True

    @property
    def model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"[WikiIndex] loading model {self.model_name} (first use may download ~120MB)")
                self._model = SentenceTransformer(self.model_name)
            except Exception as e:
                logger.warning(f"[WikiIndex] model load failed: {e}")
                self._model = None
        return self._model

    def _encode(self, text: str) -> bytes | None:
        m = self.model
        if m is None or not text.strip():
            return None
        try:
            vec = m.encode(text, normalize_embeddings=True)
            return struct.pack(f"{_EMBED_DIM}f", *vec.tolist())
        except Exception as e:
            logger.warning(f"[WikiIndex] encode failed: {e}")
            return None

    def upsert(self, path: str) -> bool:
        if not self._ready:
            return False
        try:
            p = Path(path)
            if not p.exists():
                return False
            mtime = p.stat().st_mtime
            row = self._conn.execute("SELECT mtime FROM pages WHERE path=?", (str(p),)).fetchone()
            if row and abs(row[0] - mtime) < 0.001:
                return False
            from services.memory.frontmatter import load_page
            post = load_page(str(p))
            body = post.content if post else p.read_text(encoding="utf-8")
            emb = self._encode(body)
            if emb is None:
                return False
            snippet = body.replace("\n", " ")[:240]
            self._conn.execute("DELETE FROM pages WHERE path=?", (str(p),))
            self._conn.execute(
                "INSERT INTO pages(path, mtime, snippet) VALUES(?,?,?)",
                (str(p), mtime, snippet),
            )
            # Get rowid from pages for vec alignment (use path hash instead — simpler: use pages.rowid)
            pages_row = self._conn.execute("SELECT rowid FROM pages WHERE path=?", (str(p),)).fetchone()
            rowid = pages_row[0]
            self._conn.execute("DELETE FROM vec_pages WHERE rowid=?", (rowid,))
            self._conn.execute("INSERT INTO vec_pages(rowid, embedding) VALUES(?,?)", (rowid, emb))
            self._conn.commit()
            return True
        except Exception as e:
            logger.warning(f"[WikiIndex] upsert {path} failed: {e}")
            return False

    def rebuild(self, root_dir: str) -> int:
        if not self._ready:
            return 0
        count = 0
        root = Path(root_dir)
        for p in root.rglob("*.md"):
            if p.name in ("index.md", "log.md"):
                continue
            if self.upsert(str(p)):
                count += 1
        return count

    def search(self, query: str, k: int = 5) -> list[tuple[str, float, str]]:
        if not self._ready:
            return []
        try:
            emb = self._encode(query)
            if emb is None:
                return []
            rows = self._conn.execute(
                "SELECT p.path, v.distance, p.snippet "
                "FROM vec_pages v JOIN pages p ON p.rowid = v.rowid "
                "WHERE v.embedding MATCH ? AND k=? "
                "ORDER BY v.distance",
                (emb, k),
            ).fetchall()
            return [(r[0], float(r[1]), r[2]) for r in rows]
        except Exception as e:
            logger.warning(f"[WikiIndex] search failed: {e}")
            return []

    def search_hybrid(self, query: str, k: int = 5,
                      vector_weight: float = 0.7, text_weight: float = 0.3) -> list[tuple[str, float, str]]:
        vec_hits = self.search(query, k=k * 2)
        q_lower = (query or "").lower()
        scored = []
        for path, dist, snippet in vec_hits:
            # vec dist is cosine distance (lower is better) — convert to similarity
            vec_sim = max(0.0, 1.0 - dist)
            text_sim = 0.0
            if q_lower and snippet:
                text_sim = snippet.lower().count(q_lower) / max(1, len(snippet.split()))
                text_sim = min(1.0, text_sim * 10)
            score = vector_weight * vec_sim + text_weight * text_sim
            scored.append((path, score, snippet))
        scored.sort(key=lambda r: r[1], reverse=True)
        return scored[:k]

    def close(self):
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
            self._ready = False
