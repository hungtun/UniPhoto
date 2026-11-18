import threading
from typing import Dict, Any

_CANCEL_EVENT = threading.Event()

_PROGRESS_STATE: Dict[str, Any] = {
    "phase": "idle",  # "idle" | "scanning" | "clustering" | "aesthetic_scoring" | "cancelled" | "done"
    "current": 0,
    "total": 0,
    "percent": 0,
    "current_file": "",
    "new_added": 0,
    "exact_duplicates": 0,
    "already_indexed": 0,
    "cancel_requested": False,
}


def reset_cancel() -> None:
    _CANCEL_EVENT.clear()
    _PROGRESS_STATE["cancel_requested"] = False


def request_cancel() -> None:
    _CANCEL_EVENT.set()
    _PROGRESS_STATE["cancel_requested"] = True


def is_cancel_requested() -> bool:
    return _CANCEL_EVENT.is_set()


def update_progress(
    phase: str,
    current: int,
    total: int,
    current_file: str = "",
    new_added: int = 0,
    exact_duplicates: int = 0,
    already_indexed: int = 0,
) -> None:
    percent = int(round((current / total) * 100)) if total > 0 else 0
    _PROGRESS_STATE.update(
        {
            "phase": phase,
            "current": current,
            "total": total,
            "percent": min(percent, 100),
            "current_file": current_file,
            "new_added": new_added,
            "exact_duplicates": exact_duplicates,
            "already_indexed": already_indexed,
            "cancel_requested": is_cancel_requested(),
        }
    )


def get_progress() -> Dict[str, Any]:
    return dict(_PROGRESS_STATE)
