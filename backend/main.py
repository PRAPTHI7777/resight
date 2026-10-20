from contextlib import asynccontextmanager
import logging
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import users
from database import Base, engine
import articles
import auth
import bookmarks
import likes
from subscription import router as subscription_router
from digest import router as digest_router
from scheduler import start_scheduler, stop_scheduler
from config import ALLOWED_ORIGINS
from sqlalchemy.exc import SQLAlchemyError


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.debug("Starting %s application lifecycle.", app.title)
    try:
        Base.metadata.create_all(bind=engine)
    except SQLAlchemyError as error:
        logger.exception(
            "Database initialization failed. Check DATABASE_URL, network access, "
            "database availability, and schema permissions."
        )
        raise RuntimeError(
            "Database initialization failed; check the server log and database "
            "connection configuration."
        ) from error

    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ALLOWED_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Welcome to the Articles API"}

app.include_router(articles.router)
app.include_router(auth.router)
app.include_router(bookmarks.router)
app.include_router(users.router)
app.include_router(likes.router)
app.include_router(subscription_router)
app.include_router(digest_router)