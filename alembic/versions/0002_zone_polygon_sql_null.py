"""Store empty zone polygons as SQL NULL instead of JSON null

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-22
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE planting_zones SET polygon_geojson = NULL WHERE polygon_geojson = 'null'::jsonb")
    op.create_check_constraint(
        "ck_planting_zones_polygon_not_json_null",
        "planting_zones",
        "polygon_geojson IS NULL OR jsonb_typeof(polygon_geojson) = 'object'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_planting_zones_polygon_not_json_null", "planting_zones", type_="check")
