"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-10-22 11:25:36.717883+00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('origins',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('donor_name', sa.String(length=160), nullable=False),
    sa.Column('donated_at', sa.Date(), nullable=True),
    sa.Column('seedling_count', sa.Integer(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('seedling_count >= 0', name=op.f('ck_origins_seedling_count_non_negative')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_origins')),
    sa.UniqueConstraint('donor_name', name=op.f('uq_origins_donor_name'))
    )
    op.create_table('planting_zones',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('restrictions', sa.Text(), nullable=True),
    sa.Column('polygon_geojson', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_planting_zones')),
    sa.UniqueConstraint('name', name=op.f('uq_planting_zones_name'))
    )
    op.create_table('species',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('common_name', sa.String(length=120), nullable=False),
    sa.Column('scientific_name', sa.String(length=160), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('size_class', sa.String(length=60), nullable=True),
    sa.Column('root_notes', sa.Text(), nullable=True),
    sa.Column('fruiting_season', sa.String(length=120), nullable=True),
    sa.Column('fun_fact', sa.Text(), nullable=True),
    sa.Column('photo_path', sa.String(length=255), nullable=True),
    sa.Column('data_review_status', sa.Enum('pending', 'reviewed', name='data_review_status', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_species')),
    sa.UniqueConstraint('common_name', name=op.f('uq_species_common_name'))
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=60), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('username', name=op.f('uq_users_username'))
    )
    op.create_table('watering_rules',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('phase', sa.Enum('newly_planted', 'established', name='watering_phase', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('interval_days', sa.Float(), nullable=False),
    sa.Column('phase_until_days', sa.Integer(), nullable=True),
    sa.Column('is_placeholder', sa.Boolean(), nullable=False),
    sa.Column('note', sa.String(length=280), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('interval_days > 0', name=op.f('ck_watering_rules_interval_positive')),
    sa.CheckConstraint('phase_until_days IS NULL OR phase_until_days > 0', name=op.f('ck_watering_rules_until_positive')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_watering_rules')),
    sa.UniqueConstraint('phase', name=op.f('uq_watering_rules_phase'))
    )
    op.create_table('rain_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('precipitation_mm', sa.Numeric(precision=6, scale=1), nullable=True),
    sa.Column('source', sa.Enum('manual', 'automatic', name='rain_source', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('notes', sa.String(length=280), nullable=True),
    sa.Column('created_by_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('precipitation_mm IS NULL OR precipitation_mm >= 0', name=op.f('ck_rain_events_precipitation_non_negative')),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], name=op.f('fk_rain_events_created_by_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rain_events'))
    )
    op.create_index(op.f('ix_rain_events_occurred_at'), 'rain_events', ['occurred_at'], unique=False)
    op.create_table('trees',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=16), nullable=False),
    sa.Column('public_id', sa.String(length=8), nullable=False),
    sa.Column('species_id', sa.Integer(), nullable=False),
    sa.Column('origin_id', sa.Integer(), nullable=False),
    sa.Column('zone_id', sa.Integer(), nullable=True),
    sa.Column('planting_batch', sa.Integer(), nullable=True),
    sa.Column('status', sa.Enum('awaiting_planting', 'planted', 'attention', 'dead', name='tree_status', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('planted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('lat', sa.Double(), nullable=True),
    sa.Column('lng', sa.Double(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status NOT IN ('planted', 'attention') OR planted_at IS NOT NULL", name=op.f('ck_trees_planted_requires_date')),
    sa.CheckConstraint('(lat IS NULL) = (lng IS NULL)', name=op.f('ck_trees_lat_lng_together')),
    sa.CheckConstraint('lat IS NULL OR lat BETWEEN -90 AND 90', name=op.f('ck_trees_lat_range')),
    sa.CheckConstraint('lng IS NULL OR lng BETWEEN -180 AND 180', name=op.f('ck_trees_lng_range')),
    sa.CheckConstraint('planting_batch IS NULL OR planting_batch > 0', name=op.f('ck_trees_batch_positive')),
    sa.ForeignKeyConstraint(['origin_id'], ['origins.id'], name=op.f('fk_trees_origin_id_origins'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['species_id'], ['species.id'], name=op.f('fk_trees_species_id_species'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['zone_id'], ['planting_zones.id'], name=op.f('fk_trees_zone_id_planting_zones'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_trees')),
    sa.UniqueConstraint('code', name=op.f('uq_trees_code')),
    sa.UniqueConstraint('public_id', name=op.f('uq_trees_public_id'))
    )
    op.create_index(op.f('ix_trees_origin_id'), 'trees', ['origin_id'], unique=False)
    op.create_index(op.f('ix_trees_species_id'), 'trees', ['species_id'], unique=False)
    op.create_index(op.f('ix_trees_status'), 'trees', ['status'], unique=False)
    op.create_index(op.f('ix_trees_zone_id'), 'trees', ['zone_id'], unique=False)
    op.create_table('care_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tree_id', sa.Integer(), nullable=False),
    sa.Column('type', sa.Enum('watering', 'fertilizing', 'pruning', 'other', name='care_event_type', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('performed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('performed_by_name', sa.String(length=60), nullable=True),
    sa.Column('notes', sa.String(length=280), nullable=True),
    sa.Column('source', sa.Enum('public', 'admin', name='event_source', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('ip_hash', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['tree_id'], ['trees.id'], name=op.f('fk_care_events_tree_id_trees'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_care_events'))
    )
    op.create_index('ix_care_events_ip_hash_created', 'care_events', ['ip_hash', 'created_at'], unique=False)
    op.create_index('ix_care_events_tree_type_performed', 'care_events', ['tree_id', 'type', 'performed_at'], unique=False)
    op.create_table('photos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tree_id', sa.Integer(), nullable=False),
    sa.Column('taken_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('file_path', sa.String(length=255), nullable=False),
    sa.Column('caption', sa.String(length=200), nullable=True),
    sa.Column('uploaded_by_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['tree_id'], ['trees.id'], name=op.f('fk_photos_tree_id_trees'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['uploaded_by_id'], ['users.id'], name=op.f('fk_photos_uploaded_by_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_photos'))
    )
    op.create_index(op.f('ix_photos_tree_id'), 'photos', ['tree_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_photos_tree_id'), table_name='photos')
    op.drop_table('photos')
    op.drop_index('ix_care_events_tree_type_performed', table_name='care_events')
    op.drop_index('ix_care_events_ip_hash_created', table_name='care_events')
    op.drop_table('care_events')
    op.drop_index(op.f('ix_trees_zone_id'), table_name='trees')
    op.drop_index(op.f('ix_trees_status'), table_name='trees')
    op.drop_index(op.f('ix_trees_species_id'), table_name='trees')
    op.drop_index(op.f('ix_trees_origin_id'), table_name='trees')
    op.drop_table('trees')
    op.drop_index(op.f('ix_rain_events_occurred_at'), table_name='rain_events')
    op.drop_table('rain_events')
    op.drop_table('watering_rules')
    op.drop_table('users')
    op.drop_table('species')
    op.drop_table('planting_zones')
    op.drop_table('origins')
