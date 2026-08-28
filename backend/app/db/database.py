from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# connect_args needed only for SQLite; swap DATABASE_URL to a Postgres DSN
# (e.g. postgresql+psycopg2://user:pass@host/db) to move to Postgres later —
# no other code in this module needs to change.
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.db import models  # noqa: ensure models are registered
    Base.metadata.create_all(bind=engine)
