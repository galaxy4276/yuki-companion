from pathlib import Path
from core.logging import logger
from services.memory.frontmatter import load_page, write_page, stamp

class WikiStore:
    def __init__(self, root_dir):
        self.root = Path(root_dir)
        self.index_file = self.root / "index.md"
        self.log_file = self.root / "log.md"
        self._index = None  # sqlite-vec WikiIndex, set via set_index

    def bootstrap(self):
        try:
            for sub in ("concepts", "entities", "comparisons"):
                (self.root / sub).mkdir(parents=True, exist_ok=True)
            if not self.index_file.exists():
                self.index_file.write_text("---\ntitle: Wiki Index\n---\n\n# Wiki Index\n", encoding="utf-8")
            if not self.log_file.exists():
                self.log_file.write_text("", encoding="utf-8")
        except Exception as e:
            logger.warning(f"[WikiStore] bootstrap failed: {e}")

    def set_index(self, idx):
        self._index = idx

    def read_index(self) -> str:
        try:
            post = load_page(self.index_file)
            return post.content if post else ""
        except Exception as e:
            logger.warning(f"[WikiStore] read_index failed: {e}")
            return ""

    def append_log(self, line: str):
        try:
            from datetime import datetime
            ts = datetime.now().isoformat(timespec="seconds")
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"{ts} — {line}\n")
        except Exception as e:
            logger.warning(f"[WikiStore] append_log failed: {e}")

    def _page_path(self, page_type: str, name: str) -> Path:
        safe = name.replace("/", "_").replace(" ", "_")
        return self.root / page_type / f"{safe}.md"

    def load_page(self, page_type: str, name: str):
        try:
            return load_page(self._page_path(page_type, name))
        except Exception as e:
            logger.warning(f"[WikiStore] load_page failed: {e}")
            return None

    def write_page(self, page_type: str, name: str, meta: dict, body: str):
        try:
            path = self._page_path(page_type, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            meta = stamp({**meta, "type": meta.get("type", page_type), "title": meta.get("title", name)})
            write_page(path, meta, body)
            if self._index:
                try:
                    self._index.upsert(str(path))
                except Exception as e:
                    logger.warning(f"[WikiStore] index upsert failed: {e}")
            return str(path)
        except Exception as e:
            logger.warning(f"[WikiStore] write_page failed: {e}")
            return ""

    def update_page_section(self, page_type: str, name: str, section: str, content: str):
        try:
            path = self._page_path(page_type, name)
            post = load_page(path)
            if post is None:
                return self.write_page(page_type, name, {}, f"## {section}\n{content}\n")
            body = post.content
            marker = f"## {section}"
            if marker in body:
                lines = body.splitlines()
                out, skip = [], False
                for ln in lines:
                    if ln.strip().startswith("## "):
                        if ln.strip() == marker:
                            skip = True
                            out.append(ln)
                            out.append(content)
                            continue
                        skip = False
                    if not skip:
                        out.append(ln)
                new_body = "\n".join(out)
            else:
                new_body = body.rstrip() + f"\n\n## {section}\n{content}\n"
            post.metadata = stamp(post.metadata)
            import frontmatter as _fm
            new_post = _fm.Post(new_body, **post.metadata)
            with open(path, "w", encoding="utf-8") as f:
                f.write(_fm.dumps(new_post))
                f.write("\n")
            if self._index:
                try:
                    self._index.upsert(str(path))
                except Exception as e:
                    logger.warning(f"[WikiStore] index upsert failed: {e}")
            return str(path)
        except Exception as e:
            logger.warning(f"[WikiStore] update_page_section failed: {e}")
            return ""

    def list_pages(self, page_type=None) -> list[dict]:
        try:
            types = [page_type] if page_type else ["concepts", "entities", "comparisons"]
            out = []
            for t in types:
                d = self.root / t
                if not d.exists():
                    continue
                for f in d.glob("*.md"):
                    post = load_page(f)
                    if post:
                        out.append({"path": str(f), "type": t, "name": f.stem, **post.metadata})
            return out
        except Exception as e:
            logger.warning(f"[WikiStore] list_pages failed: {e}")
            return []

    def update_index(self):
        try:
            pages = self.list_pages()
            lines = ["---", "title: Wiki Index", "---", "", "# Wiki Index", ""]
            by_type = {}
            for p in pages:
                by_type.setdefault(p["type"], []).append(p)
            for t in sorted(by_type):
                lines.append(f"## {t}")
                for p in sorted(by_type[t], key=lambda x: x["name"]):
                    title = p.get("title", p["name"])
                    lines.append(f"- [[{p['name']}]] — {title}")
                lines.append("")
            self.index_file.write_text("\n".join(lines), encoding="utf-8")
        except Exception as e:
            logger.warning(f"[WikiStore] update_index failed: {e}")
