"""Small local env loader for standalone scripts.

The FastAPI app uses pydantic-settings, but many scripts are intentionally
thin and read os.environ directly. Loading .env.local here keeps secrets out
of git while making scripts behave like the app.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_local_env(start: Path | None = None) -> None:
    """Load backend/.env then backend/.env.local into os.environ if present.

    Existing environment variables win. This mirrors common dotenv behavior:
    shell-provided values override local files.
    """
    root = start or Path.cwd()
    if root.name != "backend":
        for parent in [root, *root.parents]:
            if parent.name == "backend":
                root = parent
                break

    for name in (".env", ".env.local"):
        path = root / name
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)
