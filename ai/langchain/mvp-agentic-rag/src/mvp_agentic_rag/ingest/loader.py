from pathlib import Path

SUPPORTED = {".md", ".txt"}


def load_documents(directory: str) -> list[dict]:
    """读目录下 .md/.txt,返回 [{doc_id, text}]。doc_id = 相对文件名。"""
    base = Path(directory)
    docs: list[dict] = []
    for path in sorted(base.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED:
            docs.append(
                {
                    "doc_id": str(path.relative_to(base)),
                    "text": path.read_text(encoding="utf-8"),
                }
            )
    return docs
