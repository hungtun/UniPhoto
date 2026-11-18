import asyncio
import hashlib
import json
import multiprocessing
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path


def _configure_mpl_cache_dir() -> None:
    """Configure a persistent writable cache dir for dev/frozen runs."""
    if getattr(sys, "frozen", False):
        bundle_key = hashlib.sha256(
            str(Path(getattr(sys, "_MEIPASS", sys.executable)).resolve()).encode("utf-8")
        ).hexdigest()[:10]
        mpl_dir = Path(f"/tmp/uniphoto-mpl-{bundle_key}")
        try:
            mpl_dir.mkdir(parents=True, exist_ok=True)
            os.environ["MPLCONFIGDIR"] = str(mpl_dir)
            return
        except OSError:
            pass
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/uniphoto-mpl")


_configure_mpl_cache_dir()


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def _start_parent_watchdog(parent_pid: int) -> None:
    initial_ppid = os.getppid()

    def _watch() -> None:
        while True:
            time.sleep(2.0)
            current_ppid = os.getppid()
            if current_ppid == 1:
                os._exit(0)
            if initial_ppid == parent_pid and current_ppid != parent_pid:
                os._exit(0)
            if not _is_pid_alive(parent_pid):
                os._exit(0)

    watcher = threading.Thread(
        target=_watch, name="uniphoto-parent-watchdog", daemon=True
    )
    watcher.start()


async def _asgi_request_json(
    fastapi_app,
    method: str,
    path: str,
    host: str,
    port: int,
    payload: dict | None = None,
) -> tuple[int, dict]:
    messages: list[dict] = []
    req_bytes = json.dumps(payload).encode("utf-8") if payload is not None else b""
    sent = False

    async def _receive() -> dict:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": req_bytes, "more_body": False}
        return {"type": "http.disconnect"}

    async def _send(msg: dict) -> None:
        messages.append(msg)

    headers = [(b"host", f"{host}:{port}".encode("utf-8"))]
    if payload is not None:
        headers.append((b"content-type", b"application/json"))
        headers.append((b"content-length", str(len(req_bytes)).encode("utf-8")))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 50000),
        "server": (host, port),
    }
    await fastapi_app(scope, _receive, _send)
    start_msg = next(m for m in messages if m["type"] == "http.response.start")
    body_bytes = b"".join(
        m.get("body", b"") for m in messages if m["type"] == "http.response.body"
    )
    return start_msg["status"], json.loads(body_bytes.decode("utf-8"))


async def _asgi_get_health(fastapi_app, host: str, port: int) -> tuple[int, dict]:
    return await _asgi_request_json(fastapi_app, "GET", "/api/v1/health", host, port)


def _run_e2e_test(folder_path: str) -> int:
    """Execute a full isolated ASGI scan -> cluster -> aesthetic-score pipeline inside this runtime."""
    created_temp_data_dir: str | None = None
    if not os.environ.get("UNIPHOTO_DATA_DIR", "").strip():
        created_temp_data_dir = tempfile.mkdtemp(prefix="uniphoto-e2e-")
        os.environ["UNIPHOTO_DATA_DIR"] = created_temp_data_dir

    try:
        from app.core.config import settings
        from app.core.database import engine, init_db
        from app.main import app

        host = os.environ.get("HOST", settings.HOST).strip() or settings.HOST
        port = int(os.environ.get("PORT", str(settings.PORT)))
        settings.HOST = host
        settings.PORT = port
        init_db()

        async def _pipeline() -> dict:
            st_h, health = await _asgi_request_json(app, "GET", "/api/v1/health", host, port)
            if st_h != 200:
                raise RuntimeError(f"Health failed: {st_h} {health}")

            st_s, scan_res = await _asgi_request_json(
                app, "POST", "/api/v1/scan", host, port, {"folder_path": folder_path}
            )
            if st_s != 200:
                raise RuntimeError(f"Scan failed: {st_s} {scan_res}")

            st_c, cluster_res = await _asgi_request_json(
                app, "POST", "/api/v1/cluster", host, port, {}
            )
            if st_c != 200:
                raise RuntimeError(f"Cluster failed: {st_c} {cluster_res}")

            st_a, score_res = await _asgi_request_json(
                app, "POST", "/api/v1/cluster/aesthetic-score", host, port, {}
            )
            if st_a != 200:
                raise RuntimeError(f"Aesthetic score failed: {st_a} {score_res}")

            st_d, dups = await _asgi_request_json(
                app, "GET", "/api/v1/photos/duplicates", host, port
            )
            st_cl, clusters = await _asgi_request_json(
                app, "GET", "/api/v1/photos/clusters", host, port
            )
            if st_d != 200 or st_cl != 200:
                raise RuntimeError(f"List endpoints failed: dups={st_d}, clusters={st_cl}")

            return {
                "frozen": bool(getattr(sys, "frozen", False)),
                "torch_loaded": "torch" in sys.modules,
                "scipy_loaded": "scipy" in sys.modules,
                "matplotlib_stub": bool(
                    getattr(sys.modules.get("matplotlib"), "__uniphoto_stub__", False)
                )
                if "matplotlib" in sys.modules
                else True,
                "scan": {
                    "total_found": scan_res["total_found"],
                    "new_added": scan_res["new_added"],
                    "exact_duplicates": scan_res["exact_duplicates"],
                    "errors_count": scan_res["errors_count"],
                },
                "cluster": {
                    "total_processed": cluster_res["total_processed"],
                    "clusters_created": cluster_res["clusters_created"],
                    "photos_clustered": cluster_res["photos_clustered"],
                },
                "aesthetic": {
                    "clusters_scored": score_res["clusters_scored"],
                    "photos_scored": score_res["photos_scored"],
                    "best_changed_count": score_res["best_changed_count"],
                },
                "duplicate_groups": dups["total_groups"],
                "clusters": [
                    {
                        "cluster_id": c["cluster_id"],
                        "best_file": os.path.basename(
                            next(p["file_path"] for p in c["photos"] if p["id"] == c["best_photo_id"])
                        ),
                        "photos": [
                            {
                                "file": os.path.basename(p["file_path"]),
                                "aesthetic_score": p["aesthetic_score"],
                                "quality_score": p["quality_score"],
                                "face_score": p["face_score"],
                                "tilt_angle": p["tilt_angle"],
                                "has_closed_eyes": p["has_closed_eyes"],
                                "aesthetic_tags": p["aesthetic_tags"],
                            }
                            for p in c["photos"]
                        ],
                    }
                    for c in clusters["items"]
                ],
            }

        summary = asyncio.run(_pipeline())
        engine.dispose()
        print("E2E_TEST_OK " + json.dumps(summary, ensure_ascii=False), flush=True)
        return 0
    finally:
        if created_temp_data_dir:
            shutil.rmtree(created_temp_data_dir, ignore_errors=True)


