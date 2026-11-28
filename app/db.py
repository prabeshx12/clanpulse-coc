"""Database engine, sessions and the declarative Base for all models."""
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Parent class for every table in app/models.py."""


def make_engine(database_url: str, echo: bool = False) -> Engine:
    """Create an engine. For SQLite, also turn on foreign key enforcement.

    echo=True prints every SQL statement, handy for learning what the ORM does.
    """
    engine = create_engine(database_url, echo=echo)

    if engine.dialect.name == "sqlite":
        # SQLite ignores FOREIGN KEY constraints unless this is set on every connection.
        @event.listens_for(engine, "connect")
        def _enable_sqlite_fks(dbapi_conn, _record) -> None:  # type: ignore[no-untyped-def]
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a factory that creates Sessions bound to this engine."""
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    """Create any tables that don't exist yet. Doesn't alter existing tables."""
    from app import models  # noqa: F401  (import registers the tables on Base)

    Base.metadata.create_all(engine)


if __name__ == "__main__":
    # python -m app.db  → creates the tables in the database from .env
    from app import db
    from app.config import get_settings

    settings = get_settings()
    db.init_db(db.make_engine(settings.database_url))
    print(f"Tables created in {settings.database_url}")
