"""
scripts/create_db.py
Creates the 'satquery' database in PostgreSQL if it does not already exist.
Connects to default administrative database 'postgres' to issue CREATE DATABASE.
"""

import os
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import asyncio
import asyncpg
from app.core.settings import settings


async def init_database():
    user = settings.postgres_user
    password = settings.postgres_password
    target_db = settings.postgres_db

    print(f"Connecting to PostgreSQL on localhost:5432 as user '{user}'...")
    try:
        # Connect to default system database 'postgres' to check/create target database
        conn = await asyncpg.connect(
            user=user,
            password=password,
            database="postgres",
            host="localhost",
            port=5432,
            timeout=5,
        )
    except Exception as exc:
        print(f"FAILED to connect to PostgreSQL on localhost:5432: {exc}")
        print("Please ensure PostgreSQL is running and credentials in .env are correct.")
        return False

    try:
        # Check if target database exists
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", target_db
        )
        if exists:
            print(f"Database '{target_db}' already exists.")
        else:
            print(f"Creating database '{target_db}'...")
            await conn.execute(f'CREATE DATABASE "{target_db}"')
            print(f"SUCCESS: Database '{target_db}' created successfully.")

        # Connect to target db and enable PostGIS extension
        await conn.close()

        print(f"Connecting to '{target_db}' to enable PostGIS extension...")
        target_conn = await asyncpg.connect(
            user=user,
            password=password,
            database=target_db,
            host="localhost",
            port=5432,
            timeout=5,
        )
        try:
            await target_conn.execute("CREATE EXTENSION IF NOT EXISTS postgis")
            postgis_ver = await target_conn.fetchval("SELECT PostGIS_Version()")
            print(f"SUCCESS: PostGIS extension enabled (Version: {postgis_ver}).")
        except Exception as pg_err:
            print(f"WARNING: PostGIS extension could not be enabled: {pg_err}")
            print("Note: If PostGIS is not installed in PostgreSQL, install it via the PostgreSQL Application Stack Builder.")
        finally:
            await target_conn.close()

        return True
    except Exception as exc:
        print(f"ERROR: {exc}")
        return False


if __name__ == "__main__":
    asyncio.run(init_database())