def _run_self_test() -> int:
    """Verify slim lazy FastAPI startup, /api/v1/health, pure-DCT pHash, ONNX cv2.dnn, and MediaPipe."""
    t_total0 = time.perf_counter()
    created_temp_data_dir: str | None = None

    if not os.environ.get("UNIPHOTO_DATA_DIR", "").strip():
        created_temp_data_dir = tempfile.mkdtemp(prefix="uniphoto-selftest-")
        os.environ["UNIPHOTO_DATA_DIR"] = created_temp_data_dir

    try:
        t_boot0 = time.perf_counter()
        from app.core.config import settings

        host = os.environ.get("HOST", settings.HOST).strip() or settings.HOST
        port = int(os.environ.get("PORT", str(settings.PORT)))
        settings.HOST = host
        settings.PORT = port
        os.environ["HOST"] = host
        os.environ["PORT"] = str(port)

        from app.main import app

        boot_ms = (time.perf_counter() - t_boot0) * 1000.0
        eager_heavy = [
            mod
            for mod in ("torch", "torchvision", "scipy", "matplotlib", "mediapipe", "cv2")
            if mod in sys.modules
        ]
        if eager_heavy:
            raise RuntimeError(
                f"Expected lazy ML imports on app.main startup, but found eager modules: {eager_heavy}"
            )

        # In frozen PyInstaller runtime, verify zero torch/scipy/matplotlib packages are bundled
        is_frozen = bool(getattr(sys, "frozen", False))
        if is_frozen:
            meipass = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent / "_internal"))
            for forbidden_dir in (
                "torch",
                "torchvision",
                "scipy",
                "matplotlib",
                "imagehash",
                "pywt",
                "sklearn",
            ):
                if (meipass / forbidden_dir).exists():
                    raise RuntimeError(
                        f"Excluded package directory '{forbidden_dir}' still present in {meipass}"
                    )
            for forbidden_mod in ("torch", "torchvision", "scipy", "imagehash", "pywt", "sklearn"):
                try:
                    __import__(forbidden_mod)
                    raise RuntimeError(
                        f"Excluded module '{forbidden_mod}' unexpectedly importable in frozen runtime"
                    )
                except ImportError:
                    pass

        from app.core.database import engine, init_db

        init_db()
        status_code, payload = asyncio.run(_asgi_get_health(app, host, port))
        engine.dispose()
        if status_code != 200 or payload.get("status") != "ok":
            raise RuntimeError(
                f"Health endpoint self-test failed: status={status_code}, payload={payload}"
            )

        # 1) Verify pure NumPy + Pillow 16x16 DCT pHash
        import numpy as np
        from PIL import Image
        from app.services import aesthetic_scorer, ai_engine, quality_scorer, scanner

        if not callable(scanner.scan_directory) or not callable(
            quality_scorer.evaluate_photo_quality
        ):
            raise RuntimeError("Scanner or quality_scorer entrypoints missing")

        yy, xx = np.mgrid[0:64, 0:64].astype(np.uint8)
        sample_img = Image.fromarray(np.stack([xx * 3, yy * 3, (xx + yy) * 2], axis=-1), mode="RGB")
        phash_hex = scanner.calculate_phash(sample_img)
        if not (isinstance(phash_hex, str) and len(phash_hex) == 64):
            raise RuntimeError(f"Unexpected calculate_phash output: {phash_hex!r}")

        # 2) Verify ONNX MobileNetV2 feature extractor loads and produces (1, 1280) float32 embedding
        models_env = os.environ.get("UNIPHOTO_MODELS_DIR", "").strip()
        onnx_path = ai_engine._resolve_mobilenet_onnx_path()
        if models_env and onnx_path is None:
            raise RuntimeError(
                f"mobilenet_v2.onnx not found under UNIPHOTO_MODELS_DIR={models_env}"
            )
        if onnx_path is not None:
            extractor = ai_engine.get_feature_extractor()
            if not isinstance(extractor, ai_engine.OnnxMobileNetV2Extractor):
                raise RuntimeError(
                    f"Expected OnnxMobileNetV2Extractor, got {type(extractor).__name__}"
                )
            dummy_blob = np.zeros((1, 3, 224, 224), dtype=np.float32)
            emb = extractor(dummy_blob)
            if emb.shape != (1, 1280) or emb.dtype != np.float32 or not np.all(np.isfinite(emb)):
                raise RuntimeError(
                    f"Invalid ONNX MobileNetV2 embedding output: shape={emb.shape}, dtype={emb.dtype}"
                )

        # 3) Verify MediaPipe FaceLandmarker loads face_landmarker.task via libmediapipe.dylib
        if models_env or aesthetic_scorer._resolve_face_task_path() is not None:
            if models_env and aesthetic_scorer._resolve_face_task_path() is None:
                raise RuntimeError(
                    f"face_landmarker.task not found under UNIPHOTO_MODELS_DIR={models_env}"
                )
            landmarker = aesthetic_scorer._get_face_landmarker()
            if landmarker is None:
                raise RuntimeError(
                    "Failed to initialize MediaPipe FaceLandmarker from bundled task asset"
                )
            try:
                landmarker.close()
            except Exception:
                pass
            aesthetic_scorer._FACE_LANDMARKER = None
            aesthetic_scorer._LANDMARKER_INITIALIZED = False

        # Ensure zero torch/scipy imported during full AI & aesthetic self-test
        unexpected_loaded = [m for m in ("torch", "torchvision", "scipy") if m in sys.modules]
        if unexpected_loaded:
            raise RuntimeError(
                f"Slim backend self-test unexpectedly imported heavy modules: {unexpected_loaded}"
            )
        if is_frozen and "matplotlib" in sys.modules:
            if not getattr(sys.modules["matplotlib"], "__uniphoto_stub__", False):
                raise RuntimeError("Real matplotlib loaded in frozen runtime instead of lightweight stub")

        total_ms = (time.perf_counter() - t_total0) * 1000.0
        print(
            f"APP_IMPORT_OK boot_ms={boot_ms:.1f} total_ms={total_ms:.1f}",
            flush=True,
        )
        print("SELF_TEST_OK", flush=True)
        return 0
    finally:
        if created_temp_data_dir:
            shutil.rmtree(created_temp_data_dir, ignore_errors=True)


