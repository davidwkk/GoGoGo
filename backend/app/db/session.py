from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base

engine = create_engine(settings.DATABASE_URL, echo=False)

session_factory = sessionmaker(engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
