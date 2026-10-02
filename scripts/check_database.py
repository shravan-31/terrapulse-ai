"""
scripts/check_database.py
Validates PostgreSQL connectivity, PostGIS spatial extension, and checks table presence.
"""

import sys
import asyncio
from pathlib import Path

# Add backend to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.settings import settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def check_db():
    print("=" * 60)
    print("TerraPulse AI — Database & PostGIS Verification")
    print("=" * 60)
    print(f"Target Database URL: {settings.database_url.split('@')[-1] if '@' in settings.database_url else settings.database_url}")

    try:
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        async with engine.connect() as conn:
            # 1. Basic Ping
            res = await conn.execute(text("SELECT version();"))
            ver = res.scalar()
            print(f"  [OK] PostgreSQL Server   : {ver.split(',')[0] if ver else 'Connected'}")

            # 2. PostGIS Check
            try:
                pg_res = await conn.execute(text("SELECT PostGIS_Version();"))
                pg_ver = pg_res.scalar()
                print(f"  [OK] PostGIS Extension   : {pg_ver}")
            except Exception:
                print("  [--] PostGIS Extension   : Not active (Using standard JSONB geometry coordinates)")

            # 3. Tables Check
            t_res = await conn.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' ORDER BY table_name;
            """))
            tables = [row[0] for row in t_res.fetchall()]
            print(f"  [OK] Public Schema Tables: {len(tables)} tables present")
            for t in tables[:10]:
                print(f"        - {t}")
            if len(tables) > 10:
                print(f"        ... and {len(tables) - 10} more")

        await engine.dispose()
        print("=" * 60)
        print("STATUS: DATABASE CONNECTIVITY HEALTHY")
        print("=" * 60)
    except Exception as e:
        print(f"  [FAIL] Database Connection Error: {e}")
        print("=" * 60)
        print("STATUS: DATABASE UNAVAILABLE (Local SQLite fallback or service start required)")
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(check_db())
