"""add search indexes to vehicles table

Revision ID: 591b678e0623
Revises: 0f02e5310259
Create Date: 2026-07-30 20:18:00.247403

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '591b678e0623'
down_revision: Union[str, Sequence[str], None] = '0f02e5310259'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

from alembic import op


def upgrade() -> None:
    # Single-column indexes for the most commonly filtered fields.
    # Each index speeds up queries that filter on that column alone.
    op.create_index(
        "ix_vehicles_make",
        "vehicles",
        ["make"]
    )
    op.create_index(
        "ix_vehicles_model",
        "vehicles",
        ["model"]
    )
    op.create_index(
        "ix_vehicles_year",
        "vehicles",
        ["year"]
    )
    op.create_index(
        "ix_vehicles_price",
        "vehicles",
        ["price"]
    )
    op.create_index(
        "ix_vehicles_category",
        "vehicles",
        ["category"]
    )
    op.create_index(
        "ix_vehicles_quantity",
        "vehicles",
        ["quantity"]
    )

    # Composite index for the most common combined search.
    # A composite index on (make, model, category) helps queries that
    # filter on any left-prefix combination: make alone, make+model,
    # or make+model+category. It does NOT help queries on model alone.
    # This is called the leftmost prefix rule of composite indexes.
    op.create_index(
        "ix_vehicles_make_model_category",
        "vehicles",
        ["make", "model", "category"]
    )

    # Partial index: only index rows where is_deleted = false.
    # Since the application always excludes deleted records, this index
    # is smaller and faster than a full index on all rows.
    # postgresql_where restricts the index to non-deleted rows only.
    op.create_index(
        "ix_vehicles_active_price",
        "vehicles",
        ["price"],
        postgresql_where="is_deleted = false"
    )

    op.create_index(
        "ix_vehicles_active_quantity",
        "vehicles",
        ["quantity"],
        postgresql_where="is_deleted = false"
    )


def downgrade() -> None:
    op.drop_index("ix_vehicles_active_quantity", table_name="vehicles")
    op.drop_index("ix_vehicles_active_price", table_name="vehicles")
    op.drop_index("ix_vehicles_make_model_category", table_name="vehicles")
    op.drop_index("ix_vehicles_quantity", table_name="vehicles")
    op.drop_index("ix_vehicles_category", table_name="vehicles")
    op.drop_index("ix_vehicles_price", table_name="vehicles")
    op.drop_index("ix_vehicles_year", table_name="vehicles")
    op.drop_index("ix_vehicles_model", table_name="vehicles")
    op.drop_index("ix_vehicles_make", table_name="vehicles")