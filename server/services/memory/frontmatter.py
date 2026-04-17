from datetime import date
import frontmatter

def load_page(path):
    try:
        return frontmatter.load(path)
    except FileNotFoundError:
        return None

def write_page(path, meta: dict, body: str):
    post = frontmatter.Post(body, **meta)
    with open(path, "w", encoding="utf-8") as f:
        f.write(frontmatter.dumps(post))
        f.write("\n")

def stamp(meta: dict) -> dict:
    meta = dict(meta or {})
    meta["last_updated"] = date.today().isoformat()
    return meta
