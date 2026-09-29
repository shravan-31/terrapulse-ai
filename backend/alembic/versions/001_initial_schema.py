"""001_initial_schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-28 15:50:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. PostGIS extension (if available on PostgreSQL server)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'postgis') THEN
                CREATE EXTENSION IF NOT EXISTS postgis;
            END IF;
        END $$;
    """)

    # 2. AOIs
    op.create_table(
        'aois',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('geometry', JSONB, nullable=False),
        sa.Column('area_km2', sa.Float(), nullable=False),
        sa.Column('vertex_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 3. Scenes
    op.create_table(
        'scenes',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('provider', sa.String(64), nullable=False),
        sa.Column('product_id', sa.String(255), nullable=False, unique=True),
        sa.Column('acquisition_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('cloud_coverage_percent', sa.Float(), nullable=False),
        sa.Column('footprint', JSONB, nullable=False),
        sa.Column('crs', sa.String(32), nullable=False),
        sa.Column('metadata_json', JSONB, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_scenes_product_id', 'scenes', ['product_id'])
    op.create_index('ix_scenes_acquisition_at', 'scenes', ['acquisition_at'])

    # 4. Scene Assets
    op.create_table(
        'scene_assets',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('scene_id', UUID(as_uuid=True), sa.ForeignKey('scenes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('asset_type', sa.String(64), nullable=False),
        sa.Column('local_path', sa.String(1024), nullable=False),
        sa.Column('checksum_sha256', sa.String(64), nullable=False),
        sa.Column('resolution_m', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 5. Tiles
    op.create_table(
        'tiles',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('scene_id', UUID(as_uuid=True), sa.ForeignKey('scenes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tile_index', sa.Integer(), nullable=False),
        sa.Column('bounds', JSONB, nullable=False),
        sa.Column('local_preview_path', sa.String(1024), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 6. Embeddings (with stable int64 vector_id for FAISS IndexIDMap2 per ADR-003)
    op.create_table(
        'embeddings',
        sa.Column('vector_id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tile_id', UUID(as_uuid=True), sa.ForeignKey('tiles.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('model_name', sa.String(128), nullable=False),
        sa.Column('model_version', sa.String(64), nullable=False),
        sa.Column('vector_dim', sa.Integer(), nullable=False),
        sa.Column('vector_data', JSONB, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 7. FAISS consistency: IndexGenerations & IndexOutbox (ADR-003)
    op.create_table(
        'index_generations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('generation_version', sa.Integer(), unique=True, nullable=False),
        sa.Column('total_vectors', sa.Integer(), nullable=False),
        sa.Column('snapshot_path', sa.String(1024), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'index_outbox',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('vector_id', sa.BigInteger(), nullable=False),
        sa.Column('action', sa.String(32), nullable=False),
        sa.Column('status', sa.String(32), nullable=False, default='pending'),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 8. Analyses
    op.create_table(
        'analyses',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('aoi_id', UUID(as_uuid=True), sa.ForeignKey('aois.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('status', sa.String(64), nullable=False),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 9. Changes (ADR-006, ADR-007, ADR-013)
    op.create_table(
        'changes',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('analysis_id', UUID(as_uuid=True), sa.ForeignKey('analyses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('change_type', sa.String(64), nullable=False),
        sa.Column('change_kind', sa.String(64), nullable=False),
        sa.Column('temporal_status', sa.String(64), nullable=False),
        sa.Column('last_baseline_observation_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('earliest_supported_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('latest_observation_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('polygon', JSONB, nullable=False),
        sa.Column('area_m2', sa.Float(), nullable=False),
        sa.Column('pixel_count', sa.Integer(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False, default=0.0),
        sa.Column('confidence_details', JSONB, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 10. Analyst decisions (ADR-007)
    op.create_table(
        'analyst_decisions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('change_id', UUID(as_uuid=True), sa.ForeignKey('changes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('operator', sa.String(128), nullable=False),
        sa.Column('review_status', sa.String(64), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 11. Provenance (ADR-002, ADR-015)
    op.create_table(
        'provenance',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('artifact_id', sa.String(255), nullable=False),
        sa.Column('artifact_type', sa.String(64), nullable=False),
        sa.Column('parent_artifact_ids', JSONB, nullable=False),
        sa.Column('source_references', JSONB, nullable=False),
        sa.Column('model_name', sa.String(128), nullable=True),
        sa.Column('model_sha256', sa.String(64), nullable=True),
        sa.Column('code_version', sa.String(64), nullable=False),
        sa.Column('parameters', JSONB, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_provenance_artifact_id', 'provenance', ['artifact_id'])

    # 12. Jobs & Job Events (ADR-005)
    op.create_table(
        'jobs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('job_type', sa.String(64), nullable=False),
        sa.Column('status', sa.String(32), nullable=False, default='pending'),
        sa.Column('progress_percent', sa.Float(), nullable=False, default=0.0),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'job_events',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('job_id', UUID(as_uuid=True), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(64), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('event_data', JSONB, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('job_events')
    op.drop_table('jobs')
    op.drop_table('provenance')
    op.drop_table('analyst_decisions')
    op.drop_table('changes')
    op.drop_table('analyses')
    op.drop_table('index_outbox')
    op.drop_table('index_generations')
    op.drop_table('embeddings')
    op.drop_table('tiles')
    op.drop_table('scene_assets')
    op.drop_table('scenes')
    op.drop_table('aois')
