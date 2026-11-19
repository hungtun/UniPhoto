#!/usr/bin/env python3
"""Synchronize and verify UniPhoto semantic versions across all 6 release-bearing files.

Usage:
  .venv/bin/python scripts/bump_version.py --check [--root <dir>]
  .venv/bin/python scripts/bump_version.py <new_version> [--root <dir>]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$", flags=re.ASCII)

VERSIONED_REL_PATHS: tuple[str, ...] = (
    "app/core/config.py",
    "frontend/package.json",
    "frontend/src-tauri/Cargo.toml",
    "frontend/src-tauri/tauri.conf.json",
    "frontend/src/utils/updater.ts",
    "website/script.js",
)


class VersionSyncError(RuntimeError):
    """Raised when a version file is missing, malformed, or out of sync."""


def normalize_semver(raw: str) -> str:
    """Validate and normalize 'X.Y.Z' or 'vX.Y.Z' into strict 'X.Y.Z'."""
    cleaned = raw.strip()
    if cleaned.startswith("v"):
        cleaned = cleaned[1:]
    if not SEMVER_RE.fullmatch(cleaned):
        raise ValueError(
            f"Invalid semantic version '{raw}': expected strict MAJOR.MINOR.PATCH (e.g. 0.2.0 or v0.2.0)."
        )
    return cleaned


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise VersionSyncError(f"Missing file: {path}")
    return path.read_text(encoding="utf-8")


def _extract_config_py_version(content: str) -> str:
    matches = list(re.finditer(r'(?m)^(\s*VERSION\s*:\s*str\s*=\s*")([^"]+)(")', content))
    if len(matches) != 1:
        raise VersionSyncError(
            f"app/core/config.py: expected exactly 1 'VERSION: str = \"...\"' line, found {len(matches)}"
        )
    return matches[0].group(2)


def _update_config_py_version(content: str, new_version: str) -> str:
    _extract_config_py_version(content)
    updated, count = re.subn(
        r'(?m)^(\s*VERSION\s*:\s*str\s*=\s*")([^"]+)(")',
        rf"\g<1>{new_version}\g<3>",
        content,
        count=1,
    )
    if count != 1:
        raise VersionSyncError("app/core/config.py: failed to update VERSION")
    return updated


def _extract_json_version(content: str, rel_label: str) -> str:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise VersionSyncError(f"{rel_label}: invalid JSON ({exc})") from exc
    version = payload.get("version")
    if not isinstance(version, str) or not version.strip():
        raise VersionSyncError(f"{rel_label}: missing string top-level 'version' field")
    return version


def _update_json_version(content: str, new_version: str, rel_label: str) -> str:
    original_payload = json.loads(content)
    if "version" not in original_payload or not isinstance(original_payload["version"], str):
        raise VersionSyncError(f"{rel_label}: missing top-level 'version' key")

    updated, count = re.subn(
        r'(?m)^(\s*"version"\s*:\s*")([^"]+)(")',
        rf"\g<1>{new_version}\g<3>",
        content,
        count=1,
    )
    if count != 1:
        raise VersionSyncError(f"{rel_label}: failed to update top-level 'version' line")

    updated_payload = json.loads(updated)
    expected_payload = dict(original_payload)
    expected_payload["version"] = new_version
    if updated_payload != expected_payload:
        raise VersionSyncError(f"{rel_label}: JSON structure changed unexpectedly during update")
    return updated


def _scan_cargo_package_version(content: str) -> tuple[list[str], int, re.Match[str]]:
    lines = content.splitlines(keepends=True)
    section_re = re.compile(r"^\s*\[([^\]]+)\]\s*(?:#.*)?$")
    version_re = re.compile(r'^(\s*version\s*=\s*")([^"]+)("(?:\s*#.*)?\r?\n?)$')

    in_package = False
    found_package = False
    matches: list[tuple[int, re.Match[str]]] = []

    for idx, line in enumerate(lines):
        sec_match = section_re.match(line)
        if sec_match:
            in_package = sec_match.group(1).strip() == "package"
            if in_package:
                found_package = True
            continue
        if in_package:
            ver_match = version_re.match(line)
            if ver_match:
                matches.append((idx, ver_match))

    if not found_package:
        raise VersionSyncError("frontend/src-tauri/Cargo.toml: missing [package] section")
    if len(matches) != 1:
        raise VersionSyncError(
            "frontend/src-tauri/Cargo.toml: expected exactly 1 'version = \"...\"' inside [package], "
            f"found {len(matches)}"
        )
    line_idx, ver_match = matches[0]
    return lines, line_idx, ver_match


def _extract_cargo_toml_version(content: str) -> str:
    _, _, ver_match = _scan_cargo_package_version(content)
    return ver_match.group(2)


def _update_cargo_toml_version(content: str, new_version: str) -> str:
    lines, line_idx, ver_match = _scan_cargo_package_version(content)
    lines[line_idx] = f"{ver_match.group(1)}{new_version}{ver_match.group(3)}"
    return "".join(lines)


def _extract_updater_ts_version(content: str) -> str:
    matches = list(
        re.finditer(
            r'(?m)^(\s*export\s+const\s+FALLBACK_APP_VERSION\s*=\s*")([^"]+)("(?:\s*;.*)?)',
            content,
        )
    )
    if len(matches) != 1:
        raise VersionSyncError(
            "frontend/src/utils/updater.ts: expected exactly 1 "
            f"'export const FALLBACK_APP_VERSION = \"...\";' line, found {len(matches)}"
        )
    return matches[0].group(2)


def _update_updater_ts_version(content: str, new_version: str) -> str:
    _extract_updater_ts_version(content)
    updated, count = re.subn(
        r'(?m)^(\s*export\s+const\s+FALLBACK_APP_VERSION\s*=\s*")([^"]+)(")',
        rf"\g<1>{new_version}\g<3>",
        content,
        count=1,
    )
    if count != 1:
        raise VersionSyncError(
            "frontend/src/utils/updater.ts: failed to update FALLBACK_APP_VERSION"
        )
    return updated


def _locate_site_config(content: str) -> re.Match[str]:
    match = re.search(
        r"(const\s+SITE_CONFIG\s*=\s*\{)(.*?)(\r?\n\};)",
        content,
        flags=re.DOTALL,
    )
    if not match:
        raise VersionSyncError("website/script.js: missing 'const SITE_CONFIG = { ... };' block")
    return match


def _extract_website_script_version(content: str) -> str:
    cfg_match = _locate_site_config(content)
    body = cfg_match.group(2)

    ver_m = re.search(r'\bversion\s*:\s*"([^"]+)"', body)
    dmg_m = re.search(r"UniPhoto_([^\"/\s]+)_aarch64\.dmg", body)
    zip_m = re.search(r"UniPhoto_([^\"/\s]+)_aarch64\.zip", body)
    win_m = re.search(r"UniPhoto_([^\"/\s]+)_x64-setup\.exe", body)

    if not (ver_m and dmg_m and zip_m and win_m):
        raise VersionSyncError(
            "website/script.js: SITE_CONFIG is missing version or one of the .dmg/.zip/.exe fallback URLs"
        )

    raw_tag = ver_m.group(1)
    if not raw_tag.startswith("v"):
        raise VersionSyncError(
            f"website/script.js: SITE_CONFIG.version '{raw_tag}' must start with 'v' (e.g. 'v0.1.0')"
        )
    tag_ver = raw_tag[1:]
    dmg_ver = dmg_m.group(1)
    zip_ver = zip_m.group(1)
    win_ver = win_m.group(1)

    if len({tag_ver, dmg_ver, zip_ver, win_ver}) != 1:
        raise VersionSyncError(
            "website/script.js: internal SITE_CONFIG mismatch "
            f"(version=v{tag_ver}, dmg={dmg_ver}, zip={zip_ver}, exe={win_ver})"
        )
    return tag_ver


def _update_website_script_version(content: str, new_version: str) -> str:
    cfg_match = _locate_site_config(content)
    body = cfg_match.group(2)

    replacements = (
        (r'(\bversion\s*:\s*")v?[^"]+(")', rf"\g<1>v{new_version}\g<2>"),
        (r"(UniPhoto_)[^\"/\s]+(_aarch64\.dmg)", rf"\g<1>{new_version}\g<2>"),
        (r"(UniPhoto_)[^\"/\s]+(_aarch64\.zip)", rf"\g<1>{new_version}\g<2>"),
        (r"(UniPhoto_)[^\"/\s]+(_x64-setup\.exe)", rf"\g<1>{new_version}\g<2>"),
    )
    updated_body = body
    for pattern, repl in replacements:
        updated_body, count = re.subn(pattern, repl, updated_body)
        if count < 1:
            raise VersionSyncError(
                f"website/script.js: failed to update pattern '{pattern}' inside SITE_CONFIG"
            )

    return (
        content[: cfg_match.start()]
        + cfg_match.group(1)
        + updated_body
        + cfg_match.group(3)
        + content[cfg_match.end() :]
    )


def read_all_versions(root: Path) -> tuple[dict[str, str], list[str]]:
    """Read versions from all 6 files under `root`, returning `(versions_by_rel_path, errors)`."""
    versions: dict[str, str] = {}
    errors: list[str] = []

    extractors = (
        ("app/core/config.py", _extract_config_py_version),
        (
            "frontend/package.json",
            lambda txt: _extract_json_version(txt, "frontend/package.json"),
        ),
        ("frontend/src-tauri/Cargo.toml", _extract_cargo_toml_version),
        (
            "frontend/src-tauri/tauri.conf.json",
            lambda txt: _extract_json_version(txt, "frontend/src-tauri/tauri.conf.json"),
        ),
        ("frontend/src/utils/updater.ts", _extract_updater_ts_version),
        ("website/script.js", _extract_website_script_version),
    )

    for rel_path, extractor in extractors:
        full_path = root / rel_path
        try:
            ver = extractor(_read_text(full_path))
            if not SEMVER_RE.fullmatch(ver):
                errors.append(f"{rel_path}: invalid semver '{ver}'")
            versions[rel_path] = ver
        except VersionSyncError as exc:
            errors.append(str(exc))

    return versions, errors


def check_sync(root: Path, expected_version: str | None = None) -> tuple[bool, str]:
    """Verify that all 6 files under `root` match the exact same MAJOR.MINOR.PATCH version."""
    versions, errors = read_all_versions(root)
    if errors:
        msg = "Version check failed:\n" + "\n".join(f"  - {err}" for err in errors)
        return False, msg

    unique_versions = sorted(set(versions.values()))
    if len(unique_versions) != 1:
        details = "\n".join(f"  - {rel}: {ver}" for rel, ver in versions.items())
        return (
            False,
            f"Version mismatch across files (found {', '.join(unique_versions)}):\n{details}",
        )

    synced = unique_versions[0]
    if expected_version is not None and synced != expected_version:
        return (
            False,
            f"Expected synced version '{expected_version}', but found '{synced}'.",
        )

    details = "\n".join(f"  - {rel}: {ver}" for rel, ver in versions.items())
    return True, f"All {len(VERSIONED_REL_PATHS)} version files are in sync at {synced}:\n{details}"


def _atomic_write_files(root: Path, updates: dict[str, str]) -> None:
    originals: dict[Path, str] = {}
    staged_temps: list[tuple[Path, Path, int]] = []

    try:
        for rel_path, new_content in updates.items():
            target = root / rel_path
            originals[target] = _read_text(target)
            mode = target.stat().st_mode
            fd, tmp_name = tempfile.mkstemp(
                prefix=f".{target.name}.",
                suffix=".tmp",
                dir=str(target.parent),
            )
            tmp_path = Path(tmp_name)
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                    handle.write(new_content)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.chmod(tmp_path, mode)
            except Exception:
                tmp_path.unlink(missing_ok=True)
                raise
            staged_temps.append((tmp_path, target, mode))

        replaced: list[Path] = []
        try:
            for tmp_path, target, _ in staged_temps:
                os.replace(tmp_path, target)
                replaced.append(target)
        except Exception:
            for target in replaced:
                target.write_text(originals[target], encoding="utf-8")
            raise
    finally:
        for tmp_path, _, _ in staged_temps:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)


def bump_all_versions(root: Path, raw_version: str) -> str:
    """Validate `raw_version` and atomically update all 6 version-bearing files under `root`."""
    new_version = normalize_semver(raw_version)

    updaters = (
        ("app/core/config.py", _update_config_py_version),
        (
            "frontend/package.json",
            lambda txt, ver: _update_json_version(txt, ver, "frontend/package.json"),
        ),
        ("frontend/src-tauri/Cargo.toml", _update_cargo_toml_version),
        (
            "frontend/src-tauri/tauri.conf.json",
            lambda txt, ver: _update_json_version(
                txt, ver, "frontend/src-tauri/tauri.conf.json"
            ),
        ),
        ("frontend/src/utils/updater.ts", _update_updater_ts_version),
        ("website/script.js", _update_website_script_version),
    )

    prepared_updates: dict[str, str] = {}
    for rel_path, updater in updaters:
        current_text = _read_text(root / rel_path)
        prepared_updates[rel_path] = updater(current_text, new_version)

    _atomic_write_files(root, prepared_updates)

    ok, report = check_sync(root, expected_version=new_version)
    if not ok:
        raise VersionSyncError(f"Post-bump sync verification failed:\n{report}")
    return new_version


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check or atomically bump UniPhoto's version across all 6 version-bearing files."
    )
    parser.add_argument(
        "new_version",
        nargs="?",
        help="Target semantic version (MAJOR.MINOR.PATCH, e.g. 0.2.0 or v0.2.0).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify that all 6 version-bearing files match the exact same version.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="Repository root directory (defaults to UniPhoto root).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    root = args.root.resolve()

    if args.check and args.new_version is not None:
        print("ERROR: Pass either --check or <new_version>, not both.", file=sys.stderr)
        return 2
    if not args.check and args.new_version is None:
        parser.print_usage(sys.stderr)
        print("ERROR: Specify --check or <new_version> (e.g. 0.2.0).", file=sys.stderr)
        return 2

    if args.check:
        ok, report = check_sync(root)
        stream = sys.stdout if ok else sys.stderr
        print(report, file=stream)
        return 0 if ok else 1

    try:
        new_version = bump_all_versions(root, args.new_version)
    except (ValueError, VersionSyncError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    _, report = check_sync(root, expected_version=new_version)
    print(report)
    print("")
    print(f"Next steps to publish UniPhoto v{new_version}:")
    print(f'  1. git add -A && git commit -m "chore: release v{new_version}"')
    print(f"  2. git tag v{new_version} && git push origin main v{new_version}")
    print("  3. npx vercel --prod website")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
