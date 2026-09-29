#!/usr/bin/env python3
"""
scripts/doctor.py — SatQuery AI preflight / environment check
Usage: python scripts/doctor.py [--host | --container] [--network]

Checks:
  - Execution context: Host (localhost:5432, localhost:6379) vs Container (postgis:5432, redis:6379)
  - Python version & required dependencies with actionable installation instructions
  - PostgreSQL / PostGIS connectivity using appropriate endpoints
  - Redis connectivity using appropriate endpoints
  - Writable data / cache / index / report paths
  - Available disk space vs FREE_DISK_RESERVE_GB
  - Available RAM
  - CUDA device availability and VRAM
  - Model file existence and SHA-256 hash verification
  - External service credentials:
      * Record credential presence separately from authentication success
      * Distinguish Sentinel Hub OAuth (sh-*) from CDSE OData download entitlement (ADR-009)
      * Groq API key presence
      * HuggingFace token presence
      * MapTiler key presence
  - Optional provider reachability (when --network is provided):
      * STAC / OData catalog discovery reachability (anonymous/public)
      * Sentinel Hub token authentication (OAuth2 exchange)

Output is human-readable plain text. Secrets are REDACTED in all output.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

REQUIRED_PYTHON = (3, 11)
if sys.version_info < REQUIRED_PYTHON:
    print(f"FAIL  Python >= {'.'.join(map(str, REQUIRED_PYTHON))} required; found {sys.version}")
    sys.exit(1)


def is_container_environment() -> bool:
    """Detect if running inside a Docker/OCI container."""
    if Path("/.dockerenv").exists():
        return True
    if os.environ.get("CONTAINER") == "true" or os.environ.get("DOCKER_CONTAINER") == "true":
        return True
    try:
        with open("/proc/1/cgroup", "rt") as f:
            content = f.read()
            if "docker" in content or "containerd" in content or "kubepods" in content:
                return True
    except Exception:
        pass
    return False


def _redact(value: str | None, keep: int = 4) -> str:
    """Redact a secret value, showing only the first `keep` chars."""
    if not value:
        return "<not set>"
    val = value.strip().strip('"').strip("'")
    if len(val) <= keep:
        return "***"
    return val[:keep] + "***"


def _check(label: str, passed: bool, detail: str = "", warn: bool = False) -> bool:
    status = "OK   " if passed else ("WARN " if warn else "FAIL ")
    msg = f"{status} {label}"
    if detail:
        msg += f": {detail}"
    print(msg)
    return passed


def _section(title: str) -> None:
    print(f"\n{'=' * 65}")
    print(f"  {title}")
    print("=" * 65)


def load_settings() -> Any | None:
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
        from app.core.settings import settings  # type: ignore
        return settings
    except Exception as e:
        print(f"WARN  Could not load backend.app.core.settings: {e}")
        return None


REQUIRED_PACKAGES = [
    "fastapi", "pydantic", "sqlalchemy", "alembic",
    "redis", "celery", "rasterio", "shapely", "pyproj",
    "numpy", "cv2", "torch", "faiss",
]
OPTIONAL_PACKAGES = [
    "open_clip", "groq", "boto3", "psutil"
]


def check_packages() -> tuple[bool, list[str]]:
    _section("1. Python packages")
    all_ok = True
    missing_required: list[str] = []

    for pkg in REQUIRED_PACKAGES:
        try:
            mod = importlib.import_module(pkg)
            ver = getattr(mod, "__version__", "unknown")
            _check(f"package {pkg}", True, ver)
        except ImportError:
            _check(f"package {pkg}", False, "NOT INSTALLED")
            missing_required.append(pkg)
            all_ok = False

    for pkg in OPTIONAL_PACKAGES:
        try:
            mod = importlib.import_module(pkg)
            ver = getattr(mod, "__version__", "unknown")
            _check(f"package {pkg} (optional)", True, ver)
        except ImportError:
            _check(f"package {pkg} (optional)", True, "not installed (optional)", warn=True)

    if missing_required:
        print("\n--> Action required to install missing packages:")
        print(f"    pip install -r backend/requirements.txt")

    return all_ok, missing_required


def check_database(settings: Any, is_container: bool) -> bool:
    _section(f"2. Database (PostgreSQL / PostGIS) — [{'CONTAINER' if is_container else 'HOST'}]")
    try:
        import asyncio
        import sqlalchemy as sa
        from sqlalchemy.ext.asyncio import create_async_engine

        raw_url = getattr(settings, "database_url", os.environ.get("DATABASE_URL", ""))
        if not raw_url:
            user = os.environ.get("POSTGRES_USER", "postgres")
            pwd = os.environ.get("POSTGRES_PASSWORD", "postgres")
            db = os.environ.get("POSTGRES_DB", "satquery")
            host = "postgis" if is_container else "localhost"
            raw_url = f"postgresql+asyncpg://{user}:{pwd}@{host}:5432/{db}"

        # Adjust host for host execution if user provided container URL
        target_url = raw_url
        if not is_container and "@postgis:5432" in raw_url:
            target_url = raw_url.replace("@postgis:5432", "@localhost:5432")
            print(f"INFO  Host execution detected: mapped postgis:5432 -> localhost:5432")
        elif is_container and "@localhost:5432" in raw_url:
            target_url = raw_url.replace("@localhost:5432", "@postgis:5432")
            print(f"INFO  Container execution detected: mapped localhost:5432 -> postgis:5432")

        display_url = re.sub(r":([^@]+)@", r":***@", target_url)
        print(f"INFO  Target connection: {display_url}")

        async def _ping() -> str:
            engine = create_async_engine(target_url, pool_pre_ping=True, pool_size=1, connect_args={"timeout": 5})
            async with engine.connect() as conn:
                row = await conn.execute(sa.text("SELECT PostGIS_Version()"))
                version = row.scalar()
            await engine.dispose()
            return str(version)

        start = time.time()
        version = asyncio.run(_ping())
        elapsed = time.time() - start
        _check("PostgreSQL connection", True, f"PostGIS {version} ({elapsed:.2f}s)")
        return True
    except Exception as e:
        err_msg = str(e).strip()[:140]
        _check("PostgreSQL connection", False, err_msg)
        if not is_container:
            print("--> Troubleshooting: Ensure PostGIS container is running and port 5432 is published:")
            print("    docker compose up postgis -d")
        else:
            print("--> Troubleshooting: Ensure postgis service is healthy in compose network:")
            print("    docker compose ps postgis")
        return False


def check_redis(settings: Any, is_container: bool) -> bool:
    _section(f"3. Redis — [{'CONTAINER' if is_container else 'HOST'}]")
    try:
        import redis as redis_lib

        raw_url = getattr(settings, "redis_url", os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
        target_url = raw_url
        if not is_container and "redis:6379" in raw_url:
            target_url = raw_url.replace("redis:6379", "localhost:6379")
            print(f"INFO  Host execution detected: mapped redis:6379 -> localhost:6379")
        elif is_container and "localhost:6379" in raw_url:
            target_url = raw_url.replace("localhost:6379", "redis:6379")
            print(f"INFO  Container execution detected: mapped localhost:6379 -> redis:6379")

        client = redis_lib.from_url(target_url, socket_connect_timeout=3)
        start = time.time()
        pong = client.ping()
        elapsed = time.time() - start
        _check("Redis connection", bool(pong), f"PONG ({elapsed:.2f}s)")
        return bool(pong)
    except Exception as e:
        err_msg = str(e).strip()[:140]
        _check("Redis connection", False, err_msg)
        if not is_container:
            print("--> Troubleshooting: Ensure Redis container is running and port 6379 is published:")
            print("    docker compose up redis -d")
        else:
            print("--> Troubleshooting: Ensure redis service is healthy in compose network:")
            print("    docker compose ps redis")
        return False


def check_paths(settings: Any) -> bool:
    _section("4. Writable paths")
    paths = {
        "DATA_PATH": getattr(settings, "data_path", "./data"),
        "CACHE_PATH": getattr(settings, "cache_path", "./data/cache"),
        "INDEX_PATH": getattr(settings, "index_path", "./indexes"),
        "REPORT_PATH": getattr(settings, "report_path", "./reports"),
    }
    all_ok = True
    for name, path_str in paths.items():
        path = Path(path_str)
        try:
            path.mkdir(parents=True, exist_ok=True)
            test_file = path / ".write_test"
            test_file.write_text("ok")
            test_file.unlink()
            _check(f"{name} writable", True, str(path.resolve()))
        except Exception as e:
            _check(f"{name} writable", False, str(e)[:80])
            all_ok = False
    return all_ok


def check_disk_and_ram(settings: Any) -> bool:
    _section("5. Resources (Disk & RAM)")
    data_path = Path(getattr(settings, "data_path", "./data"))
    reserve_gb = getattr(settings, "free_disk_reserve_gb", 5.0)
    budget_gb = getattr(settings, "storage_budget_gb", 50.0)
    try:
        target = data_path if data_path.exists() else Path.cwd()
        usage = shutil.disk_usage(target)
        free_gb = usage.free / 1e9
        total_gb = usage.total / 1e9
        ok = free_gb >= reserve_gb
        _check(
            "Free disk space",
            ok,
            f"{free_gb:.1f} GB free of {total_gb:.1f} GB (reserve: {reserve_gb} GB, budget: {budget_gb} GB)",
            warn=not ok,
        )
    except Exception as e:
        _check("Disk space check", False, str(e))

    try:
        import psutil
        mem = psutil.virtual_memory()
        total_gb = mem.total / 1e9
        available_gb = mem.available / 1e9
        _check("System RAM", True, f"{available_gb:.1f} GB available of {total_gb:.1f} GB total")
    except ImportError:
        _check("System RAM", True, "psutil not installed (skipped detail)", warn=True)
    return True


def check_device(settings: Any) -> bool:
    _section("6. Compute device")
    configured = getattr(settings, "device", "cpu")
    try:
        import torch
        if torch.cuda.is_available():
            n = torch.cuda.device_count()
            for i in range(n):
                props = torch.cuda.get_device_properties(i)
                vram_gb = props.total_memory / 1e9
                _check(f"CUDA device {i}", True, f"{props.name}, {vram_gb:.1f} GB VRAM")
            if configured == "cuda":
                _check("Configured DEVICE=cuda", True, "active")
            else:
                _check("Configured DEVICE=cpu", True, f"CUDA available but DEVICE={configured}", warn=True)
        else:
            _check("CUDA acceleration", False, "not available (CPU inference active)", warn=True)
            if configured == "cuda":
                _check("Configured DEVICE=cuda", False, "CUDA not available; set DEVICE=cpu in .env")
                return False
    except ImportError:
        _check("PyTorch", False, "not installed (run: pip install -r backend/requirements.txt)")
        return False
    return True


def check_models(settings: Any) -> bool:
    _section("7. ML model files")
    models = [
        ("RemoteCLIP", getattr(settings, "remoteclip_model_path", "./models/remoteclip/RemoteCLIP-ViT-L-14.pt"), getattr(settings, "remoteclip_sha256", None)),
        ("ChangeFormer", getattr(settings, "changeformer_checkpoint_path", "./models/changeformer/ChangeFormer_LEVIR.pth"), getattr(settings, "changeformer_sha256", None)),
    ]
    for name, path_str, expected_sha in models:
        path = Path(path_str)
        if not path.exists():
            _check(f"{name} checkpoint", False, f"missing at {path} (run: python scripts/download_models.py)", warn=True)
            continue
        size_mb = path.stat().st_size / 1e6
        if expected_sha:
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            actual_sha = h.hexdigest()
            ok = actual_sha == expected_sha
            _check(f"{name} SHA-256", ok, f"{'match' if ok else 'MISMATCH'} ({size_mb:.1f} MB)")
        else:
            _check(f"{name} checkpoint", True, f"present ({size_mb:.1f} MB); hash unpinned")
    return True


def check_credentials(settings: Any) -> None:
    """
    Check credential presence separately from authentication (ADR-009).
    Sentinel Hub client credentials (sh-*) being present does NOT prove OData downloads work.
    """
    _section("8. External credentials (presence check only — no secrets exposed)")
    s = settings

    cid = getattr(s, "copernicus_client_id", None) or os.environ.get("COPERNICUS_CLIENT_ID") or os.environ.get("Client_ID")
    csec = getattr(s, "copernicus_client_secret", None) or os.environ.get("COPERNICUS_CLIENT_SECRET") or os.environ.get("Client_secret")

    has_sh_cid = bool(cid and cid.strip().strip('"').strip("'").startswith("sh-"))
    _check("Sentinel Hub OAuth Client_ID presence", bool(cid), _redact(cid), warn=not cid)
    _check("Sentinel Hub OAuth Client_secret presence", bool(csec), _redact(csec), warn=not csec)

    if has_sh_cid:
        print("  --> [ADR-009 Notice]: Client ID has 'sh-' prefix (Sentinel Hub OAuth credentials).")
        print("      Credential presence is RECORDED. This allows Sentinel Hub Process API usage.")
        print("      It does NOT establish that CDSE OData archive downloads work.")
        print("      Catalog discovery and download authorization are distinct provider surfaces.")

    groq_key = getattr(s, "groq_api_key", None) or os.environ.get("GROQ_API_KEY")
    groq_model = getattr(s, "groq_model", "llama3-8b-8192")
    _check("Groq API key presence", bool(groq_key), _redact(groq_key), warn=not groq_key)
    _check("Groq model configured", bool(groq_model), groq_model)

    hf = getattr(s, "huggingface_token", None) or os.environ.get("HUGGINGFACE_TOKEN")
    _check("HuggingFace token presence", bool(hf), _redact(hf), warn=not hf)

    mt = getattr(s, "vite_maptiler_api_key", None) or os.environ.get("VITE_MAPTILER_API_KEY") or os.environ.get("MAPTILER_API_KEY")
    _check("MapTiler key presence", bool(mt), _redact(mt), warn=not mt)


def check_copernicus_connectivity(settings: Any, run_network: bool) -> None:
    _section("9. Copernicus Connectivity & Auth (Decoupled per ADR-009)")
    if not run_network:
        print("INFO  Network checks skipped by default. Run with --network to verify live endpoints.")
        return

    import urllib.request
    import urllib.error

    # 1. Catalog discovery reachability (anonymous/public)
    stac_url = getattr(settings, "copernicus_stac_url", "https://catalogue.dataspace.copernicus.eu/stac")
    try:
        req = urllib.request.Request(stac_url, method="HEAD")
        req.add_header("User-Agent", "SatQuery-Doctor/1.0")
        with urllib.request.urlopen(req, timeout=8) as resp:
            code = resp.status
        _check("STAC Catalog Discovery endpoint", code < 500, f"HTTP {code} ({stac_url})")
    except Exception as e:
        _check("STAC Catalog Discovery endpoint", False, f"{e} ({stac_url})", warn=True)

    # 2. Token authentication attempt
    cid = getattr(settings, "copernicus_client_id", None) or os.environ.get("COPERNICUS_CLIENT_ID") or os.environ.get("Client_ID")
    csec = getattr(settings, "copernicus_client_secret", None) or os.environ.get("COPERNICUS_CLIENT_SECRET") or os.environ.get("Client_secret")
    token_url = getattr(settings, "copernicus_token_url", "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token")

    if cid and csec:
        try:
            import urllib.parse
            data = urllib.parse.urlencode({
                "grant_type": "client_credentials",
                "client_id": cid.strip().strip('"').strip("'"),
                "client_secret": csec.strip().strip('"').strip("'"),
            }).encode("utf-8")
            req = urllib.request.Request(token_url, data=data, method="POST")
            req.add_header("User-Agent", "SatQuery-Doctor/1.0")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
            with urllib.request.urlopen(req, timeout=10) as resp:
                code = resp.status
            _check("OAuth token authentication", code == 200, f"HTTP {code} (OAuth exchange succeeded)")
        except urllib.error.HTTPError as e:
            _check("OAuth token authentication", False, f"HTTP {e.code}: {e.reason}", warn=True)
            print("  --> Note: Token endpoint returned error. Check if client credentials require Sentinel Hub realm.")
        except Exception as e:
            _check("OAuth token authentication", False, str(e)[:100], warn=True)
    else:
        _check("OAuth token authentication", False, "Skipped — credentials not provided", warn=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="SatQuery AI Preflight Doctor")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--container", action="store_true", help="Force container execution mode")
    group.add_argument("--host", action="store_true", help="Force host execution mode")
    parser.add_argument("--network", action="store_true", help="Perform live external network checks")
    args = parser.parse_args()

    if args.container:
        is_container = True
    elif args.host:
        is_container = False
    else:
        is_container = is_container_environment()

    print("\n" + "=" * 65)
    print("  SatQuery AI — Preflight Doctor (ADR-009 & ADR-012 compliant)")
    print("=" * 65)
    print(f"Execution context: [{'CONTAINER (service names)' if is_container else 'HOST (localhost ports)'}]")
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    print(f"Working directory: {Path.cwd()}")

    settings = load_settings()

    pkg_ok, missing_pkgs = check_packages()
    paths_ok = check_paths(settings) if settings else True
    disk_ok = check_disk_and_ram(settings) if settings else True
    dev_ok = check_device(settings) if settings else True

    db_ok = check_database(settings, is_container) if settings else False
    redis_ok = check_redis(settings, is_container) if settings else False

    check_models(settings) if settings else None
    check_credentials(settings) if settings else None
    check_copernicus_connectivity(settings, args.network)

    _section("Summary & Gate 0 Evaluation")
    print(f"Packages status: {'OK' if pkg_ok else 'FAIL (missing dependencies)'}")
    print(f"Paths status:    {'OK' if paths_ok else 'FAIL'}")
    print(f"PostGIS status:  {'OK' if db_ok else 'UNAVAILABLE (port 5432)'}")
    print(f"Redis status:    {'OK' if redis_ok else 'UNAVAILABLE (port 6379)'}")

    gate_0_ready = pkg_ok and db_ok and redis_ok
    if gate_0_ready:
        print("\n==> GATE 0 CRITERIA MET: PostGIS and Redis are healthy, dependencies satisfied.")
    else:
        print("\n==> GATE 0 BLOCKED: PostGIS or Redis are not reachable, or dependencies missing.")
        print("    Operator action to unblock:")
        print("    1. Install requirements: pip install -r backend/requirements.txt")
        print("    2. Start services:      docker compose up postgis redis -d")
        print("    3. Re-run doctor:       python scripts/doctor.py")

    sys.exit(0 if gate_0_ready else 1)


if __name__ == "__main__":
    main()
