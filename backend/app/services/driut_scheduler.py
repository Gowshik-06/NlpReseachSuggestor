"""
In-process background scheduler for Dynamic Research Impact Update Tracker (DRIUT).

Manages periodic research literature monitoring, academic source querying,
taxonomy classification, and alert creation with concurrency locks and graceful
FastAPI lifespan startup/shutdown hooks.
"""
import asyncio
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from app.core.config import get_settings
from app.core.logging import get_logger
from sqlalchemy import text
from app.db.session import SessionLocal, engine
from app.services.driut_service import scan_research_impact_updates

logger = get_logger(__name__)


class DRIUTScheduler:
    def __init__(self):
        settings = get_settings()
        self._is_enabled: bool = getattr(settings, "ENABLE_DRIUT_SCHEDULER", True)
        self._interval_minutes: int = getattr(settings, "DRIUT_SCAN_INTERVAL_MINUTES", 60)
        self._query_academic: bool = getattr(settings, "DRIUT_QUERY_ACADEMIC_SOURCES", True)
        self._advisory_lock_key: int = getattr(settings, "DRIUT_ADVISORY_LOCK_KEY", 7376232)

        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._is_running_scan: bool = False

        self._last_run_time: Optional[datetime] = None
        self._last_run_duration_seconds: Optional[float] = None
        self._last_run_status: str = "idle"
        self._total_scans_completed: int = 0
        self._last_scan_metrics: Dict[str, Any] = {}
        self._provider_status: Dict[str, str] = {
            "arxiv": "idle",
            "pubmed": "idle",
            "csir": "idle",
            "crossref": "idle"
        }
        self._provider_errors: Dict[str, str] = {}

    @property
    def is_enabled(self) -> bool:
        return self._is_enabled

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def advisory_lock_key(self) -> int:
        return self._advisory_lock_key

    def _acquire_advisory_lock(self, lock_key: int):
        """
        Attempt to non-blockingly acquire a session-level PostgreSQL advisory lock.
        Uses a dedicated connection with AUTOCOMMIT so no database transaction
        is held open across long network requests.
        Returns: (lock_acquired: bool, connection: Optional[Connection])
        """
        try:
            if engine.dialect.name != "postgresql":
                # For non-PostgreSQL dialects (e.g. SQLite in isolated test mocks), proceed
                return True, None

            conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
            acquired = conn.execute(
                text("SELECT pg_try_advisory_lock(:key)"),
                {"key": lock_key}
            ).scalar()

            if not acquired:
                conn.close()
                return False, None
            return True, conn
        except Exception as err:
            logger.error("Failed to acquire PostgreSQL advisory lock %s: %s", lock_key, err)
            return False, None

    def _release_advisory_lock(self, conn, lock_key: int):
        """Release session-level PostgreSQL advisory lock and close connection."""
        if conn is None:
            return
        try:
            conn.execute(
                text("SELECT pg_advisory_unlock(:key)"),
                {"key": lock_key}
            )
        except Exception as err:
            logger.warning("Error releasing PostgreSQL advisory lock %s: %s", lock_key, err)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    async def start(self) -> None:
        """Start the periodic background scheduler task."""
        if not self._is_enabled:
            logger.info("DRIUT background scheduler is disabled (ENABLE_DRIUT_SCHEDULER=False).")
            return

        if self._task and not self._task.done():
            logger.warning("DRIUT background scheduler is already running.")
            return

        self._task = asyncio.create_task(
            self._scheduler_loop(),
            name="driut-background-scheduler-loop"
        )
        logger.info(
            "DRIUT background scheduler started (interval: %d minutes, academic queries: %s).",
            self._interval_minutes, self._query_academic
        )

    async def stop(self) -> None:
        """Gracefully stop the background scheduler task."""
        if self._task and not self._task.done():
            logger.info("Stopping DRIUT background scheduler...")
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            logger.info("DRIUT background scheduler stopped cleanly.")

    async def _scheduler_loop(self) -> None:
        """Internal periodic scheduling loop."""
        try:
            while True:
                # Sleep interval seconds
                await asyncio.sleep(self._interval_minutes * 60)
                logger.info("DRIUT scheduler: Starting scheduled research impact scan...")
                try:
                    await self.run_scan_job(user_id=None, query_academic=self._query_academic)
                except Exception as err:
                    logger.error("Error during scheduled DRIUT monitoring scan: %s", err, exc_info=True)
        except asyncio.CancelledError:
            logger.debug("DRIUT scheduler loop cancelled.")

    async def run_scan_job(
        self,
        user_id: Optional[str] = None,
        query_academic: Optional[bool] = None,
        require_advisory_lock: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Execute an automated DRIUT scan job with non-overlapping concurrency protection.
        Can be invoked by the background scheduler or on-demand via API endpoint.

        Scheduled scans (user_id=None) coordinate across multiple worker processes
        via PostgreSQL advisory locking (DRIUT_ADVISORY_LOCK_KEY).
        """
        if self._lock.locked() or self._is_running_scan:
            logger.warning("DRIUT scan already in progress in this process. Skipping overlapping invocation.")
            return {
                "status": "skipped",
                "reason": "A DRIUT scan is currently running in the background.",
                "new_alerts_created": 0,
                "papers_evaluated": 0,
                "alerts": []
            }

        async with self._lock:
            # Determine if PostgreSQL advisory lock is required across workers
            needs_advisory = (require_advisory_lock if require_advisory_lock is not None else (user_id is None))
            lock_conn = None

            if needs_advisory:
                acquired, lock_conn = self._acquire_advisory_lock(self._advisory_lock_key)
                if not acquired:
                    logger.warning(
                        "Another worker holds PostgreSQL advisory lock (%s). Skipping scheduled execution.",
                        self._advisory_lock_key
                    )
                    return {
                        "status": "skipped",
                        "reason": f"Another worker holds PostgreSQL advisory lock ({self._advisory_lock_key}).",
                        "new_alerts_created": 0,
                        "papers_evaluated": 0,
                        "alerts": []
                    }

            self._is_running_scan = True
            self._last_run_status = "running"
            start_time = time.monotonic()
            db = SessionLocal()

            try:
                should_query = query_academic if query_academic is not None else self._query_academic
                res = await scan_research_impact_updates(
                    session=db,
                    user_id=user_id,
                    query_academic=should_query
                )

                # Background scheduler catch-up for any unindexed papers
                try:
                    from app.services.vector_index import sync_unindexed_papers
                    recovered_cnt = sync_unindexed_papers(session=db)
                    if recovered_cnt > 0:
                        logger.info("DRIUT scan cycle synchronized %d previously unindexed papers.", recovered_cnt)
                except Exception as rec_err:
                    logger.warning("DRIUT background unindexed paper sync recovery encountered error: %s", rec_err)


                duration = round(time.monotonic() - start_time, 2)
                self._last_run_time = datetime.now(timezone.utc)
                self._last_run_duration_seconds = duration
                self._provider_status = res.get("provider_status", {})
                self._provider_errors = res.get("provider_errors", {})

                if self._provider_errors:
                    self._last_run_status = "partial_failure"
                else:
                    self._last_run_status = "success"

                self._total_scans_completed += 1
                self._last_scan_metrics = {
                    "users_scanned": res.get("users_scanned", 0),
                    "saved_papers_monitored": res.get("saved_papers_monitored", 0),
                    "candidates_evaluated": res.get("candidates_evaluated", 0),
                    "new_alerts_created": res.get("new_alerts_created", 0),
                    "execution_time_seconds": duration
                }

                return {
                    **res,
                    "status": self._last_run_status,
                    "duration_seconds": duration,
                    "papers_evaluated": res.get("candidates_evaluated", 0)
                }

            except Exception as e:
                duration = round(time.monotonic() - start_time, 2)
                self._last_run_time = datetime.now(timezone.utc)
                self._last_run_duration_seconds = duration
                self._last_run_status = "error"
                logger.error("DRIUT scan job encountered an unhandled error: %s", e, exc_info=True)
                return {
                    "status": "error",
                    "error": str(e),
                    "new_alerts_created": 0,
                    "papers_evaluated": 0,
                    "alerts": []
                }
            finally:
                db.close()
                if needs_advisory and lock_conn is not None:
                    self._release_advisory_lock(lock_conn, self._advisory_lock_key)
                self._is_running_scan = False

    def get_status(self) -> Dict[str, Any]:
        """Return real-time scheduler state and provider health metrics."""
        return {
            "is_enabled": self._is_enabled,
            "is_running_scan": self._is_running_scan,
            "interval_minutes": self._interval_minutes,
            "last_run_time": self._last_run_time,
            "last_run_duration_seconds": self._last_run_duration_seconds,
            "last_run_status": self._last_run_status,
            "total_scans_completed": self._total_scans_completed,
            "last_scan_metrics": self._last_scan_metrics,
            "provider_status": self._provider_status,
            "provider_errors": self._provider_errors
        }


# Global singleton scheduler instance
driut_scheduler = DRIUTScheduler()
