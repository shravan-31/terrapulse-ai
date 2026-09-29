"""002_postgis_geometry_and_indexes

Revision ID: 002_postgis_geometry_and_indexes
Revises: 001_initial_schema
Create Date: 2026-09-28 23:25:00

Enhances initial schema with:
- Native PostGIS geometry columns and GiST spatial indexes for aois, scenes, and changes
- Explicit foreign key and lookup indexes for high-throughput queries
- Data integrity check constraints (ranges for area, cloud cover, confidence, progress)
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002_postgis_geometry_and_indexes'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. PostGIS Geometry columns and GiST indexes (if PostGIS extension is active)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'postgis') THEN
                ALTER TABLE aois ADD COLUMN IF NOT EXISTS geom geometry(Geometry, 4326);
                CREATE INDEX IF NOT EXISTS ix_aois_geom ON aois USING GIST (geom);

                ALTER TABLE scenes ADD COLUMN IF NOT EXISTS footprint_geom geometry(Geometry, 4326);
                CREATE INDEX IF NOT EXISTS ix_scenes_footprint_geom ON scenes USING GIST (footprint_geom);

                ALTER TABLE changes ADD COLUMN IF NOT EXISTS polygon_geom geometry(Geometry, 4326);
                CREATE INDEX IF NOT EXISTS ix_changes_polygon_geom ON changes USING GIST (polygon_geom);
            END IF;
        END $$;
    """)

    # 2. Foreign Key & Query Indexes
    op.create_index('ix_scene_assets_scene_id', 'scene_assets', ['scene_id'], if_not_exists=True)
    op.create_index('ix_tiles_scene_id', 'tiles', ['scene_id'], if_not_exists=True)
    op.create_index('ix_analyses_aoi_id', 'analyses', ['aoi_id'], if_not_exists=True)
    op.create_index('ix_changes_analysis_id', 'changes', ['analysis_id'], if_not_exists=True)
    op.create_index('ix_analyst_decisions_change_id', 'analyst_decisions', ['change_id'], if_not_exists=True)
    op.create_index('ix_job_events_job_id', 'job_events', ['job_id'], if_not_exists=True)
    op.create_index('ix_job_events_created_at', 'job_events', ['created_at'], if_not_exists=True)
    op.create_index('ix_index_outbox_status', 'index_outbox', ['status'], if_not_exists=True)

    # 3. Check Constraints
    op.create_check_constraint(
        'ck_aoi_area_positive',
        'aois',
        'area_km2 > 0'
    )
    op.create_check_constraint(
        'ck_scenes_cloud_range',
        'scenes',
        'cloud_coverage_percent >= 0.0 AND cloud_coverage_percent <= 100.0'
    )
    op.create_check_constraint(
        'ck_changes_area_positive',
        'changes',
        'area_m2 >= 0.0'
    )
    op.create_check_constraint(
        'ck_changes_confidence_range',
        'changes',
        'confidence_score >= 0.0 AND confidence_score <= 1.0'
    )
    op.create_check_constraint(
        'ck_jobs_progress_range',
        'jobs',
        'progress_percent >= 0.0 AND progress_percent <= 100.0'
    )


def downgrade() -> None:
    # Drop constraints
    op.drop_constraint('ck_jobs_progress_range', 'jobs', type_='check')
    op.drop_constraint('ck_changes_confidence_range', 'changes', type_='check')
    op.drop_constraint('ck_changes_area_positive', 'changes', type_='check')
    op.drop_constraint('ck_scenes_cloud_range', 'scenes', type_='check')
    op.drop_constraint('ck_aoi_area_positive', 'aois', type_='check')

    # Drop indexes
    op.drop_index('ix_index_outbox_status', table_name='index_outbox')
    op.drop_index('ix_job_events_created_at', table_name='job_events')
    op.drop_index('ix_job_events_job_id', table_name='job_events')
    op.drop_index('ix_analyst_decisions_change_id', table_name='analyst_decisions')
    op.drop_index('ix_changes_analysis_id', table_name='changes')
    op.drop_index('ix_analyses_aoi_id', table_name='analyses')
    op.drop_index('ix_tiles_scene_id', table_name='tiles')
    op.drop_index('ix_scene_assets_scene_id', table_name='scene_assets')

    # Drop PostGIS columns & spatial indexes
    op.execute("DROP INDEX IF EXISTS ix_changes_polygon_geom;")
    op.execute("ALTER TABLE changes DROP COLUMN IF EXISTS polygon_geom;")

    op.execute("DROP INDEX IF EXISTS ix_scenes_footprint_geom;")
    op.execute("ALTER TABLE scenes DROP COLUMN IF EXISTS footprint_geom;")

    op.execute("DROP INDEX IF EXISTS ix_aois_geom;")
    op.execute("ALTER TABLE aois DROP COLUMN IF EXISTS geom;")
