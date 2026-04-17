from pathlib import Path
from datetime import datetime, date
from core.logging import logger
from services.memory.frontmatter import load_page, write_page, stamp

class MemoryStore:
    def __init__(self, root_dir):
        self.root = Path(root_dir)
        self.memory_file = self.root / "MEMORY.md"
        self.episodes_dir = self.root / "episodes"
        self.topics_dir = self.root / "topics"
        self.archives_dir = self.root / "archives"

    def bootstrap(self):
        try:
            for d in (self.root, self.episodes_dir, self.topics_dir, self.archives_dir):
                d.mkdir(parents=True, exist_ok=True)
            if not self.memory_file.exists():
                self.memory_file.write_text("---\ntitle: Yuki Memory\ntype: memory\n---\n\n# Yuki Memory\n", encoding="utf-8")
        except Exception as e:
            logger.warning(f"[MemoryStore] bootstrap failed: {e}")

    def load_memory(self) -> str:
        try:
            post = load_page(self.memory_file)
            return post.content if post else ""
        except Exception as e:
            logger.warning(f"[MemoryStore] load failed: {e}")
            return ""

    def replace_memory(self, content: str):
        try:
            write_page(self.memory_file, stamp({"title": "Yuki Memory", "type": "memory"}), content)
        except Exception as e:
            logger.warning(f"[MemoryStore] replace failed: {e}")

    def append_memory(self, category: str, content: str):
        try:
            current = self.load_memory()
            today = date.today().isoformat()
            block = f"\n## [{category}] {today}\n{content}\n"
            self.replace_memory(current + block)
        except Exception as e:
            logger.warning(f"[MemoryStore] append failed: {e}")

    def load_recent_episode(self, k: int = 1) -> list[str]:
        try:
            if not self.episodes_dir.exists():
                return []
            files = sorted(self.episodes_dir.glob("*.md"), reverse=True)[:k]
            out = []
            for f in files:
                post = load_page(f)
                if post:
                    out.append(post.content)
            return out
        except Exception as e:
            logger.warning(f"[MemoryStore] load_recent_episode failed: {e}")
            return []

    def write_episode(self, content: str, meta: dict) -> str:
        try:
            today = date.today().isoformat()
            existing = list(self.episodes_dir.glob(f"{today}-*.md"))
            seq = len(existing) + 1
            path = self.episodes_dir / f"{today}-{seq:02d}.md"
            meta = stamp({**meta, "title": meta.get("title", f"Episode {today}-{seq:02d}")})
            write_page(path, meta, content)
            return str(path)
        except Exception as e:
            logger.warning(f"[MemoryStore] write_episode failed: {e}")
            return ""

    def load_topic(self, slug: str) -> str | None:
        try:
            p = self.topics_dir / f"{slug}.md"
            post = load_page(p)
            return post.content if post else None
        except Exception as e:
            logger.warning(f"[MemoryStore] load_topic failed: {e}")
            return None

    def write_topic(self, slug: str, content: str, meta: dict):
        try:
            p = self.topics_dir / f"{slug}.md"
            write_page(p, stamp({**meta, "title": meta.get("title", slug)}), content)
        except Exception as e:
            logger.warning(f"[MemoryStore] write_topic failed: {e}")

    def count_lines(self, path=None) -> int:
        try:
            p = Path(path) if path else self.memory_file
            return len(p.read_text(encoding="utf-8").splitlines())
        except Exception:
            return 0

    def archive(self) -> str:
        try:
            ts = datetime.now().strftime("%Y-%m-%d-%H%M")
            archive_path = self.archives_dir / f"{ts}-MEMORY.md"
            content = self.memory_file.read_text(encoding="utf-8")
            archive_path.write_text(content, encoding="utf-8")
            self.memory_file.write_text("---\ntitle: Yuki Memory\ntype: memory\n---\n\n# Yuki Memory\n", encoding="utf-8")
            return str(archive_path)
        except Exception as e:
            logger.warning(f"[MemoryStore] archive failed: {e}")
            return ""
