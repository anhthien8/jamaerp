"""
Background task worker for JAMA HOME CRM.

Handles periodic lead scoring, task coordination, and insight generation.
Structured for easy migration to Redis/Celery or similar task queue.
"""

import asyncio
import logging
import signal
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Optional
from zoneinfo import ZoneInfo

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class WorkerTask:
    task_id: str
    name: str
    coroutine: Callable[..., Coroutine]
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    result: Any = None
    error: Optional[str] = None


class BackgroundWorker:
    """In-memory asyncio-based background task worker.

    Designed with a queue abstraction so the storage backend can be swapped
    for Redis, RabbitMQ, or another broker without touching task logic.
    """

    def __init__(
        self,
        lead_scoring_interval: int = 3600,  # 1 hour
        insight_generation_interval: int = 86400,  # 24 hours
        health_check_interval: int = 30,
        max_concurrent_tasks: int = 5,
    ):
        # --- queue abstraction (swap for redis/brpop in the future) ---
        self.task_queue: deque[WorkerTask] = deque()
        self.completed_tasks: deque[WorkerTask] = deque(maxlen=200)
        self.failed_tasks: deque[WorkerTask] = deque(maxlen=200)

        # --- lifecycle ---
        self.running = False
        self._shutdown_event: Optional[asyncio.Event] = None
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)

        # --- periodic intervals (seconds) ---
        self.lead_scoring_interval = lead_scoring_interval
        self.insight_generation_interval = insight_generation_interval
        self.health_check_interval = health_check_interval

        # --- tracking ---
        self._last_lead_scoring: float = 0.0
        self._last_insight_generation: float = 0.0
        self._last_automation_date: str = ""      # "YYYY-MM-DD" (VN time)
        self._last_bod_report_date: str = ""      # "YYYY-MM-DD" (VN time)
        self._last_backup_date: str = ""          # "YYYY-MM-DD" (VN time)
        self._start_time: float = 0.0
        self._tasks_processed: int = 0
        self._tasks_failed: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enqueue_task(
        self,
        name: str,
        coroutine: Callable[..., Coroutine],
        *args: Any,
        priority: TaskPriority = TaskPriority.NORMAL,
        **kwargs: Any,
    ) -> WorkerTask:
        """Add a task to the in-memory queue."""
        task_id = f"task-{self._tasks_processed + len(self.task_queue) + 1}"
        worker_task = WorkerTask(
            task_id=task_id,
            name=name,
            coroutine=coroutine,
            args=args,
            kwargs=kwargs,
            priority=priority,
        )
        self.task_queue.append(worker_task)
        # Re-sort by priority (highest first)
        sorted_queue = sorted(self.task_queue, key=lambda t: t.priority.value, reverse=True)
        self.task_queue = deque(sorted_queue)
        logger.info("Enqueued task %s [%s] (priority=%s)", task_id, name, priority.name)
        return worker_task

    async def start(self) -> None:
        """Main entry point. Blocks until shutdown signal is received."""
        self.running = True
        self._shutdown_event = asyncio.Event()
        self._start_time = time.time()

        logger.info("Background worker starting up...")
        self._install_signal_handlers()

        # Run all loops concurrently until shutdown
        await asyncio.gather(
            self._process_queue_loop(),
            self._periodic_tasks(),
            self._health_check_loop(),
            self._shutdown_event.wait(),
        )

        logger.info("Background worker shut down gracefully.")

    async def stop(self) -> None:
        """Signal the worker to stop."""
        logger.info("Shutdown signal received -- stopping worker...")
        self.running = False
        if self._shutdown_event:
            self._shutdown_event.set()

    def get_health(self) -> dict[str, Any]:
        """Return a health snapshot suitable for a /healthz endpoint."""
        uptime = time.time() - self._start_time if self._start_time else 0
        return {
            "status": "healthy" if self.running else "stopped",
            "uptime_seconds": round(uptime, 2),
            "queue_depth": len(self.task_queue),
            "tasks_processed": self._tasks_processed,
            "tasks_failed": self._tasks_failed,
            "completed_recent": len(self.completed_tasks),
            "failed_recent": len(self.failed_tasks),
        }

    # ------------------------------------------------------------------
    # Queue processing loop
    # ------------------------------------------------------------------

    async def _process_queue_loop(self) -> None:
        """Continuously drain tasks from the queue."""
        while self.running:
            if not self.task_queue:
                await asyncio.sleep(0.1)
                continue

            worker_task = self.task_queue.popleft()
            worker_task.status = TaskStatus.RUNNING

            async with self._semaphore:
                try:
                    logger.info(
                        "Running task %s [%s]", worker_task.task_id, worker_task.name
                    )
                    result = await worker_task.coroutine(*worker_task.args, **worker_task.kwargs)
                    worker_task.status = TaskStatus.COMPLETED
                    worker_task.result = result
                    self.completed_tasks.append(worker_task)
                    self._tasks_processed += 1
                    logger.info("Task %s completed successfully.", worker_task.task_id)
                except Exception as exc:
                    worker_task.status = TaskStatus.FAILED
                    worker_task.error = str(exc)
                    self.failed_tasks.append(worker_task)
                    self._tasks_failed += 1
                    logger.exception("Task %s failed: %s", worker_task.task_id, exc)

    # ------------------------------------------------------------------
    # Periodic task scheduler
    # ------------------------------------------------------------------

    async def _periodic_tasks(self) -> None:
        """Schedule recurring jobs at their configured intervals."""
        now = time.time()
        self._last_lead_scoring = now
        self._last_insight_generation = now

        while self.running:
            await asyncio.sleep(1)
            now = time.time()

            # --- auto-score new leads every N seconds ---
            if now - self._last_lead_scoring >= self.lead_scoring_interval:
                self._last_lead_scoring = now
                self.enqueue_task(
                    "lead_scoring",
                    process_lead_scoring,
                    priority=TaskPriority.NORMAL,
                )

            # --- daily insight generation ---
            if now - self._last_insight_generation >= self.insight_generation_interval:
                self._last_insight_generation = now
                self.enqueue_task(
                    "insight_generation",
                    process_insights,
                    priority=TaskPriority.LOW,
                )

            # --- daily CSKH automation + BOD reports (VN time-of-day) ---
            vn_now = datetime.now(VN_TZ)
            today_str = vn_now.strftime("%Y-%m-%d")

            # CSKH automation runs once per day at 07:00 VN
            if vn_now.hour >= 7 and self._last_automation_date != today_str:
                self._last_automation_date = today_str
                self.enqueue_task(
                    "cskh_automation",
                    process_automation,
                    priority=TaskPriority.HIGH,
                )

            # Daily backup at configured hour (default 05:00 VN)
            if self._last_backup_date != today_str:
                backup_hour = await _get_backup_hour()
                if backup_hour is not None and vn_now.hour >= backup_hour:
                    self._last_backup_date = today_str
                    self.enqueue_task(
                        "daily_backup",
                        process_backup,
                        priority=TaskPriority.HIGH,
                    )

            # BOD report at configured hour (default 08:00 VN)
            if self._last_bod_report_date != today_str:
                bod_hour = await _get_bod_report_hour()
                if bod_hour is not None and vn_now.hour >= bod_hour:
                    self._last_bod_report_date = today_str
                    self.enqueue_task(
                        "bod_report",
                        process_bod_reports,
                        vn_now,
                        priority=TaskPriority.NORMAL,
                    )

    # ------------------------------------------------------------------
    # Health check loop (for Docker HEALTHCHECK / monitoring)
    # ------------------------------------------------------------------

    async def _health_check_loop(self) -> None:
        """Periodically log a health snapshot."""
        while self.running:
            await asyncio.sleep(self.health_check_interval)
            health = self.get_health()
            logger.info(
                "Health check | status=%s uptime=%.0fs queue=%d processed=%d failed=%d",
                health["status"],
                health["uptime_seconds"],
                health["queue_depth"],
                health["tasks_processed"],
                health["tasks_failed"],
            )

    # ------------------------------------------------------------------
    # Signal handling
    # ------------------------------------------------------------------

    def _install_signal_handlers(self) -> None:
        """Register SIGTERM / SIGINT for graceful shutdown on Linux/macOS.
        On Windows these signals behave differently, so we fall back to
        asyncio's default Ctrl+C handling.
        """
        loop = asyncio.get_running_loop()

        if sys.platform != "win32":
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
        # else: on Windows, rely on KeyboardInterrupt from Ctrl+C
        # add_signal_handler is unreliable for SIGINT on Windows

    # ------------------------------------------------------------------
    # Task coordination helpers
    # ------------------------------------------------------------------

    async def run_task_coordination(self) -> dict[str, Any]:
        """Coordinate pending CRM tasks (reminders, follow-ups, escalations)."""
        logger.info("Running task coordination...")
        try:
            from app.agents.task_coordinator import coordinate_tasks
            result = await coordinate_tasks()
            return {"status": "completed", "result": result}
        except Exception as exc:
            logger.exception("Task coordination failed: %s", exc)
            return {"status": "failed", "error": str(exc)}


