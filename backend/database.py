import logging

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

from config import DATABASE_CONNECT_TIMEOUT_SECONDS, DATABASE_URL


logger = logging.getLogger(__name__)

try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        connect_args={"connect_timeout": DATABASE_CONNECT_TIMEOUT_SECONDS},
    )
except SQLAlchemyError as error:
    logger.exception("Could not configure the database engine.")
    raise RuntimeError(
        "Database engine configuration failed. Check DATABASE_URL and ensure "
        "the PostgreSQL driver is installed."
    ) from error

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
