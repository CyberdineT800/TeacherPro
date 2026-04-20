"""
One-shot data migration: SQLite → PostgreSQL.

Usage on the server:
    SQLITE_URL='sqlite+aiosqlite:////var/www/teacherpro/data/school_grading.db' \
    POSTGRES_URL='postgresql+asyncpg://teacherpro:PASSWORD@localhost:5432/teacherpro' \
    /var/www/teacherpro/venv/bin/python migrate_sqlite_to_postgres.py

The destination postgres database must exist and be empty.
"""
import asyncio
import os
import sys

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

import models
from models import (
    Base, School, StaffTitle, Employee, TeacherClass, TeacherSubject,
    SchoolClass, Student, Subject, Quarter, ExamName, ExamType,
    QuestionType, Exam, CHSBQuestionAssignment, Question, ExamResult,
)

# Order matters: parents before children
MIGRATION_ORDER = [
    School, StaffTitle, Subject, Quarter, ExamName, ExamType, QuestionType,
    Employee, SchoolClass, Student,
    TeacherClass, TeacherSubject,
    Exam, CHSBQuestionAssignment, Question, ExamResult,
]


def _row_to_dict(obj, model):
    return {col.name: getattr(obj, col.name) for col in model.__table__.columns}


async def reset_sequences(pg_session: AsyncSession):
    """Postgres sequences must be advanced past the imported max(id)."""
    for model in MIGRATION_ORDER:
        table = model.__tablename__
        seq = f"{table}_id_seq"
        await pg_session.execute(text(
            f"SELECT setval('{seq}', COALESCE((SELECT MAX(id) FROM {table}), 1), "
            f"(SELECT MAX(id) IS NOT NULL FROM {table}))"
        ))
    await pg_session.commit()


async def migrate():
    sqlite_url = os.environ.get('SQLITE_URL')
    postgres_url = os.environ.get('POSTGRES_URL')

    if not sqlite_url or not postgres_url:
        print("ERROR: SQLITE_URL and POSTGRES_URL env vars are required")
        sys.exit(1)

    print(f"Source: {sqlite_url}")
    print(f"Target: {postgres_url}")

    src_engine = create_async_engine(sqlite_url, future=True)
    dst_engine = create_async_engine(postgres_url, future=True)

    SrcSession = async_sessionmaker(src_engine, class_=AsyncSession, expire_on_commit=False)
    DstSession = async_sessionmaker(dst_engine, class_=AsyncSession, expire_on_commit=False)

    print("── Creating destination schema ──")
    async with dst_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SrcSession() as src, DstSession() as dst:
        for model in MIGRATION_ORDER:
            existing = (await dst.execute(select(model))).scalars().first()
            if existing:
                print(f"  {model.__tablename__}: skipped (target not empty)")
                continue

            rows = (await src.execute(select(model))).scalars().all()
            if not rows:
                print(f"  {model.__tablename__}: 0 rows")
                continue

            for r in rows:
                dst.add(model(**_row_to_dict(r, model)))
            await dst.commit()
            print(f"  {model.__tablename__}: {len(rows)} rows")

        print("── Resetting postgres sequences ──")
        await reset_sequences(dst)

    await src_engine.dispose()
    await dst_engine.dispose()
    print("Migration complete.")


if __name__ == "__main__":
    asyncio.run(migrate())