# ======================================================================
# Top-level task coroutines (imported by the periodic scheduler)
# ======================================================================

async def process_lead_scoring() -> dict[str, Any]:
    """Score all un-scored or recently updated leads."""
    logger.info("Starting lead scoring batch...")
    try:
        from app.agents.lead_scoring import score_lead_agent
        from app.database import async_session
        from app.models.lead import Lead
        from sqlalchemy import select

        scored = 0
        async with async_session() as session:
            # Query leads that haven't been scored yet or were updated recently
            result = await session.execute(
                select(Lead).where(
                    (Lead.ai_score.is_(None)) | (Lead.ai_score == 0)
                ).limit(20)
            )
            leads = result.scalars().all()

            for lead in leads:
                try:
                    await score_lead_agent(str(lead.id), session)
                    scored += 1
                except Exception as e:
                    logger.warning("Failed to score lead %s: %s", lead.id, e)

        logger.info("Lead scoring batch finished: %d leads scored.", scored)
        return {"status": "completed", "scored": scored}
    except Exception as exc:
        logger.exception("Lead scoring failed: %s", exc)
        return {"status": "failed", "error": str(exc)}


async def process_task_coordination() -> dict[str, Any]:
    """Coordinate and dispatch pending CRM tasks."""
    logger.info("Starting task coordination...")
    try:
        from app.agents.task_coordinator import coordinate_tasks
        from app.database import async_session
        from app.models.project import Project, Task
        from sqlalchemy import select, func

        coordinated = 0
        async with async_session() as session:
            # Find projects that have no tasks yet
            subq = (
                select(Task.project_id)
                .group_by(Task.project_id)
                .subquery()
            )
            result = await session.execute(
                select(Project).where(
                    ~Project.id.in_(select(subq.c.project_id))
                ).limit(10)
            )
            projects = result.scalars().all()

            for project in projects:
                try:
                    await coordinate_tasks(str(project.id), session)
                    coordinated += 1
                except Exception as e:
                    logger.warning("Failed to coordinate tasks for project %s: %s", project.id, e)

        logger.info("Task coordination finished: %d projects processed.", coordinated)
        return {"status": "completed", "coordinated": coordinated}
    except Exception as exc:
        logger.exception("Task coordination failed: %s", exc)
        return {"status": "failed", "error": str(exc)}