def main() -> None:
    if "--self-test" in sys.argv[1:]:
        raise SystemExit(_run_self_test())
    if "--e2e-test" in sys.argv[1:]:
        idx = sys.argv.index("--e2e-test")
        if idx + 1 >= len(sys.argv):
            raise SystemExit("ERROR: --e2e-test requires a folder_path argument")
        raise SystemExit(_run_e2e_test(sys.argv[idx + 1]))

    import uvicorn
    from app.core.config import settings

    host = os.environ.get("HOST", settings.HOST).strip() or settings.HOST
    port = int(os.environ.get("PORT", str(settings.PORT)))
    settings.HOST = host
    settings.PORT = port
    os.environ["HOST"] = host
    os.environ["PORT"] = str(port)

    raw_parent_pid = os.environ.get("UNIPHOTO_PARENT_PID", "").strip()
    if raw_parent_pid:
        try:
            parsed_parent_pid = int(raw_parent_pid)
            if parsed_parent_pid > 0:
                _start_parent_watchdog(parsed_parent_pid)
        except ValueError:
            pass

    packaged_mode = (
        bool(getattr(sys, "frozen", False))
        or not settings.DEBUG
        or os.environ.get("UNIPHOTO_PACKAGED", "").strip() == "1"
    )

    print(f"Starting server at http://{host}:{port}", flush=True)
    print(
        f"Swagger API Docs: http://{host}:{port}{settings.API_V1_STR}/docs",
        flush=True,
    )

    if packaged_mode:
        from app.main import app

        uvicorn.run(
            app,
            host=host,
            port=port,
            reload=False,
            log_level="warning",
        )
    else:
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            reload=True,
        )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
