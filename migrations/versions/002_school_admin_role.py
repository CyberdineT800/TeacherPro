"""School Admin role — distinguish super admins from school-scoped admins.

Revision ID: 002
Revises: 001
Create Date: 2026-06-17

Adds employees.is_super_admin. Existing administrators (is_admin = TRUE)
are promoted to super admins so nobody loses access after deploy; the
"School Admin" checkbox created from now on produces a school-scoped admin
(is_admin = TRUE, is_super_admin = FALSE).
"""
from alembic import op


# revision identifiers
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE employees "
        "ADD COLUMN IF NOT EXISTS is_super_admin BOOLEAN NOT NULL DEFAULT FALSE"
    )
    op.execute(
        "UPDATE employees SET is_super_admin = TRUE WHERE is_admin = TRUE"
    )


def downgrade() -> None:
    # Dropping columns with data is destructive — left as no-op intentionally.
    pass