async def _get_bod_report_hour() -> Optional[int]:
    """Return configured BOD report hour, or None when reporting is disabled."""
    try:
        from app.database import async_session
        from app.services.automation import get_automation_settings

        async with async_session() as session:
            settings = await get_automation_settings(session)
        if settings.get("bod_report_enabled", "true") != "true":
            return None
        return max(0, min(23, int(settings.get("bod_report_hour", "8"))))
    except Exception as exc:
        logger.warning("Could not load BOD report settings: %s", exc)
        return 8


async def _get_backup_hour() -> Optional[int]:
    """Return configured backup hour, or None when backup is disabled."""
    try:
        from app.database import async_session
        from app.services.backup_service import get_backup_settings

        async with async_session() as session:
            cfg = await get_backup_settings(session)
        if cfg.get("backup_enabled", "true") != "true":
            return None
        return max(0, min(23, int(cfg.get("backup_hour", "5"))))
    except Exception as exc:
        logger.warning("Could not load backup settings: %s", exc)
        return 5


async def process_backup() -> dict[str, Any]:
    """Run daily database backup (local + Google Drive) with retention."""
    logger.info("Starting daily backup...")
    try:
        from app.database import async_session
        from app.services.backup_service import run_backup

        async with async_session() as session:
            result = await run_backup(session)
        logger.info("Daily backup finished: %s", result.get("status"))
        return {"status": "completed", "result": result}
    except Exception as exc:
        logger.exception("Daily backup failed: %s", exc)
        return {"status": "failed", "error": str(exc)}


