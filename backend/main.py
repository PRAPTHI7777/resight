from contextlib import asynccontextmanager
import logging
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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


def _configure_timing_loggers() -> None:
    uvicorn_logger = logging.getLogger("uvicorn")
    handlers = uvicorn_logger.handlers
    if not handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter("%(levelname)s %(name)s: %(message)s")
        )
        handlers = [console_handler]

    for logger_name in ("articles", "arxiv_service"):
        timing_logger = logging.getLogger(logger_name)
        timing_logger.setLevel(logging.INFO)
        timing_logger.propagate = False
        for handler in handlers:
            if handler not in timing_logger.handlers:
                timing_logger.addHandler(handler)


_configure_timing_loggers()


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


@app.exception_handler(SQLAlchemyError)
async def handle_database_error(request: Request, error: SQLAlchemyError):
    logger.error(
        "Database operation failed (%s) while handling %s %s.",
        type(error).__name__,
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=503,
        content={"detail": "A database operation failed. Please try again."},
    )


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