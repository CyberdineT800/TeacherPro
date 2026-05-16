"""Initial schema migrations — columns added after first deploy.

Revision ID: 001
Revises:
Create Date: 2026-05-16

This migration captures every ALTER TABLE that was previously run inline
inside init_db() on application startup.  Moving them here gives us:
  - a single source of truth for schema history
  - idempotency via IF NOT EXISTS / IF EXISTS guards
  - proper rollback stubs (downgrade drops what was added)

On an existing production database: run `alembic stamp 001` to mark this
migration as already applied without re-running it, then use
`alembic upgrade head` for all future changes.

On a fresh database: `alembic upgrade head` applies everything in order.
"""
from alembic import op


# revision identifiers
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── employees: AI presentation columns ───────────────────────────────────
    op.execute(
        "ALTER TABLE employees "
        "ADD COLUMN IF NOT EXISTS ai_enabled BOOLEAN NOT NULL DEFAULT FALSE, "
        "ADD COLUMN IF NOT EXISTS ai_daily_limit INTEGER NOT NULL DEFAULT 3, "
        "ADD COLUMN IF NOT EXISTS ai_used_today INTEGER NOT NULL DEFAULT 0, "
        "ADD COLUMN IF NOT EXISTS ai_last_reset DATE"
    )

    # ── ai_presentations: template column ────────────────────────────────────
    op.execute(
        "ALTER TABLE ai_presentations "
        "ADD COLUMN IF NOT EXISTS template VARCHAR(50) NOT NULL DEFAULT 'cosmos'"
    )

    # ── employees: AI question columns ───────────────────────────────────────
    op.execute(
        "ALTER TABLE employees "
        "ADD COLUMN IF NOT EXISTS ai_questions_daily_limit INTEGER NOT NULL DEFAULT 5, "
        "ADD COLUMN IF NOT EXISTS ai_questions_used_today INTEGER NOT NULL DEFAULT 0, "
        "ADD COLUMN IF NOT EXISTS ai_questions_last_reset DATE"
    )

    # ── employees: games access ───────────────────────────────────────────────
    op.execute(
        "ALTER TABLE employees "
        "ADD COLUMN IF NOT EXISTS games_enabled BOOLEAN NOT NULL DEFAULT FALSE"
    )

    # ── announcements: widen image_url + extra image slots ───────────────────
    op.execute("ALTER TABLE announcements ALTER COLUMN image_url TYPE TEXT")
    op.execute(
        "ALTER TABLE announcements "
        "ADD COLUMN IF NOT EXISTS image_url_2 TEXT, "
        "ADD COLUMN IF NOT EXISTS image_url_3 TEXT"
    )

    # ── game_participants: unique nickname per session ────────────────────────
    op.execute(
        "DO $body$ BEGIN "
        "  IF NOT EXISTS ("
        "    SELECT 1 FROM pg_constraint "
        "    WHERE conname = 'uq_participant_session_nickname'"
        "  ) THEN "
        "    ALTER TABLE game_participants "
        "    ADD CONSTRAINT uq_participant_session_nickname "
        "    UNIQUE (session_id, nickname); "
        "  END IF; "
        "END $body$"
    )

    # ── ai_presentations: shareable link token ───────────────────────────────
    op.execute(
        "ALTER TABLE ai_presentations "
        "ADD COLUMN IF NOT EXISTS share_token VARCHAR(64)"
    )
    op.execute(
        "DO $body$ BEGIN "
        "  IF NOT EXISTS ("
        "    SELECT 1 FROM pg_indexes "
        "    WHERE indexname = 'ix_ai_presentations_share_token'"
        "  ) THEN "
        "    CREATE UNIQUE INDEX ix_ai_presentations_share_token "
        "    ON ai_presentations (share_token) "
        "    WHERE share_token IS NOT NULL; "
        "  END IF; "
        "END $body$"
    )


def downgrade() -> None:
    # Dropping columns with data is destructive — left as no-op intentionally.
    # To roll back, restore from a database backup.
    pass