async def process_automation() -> dict[str, Any]:
    """Run CSKH automation: follow-up reminders, lead recall, payment reminders."""
    logger.info("Starting CSKH automation batch...")
    try:
        from app.database import async_session
        from app.services.automation import run_all_automation

        async with async_session() as session:
            result = await run_all_automation(session)
        logger.info("CSKH automation finished: %s", result)
        return {"status": "completed", "result": result}
    except Exception as exc:
        logger.exception("CSKH automation failed: %s", exc)
        return {"status": "failed", "error": str(exc)}


async def process_bod_reports(vn_now: datetime) -> dict[str, Any]:
    """Send BOD reports: daily always; weekly on Monday; monthly on the 1st."""
    logger.info("Starting BOD report delivery...")
    try:
        from app.database import async_session
        from app.services.bod_report import send_bod_report

        results: dict[str, Any] = {}
        async with async_session() as session:
            results["daily"] = await send_bod_report(session, "daily")
            if vn_now.weekday() == 0:  # Monday
                results["weekly"] = await send_bod_report(session, "weekly")
            if vn_now.day == 1:
                results["monthly"] = await send_bod_report(session, "monthly")

            # Briefing nhóm công ty (không kèm tài chính)
            from app.services.bod_report import send_group_briefing
            results["group_briefing"] = await send_group_briefing(session)

        logger.info("BOD report delivery finished: %s", list(results.keys()))
        return {"status": "completed", "result": results}
    except Exception as exc:
        logger.exception("BOD report delivery failed: %s", exc)
        return {"status": "failed", "error": str(exc)}


async def process_insights() -> dict[str, Any]:
    """Generate daily pipeline and performance insights."""
    logger.info("Starting daily insight generation...")
    try:
        from app.agents.insight_agent import generate_insights
        from app.database import async_session

        async with async_session() as session:
            result = await generate_insights(session)
        logger.info("Insight generation finished.")
        return {"status": "completed", "result": result}
    except Exception as exc:
        logger.exception("Insight generation failed: %s", exc)
        return {"status": "failed", "error": str(exc)}


# ======================================================================
# Module-level singleton & convenience alias
# ======================================================================

_worker: Optional[BackgroundWorker] = None


def get_worker() -> BackgroundWorker:
    """Return (and lazily create) the module-level worker singleton."""
    global _worker
    if _worker is None:
        _worker = BackgroundWorker()
    return _worker


async def start() -> None:
    """Convenience entry point -- used by ``python -m app.worker``."""
    worker = get_worker()
    await worker.start()


# ======================================================================
# CLI entry point
# ======================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    try:
        asyncio.run(start())
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
