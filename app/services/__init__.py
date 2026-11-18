__all__ = ["scan_directory"]


def __getattr__(name: str):
    if name == "scan_directory":
        from app.services.scanner import scan_directory

        return scan_directory
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
