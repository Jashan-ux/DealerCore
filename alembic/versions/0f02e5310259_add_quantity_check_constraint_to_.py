"""add quantity check constraint to vehicles

Revision ID: 0f02e5310259
Revises: a0bfe67251b1
Create Date: 2026-07-30 18:54:48.046721

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0f02e5310259'
down_revision: Union[str, Sequence[str], None] = 'a0bfe67251b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from alembic import op


def upgrade() -> None:
    op.create_check_constraint(
        "ck_vehicles_quantity_non_negative",
        "vehicles",
        "quantity >= 0"
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_vehicles_quantity_non_negative",
        "vehicles",
        type_="check"
    )