from pathlib import Path
from util.response import Response
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DIR = PROJECT_ROOT / "public"

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
}

def _safe_public_path(url_path: str) -> Optional[Path]:

    if not url_path.startswith("/public"):
        return None

    rel = url_path[len("/public"):]  # e.g. "/imgs/dog.jpg" or "" or "/"
    if rel == "" or rel == "/":
        return None  # requesting the directory itself treat as not found

    # remove leading slash to make it a relative path
    rel = rel.lstrip("/")

    candidate = (PUBLIC_DIR / rel).resolve()

    try:
        candidate.relative_to(PUBLIC_DIR.resolve())
    except ValueError:
        return None

    return candidate

def serve_public(request, handler):
    file_path = _safe_public_path(request.path)
    if file_path is None or not file_path.is_file():
        res = Response().set_status(404, "Not Found").text("404 Not Found")
        handler.request.sendall(res.to_data())
        return

    ext = file_path.suffix.lower()
    mime = MIME_TYPES.get(ext, "application/octet-stream")

    data = file_path.read_bytes()
    res = Response().headers({"Content-Type": mime}).bytes(data)
    handler.request.sendall(res.to_data())

def render_page(page_filename: str):
    def _handler(request, handler):
        layout_path = PUBLIC_DIR / "layout" / "layout.html"
        page_path = PUBLIC_DIR / page_filename

        if not layout_path.is_file() or not page_path.is_file():
            res = Response().set_status(500, "Internal Server Error").text("Missing template files")
            handler.request.sendall(res.to_data())
            return

        layout_html = layout_path.read_text(encoding="utf-8")
        page_html = page_path.read_text(encoding="utf-8")
        full_html = layout_html.replace("{{content}}", page_html)

        res = Response().headers({"Content-Type": "text/html; charset=utf-8"}).text(full_html)
        handler.request.sendall(res.to_data())

    return _handler
