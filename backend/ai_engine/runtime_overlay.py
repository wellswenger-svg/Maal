"""Load gitignored runtime overlays from ``private/`` (never committed).

Explicit prompts, labels, and weight filenames live there. Tracked code only
references generic orchestration.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
PRIVATE_DIR = REPO_ROOT / "private"
_SECRETS_DIR = Path("/etc/secrets")


def private_dir() -> Path:
    return PRIVATE_DIR


def overlay_search_dirs() -> list[Path]:
    """Places overlays can live: gitignored private/, Render secret files, cwd."""
    dirs = [
        PRIVATE_DIR,
        _SECRETS_DIR,
        Path.cwd() / "private",
        Path.cwd(),
        REPO_ROOT,
    ]
    seen: set[str] = set()
    out: list[Path] = []
    for d in dirs:
        try:
            key = str(d.resolve())
        except OSError:
            key = str(d)
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


def _ensure_private_copies() -> None:
    """Copy Render secret files into ``private/`` so overlay imports stay stable."""
    if not _SECRETS_DIR.is_dir():
        return
    try:
        PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    for src in _SECRETS_DIR.iterdir():
        if src.suffix not in {".py", ".json"} or not src.is_file():
            continue
        dest = PRIVATE_DIR / src.name
        try:
            if not dest.is_file() or dest.stat().st_mtime < src.stat().st_mtime:
                shutil.copy2(src, dest)
        except OSError:
            continue


def _find_overlay_file(filename: str) -> Optional[Path]:
    _ensure_private_copies()
    for folder in overlay_search_dirs():
        path = folder / filename
        if path.is_file():
            return path
    return None


def load_json(name: str, default: Any = None) -> Any:
    path = _find_overlay_file(name)
    if path is None:
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def load_private_module(name: str) -> Optional[Any]:
    """Load ``private/<name>.py`` (or Render ``/etc/secrets/<name>.py``)."""
    path = _find_overlay_file(f"{name}.py")
    if path is None:
        return None
    mod_name = f"wan_private_{name}"
    existing = sys.modules.get(mod_name)
    if existing is not None and getattr(existing, "__wan_overlay_ready__", False):
        return existing
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    # Dataclass overlays need the module in sys.modules during exec.
    sys.modules[mod_name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(mod_name, None)
        return None
    mod.__wan_overlay_ready__ = True
    return mod


def overlay_status() -> dict[str, bool]:
    """Cheap health bits: files present, not fully imported."""
    return {
        "edit_runner": _find_overlay_file("edit_runner.py") is not None,
        "planner_rules": _find_overlay_file("planner_rules.py") is not None,
        "presets": _find_overlay_file("presets.json") is not None,
    }


def export_private(name: str, dest: dict[str, Any], names: tuple[str, ...]) -> bool:
    mod = load_private_module(name)
    if mod is None:
        return False
    for key in names:
        if hasattr(mod, key):
            dest[key] = getattr(mod, key)
    return True


def bind_module(name: str, dest: dict[str, Any]) -> bool:
    """Copy all public names from ``private/<name>.py`` into ``dest`` (usually globals())."""
    mod = load_private_module(name)
    if mod is None or not getattr(mod, "__wan_overlay_ready__", False):
        return False
    for key, val in vars(mod).items():
        if key.startswith("__") and key.endswith("__"):
            continue
        dest[key] = val
    return True


def attach_private_tests(dest: dict[str, Any], filename: str) -> None:
    """Copy Test* classes from ``private/tests/<filename>`` into a test module."""
    path = PRIVATE_DIR / "tests" / filename
    if not path.is_file():
        return
    mod_name = f"wan_private_tests_{path.stem}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        return
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    for key, val in vars(mod).items():
        if isinstance(val, type) and key.startswith("Test"):
            dest[key] = val
