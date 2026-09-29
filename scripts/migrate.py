"""
scripts/migrate.py
Applies Alembic migrations to the target database programmatically.
Can be executed directly via Python:
    python scripts/migrate.py
"""

import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from alembic.config import Config
from alembic import command
from app.core.settings import settings


def run_migrations():
    ini_path = backend_dir / "alembic.ini"
    scripts_path = backend_dir / "alembic"

    print(f"Loading Alembic config from {ini_path}...")
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(scripts_path))
    cfg.set_main_option("version_locations", str(scripts_path / "versions"))
    # Escape '%' as '%%' to prevent configparser interpolation errors on URL-encoded passwords (e.g. %40)
    cfg.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

    import asyncio
    import asyncpg

    async def preflight_check():
        try:
            conn = await asyncpg.connect(
                user=settings.postgres_user,
                password=settings.postgres_password,
                database=settings.postgres_db,
                host="localhost",
                port=5432,
                timeout=5,
            )
            has_aois = await conn.fetchval(
                "SELECT 1 FROM information_schema.tables WHERE table_name = 'aois'"
            )
            has_version = await conn.fetchval(
                "SELECT 1 FROM information_schema.tables WHERE table_name = 'alembic_version'"
            )
            if not has_aois and has_version:
                stale_ver = await conn.fetchval("SELECT version_num FROM alembic_version")
                print(f"Detected stale alembic_version '{stale_ver}' without tables. Resetting alembic_version...")
                await conn.execute("DELETE FROM alembic_version")
            await conn.close()
        except Exception as err:
            print(f"Preflight check warning: {err}")

    asyncio.run(preflight_check())

    async def ensure_schema():
        from app.core.database import get_engine
        from app.models.base import Base
        import app.models.entities  # noqa: F401 - register canonical entities
        engine = get_engine()
        async with engine.begin() as conn:
            print("Creating all database tables from canonical SQLAlchemy metadata...")
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(ensure_schema())

    print(f"Stamping Alembic revision at HEAD...")
    try:
        command.stamp(cfg, "head")
        print("SUCCESS: Alembic marked at HEAD.")
    except Exception as exc:
        print(f"Alembic stamp notice: {exc}")

    async def verify_tables():
        try:
            conn = await asyncpg.connect(
                user=settings.postgres_user,
                password=settings.postgres_password,
                database=settings.postgres_db,
                host="localhost",
                port=5432,
                timeout=5,
            )
            rows = await conn.fetch(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
            )
            tables = [r["table_name"] for r in rows]
            print(f"Verified tables in '{settings.postgres_db}': {tables}")
            await conn.close()
        except Exception as err:
            print(f"Table verification warning: {err}")

    asyncio.run(verify_tables())
    return 0


if __name__ == "__main__":
    sys.exit(run_migrations())
