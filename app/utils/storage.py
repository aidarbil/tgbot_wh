from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

UploadKind = Literal["car", "wheel", "result", "video"]

_STORAGE_ROOT = Path(__file__).resolve().parent.parent / "storage"
_USER_UPLOADS_ROOT = _STORAGE_ROOT / "user_uploads"

_FILENAMES = {
    "car": "car.jpg",
    "wheel": "wheel.jpg",
    "result": "result.jpg",
    "video": "result.mp4",
}


def _user_directory(user_id: int, ensure_exists: bool = True) -> Path:
    directory = _USER_UPLOADS_ROOT / str(user_id)
    if ensure_exists:
        directory.mkdir(parents=True, exist_ok=True)
    return directory


def build_upload_path(user_id: int, kind: UploadKind, *, ensure_dir: bool = True) -> Path:
    try:
        filename = _FILENAMES[kind]
    except KeyError as exc:
        raise ValueError(f"Unsupported upload kind: {kind}") from exc

    directory = _user_directory(user_id, ensure_exists=ensure_dir)
    return directory / filename


def read_upload_bytes(user_id: int, kind: UploadKind) -> Optional[bytes]:
    path = build_upload_path(user_id, kind, ensure_dir=False)
    if not path.exists():
        return None
    return path.read_bytes()
