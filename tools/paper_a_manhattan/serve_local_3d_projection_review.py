"""Serve one M15.19.x local 3D review from the repository root.

The server is read-only, binds only to 127.0.0.1, and never connects to Label
Studio or writes annotation data.  It exists solely to make repository-root
viewer and texture URLs available to a local browser.
"""

from __future__ import annotations

import argparse
import functools
import json
import sys
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote


REPO_ROOT = Path(__file__).resolve().parents[2]


def _within(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{resolved} is outside repository root {root.resolve()}") from exc
    return resolved


def build_server(
    *, repo_root: Path, host: str = "127.0.0.1", port: int = 8765
) -> ThreadingHTTPServer:
    if host != "127.0.0.1":
        raise ValueError("local 3D review server must bind to 127.0.0.1")
    root = repo_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"repository root does not exist: {root}")
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(root))
    return ThreadingHTTPServer((host, port), handler)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open-browser", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.repo_root.resolve()
    review = _within(args.review if args.review.is_absolute() else root / args.review, root)
    if not review.is_file():
        raise FileNotFoundError(f"review HTML does not exist: {review}")
    server = build_server(repo_root=root, host=args.host, port=args.port)
    host, port = server.server_address
    relative_review = review.relative_to(root).as_posix()
    url = f"http://{host}:{port}/{quote(relative_review, safe='/')}"
    print(
        json.dumps(
            {
                "url": url,
                "review": relative_review,
                "repo_root": str(root),
                "read_only": True,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )
    if not args.no_open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
