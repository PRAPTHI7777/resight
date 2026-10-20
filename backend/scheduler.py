import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from config import DIGEST_INTERVAL_MINUTES, DIGEST_SCHEDULER_ENABLED
from database import SessionLocal, engine
from digest import create_digest_email
from arxiv_service import fetch_papers
from email_service import send_email
import models


scheduler = BackgroundScheduler()
logger = logging.getLogger(__name__)
DIGEST_LOCK_KEY = 0x52455349474854


def send_scheduled_digest():
    lock_connection = None
    lock_acquired = False
    try:
        lock_connection = engine.connect()
        lock_acquired = bool(
            lock_connection.execute(
                text("SELECT pg_try_advisory_lock(:lock_key)"),
                {"lock_key": DIGEST_LOCK_KEY},
            ).scalar()
        )
        if not lock_acquired:
            logger.info("Another process already owns the scheduled digest lock.")
            return

        logger.info("Starting scheduled Resight digest.")

        db = SessionLocal(bind=lock_connection)
        try:
            papers = fetch_papers("artificial intelligence")
            html_body = create_digest_email(papers)
            subscribers = db.query(models.User).filter(
                models.User.is_subscribed == True
            ).all()

            for user in subscribers:
                send_email(
                    user.email,
                    "Your Resight Research Digest",
                    html_body
                )
            logger.info("Digest sent to %s subscribers.", len(subscribers))
        finally:
            db.close()

    except Exception as error:
        logger.exception(
            "Scheduled digest failed (%s).",
            type(error).__name__,
        )

    finally:
        if lock_acquired and lock_connection is not None:
            try:
                lock_connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_key)"),
                    {"lock_key": DIGEST_LOCK_KEY},
                )
            except SQLAlchemyError:
                logger.exception("Could not release the scheduled digest lock.")
        if lock_connection is not None:
            lock_connection.close()


def start_scheduler():
    if not DIGEST_SCHEDULER_ENABLED:
        logger.info("Automated digest scheduler is disabled.")
        return
    if scheduler.running:
        return
    scheduler.add_job(
        send_scheduled_digest,
        "interval",
        minutes=DIGEST_INTERVAL_MINUTES,
        id="resight_digest",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    scheduler.start()
    logger.info("Resight digest scheduler started.")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)