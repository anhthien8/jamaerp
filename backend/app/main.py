"""JAMA HOME CRM Backend — FastAPI entry point."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import engine, Base

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App startup/shutdown hooks."""
    # Import all models so Base.metadata knows them
    from app.models import User, Team, Lead, Activity, Project, Task, TaskActivity, Transaction, Commission, Payroll, SalaryAdvance  # noqa
    from app.models import Customer, Material, MaterialUsage  # noqa — ERP models
    from app.models import SalaryGrade, FixedCost, VariableCost, CommissionStructure  # noqa
    from app.api.telegram_workflow import MaterialRequest  # noqa — ensure table created
    from app.models.contract import Contract  # noqa
    from app.models.quotation import Quotation  # noqa
    from app.models.notification import Notification, SystemSetting  # noqa
    from app.models.pricing import PriceItem  # noqa
    from app.models.audit import AuditLog  # noqa
    from app.models.attendance import AttendanceRecord  # noqa
    from app.models.approval import ApprovalRequest  # noqa
    from app.models.leave import LeaveBalance, LeaveRequest  # noqa
    from app.models.performance import KpiSnapshot, CoachingNote, ReviewCycle  # noqa

    # Migrate TRƯỚC create_all — thêm cột mới vào bảng cũ (create_all không làm được)
    from app.migrate import run_migrations
    await run_migrations()

    # Create tables (no-op với bảng đã có; vẫn cần cho test/in-memory DB)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Security: ensure JWT secret is configured & strong
    _weak_secrets = {"change-me-to-a-random-64-char-string", "secret", "changeme"}
    if not settings.JWT_SECRET_KEY:
        print("[FATAL] JWT_SECRET_KEY is not set. Please set it in .env — refusing to start.")
        raise RuntimeError("JWT_SECRET_KEY must be set in environment")
    if settings.JWT_SECRET_KEY in _weak_secrets or len(settings.JWT_SECRET_KEY) < 32:
        print("[FATAL] JWT_SECRET_KEY is weak/placeholder. Generate a random 64-char string — refusing to start.")
        raise RuntimeError("JWT_SECRET_KEY must be a strong random value (>= 32 chars)")
    # Warn (không chặn) nếu bot auth chưa có bí mật chia sẻ
    if settings.TELEGRAM_BOT_TOKEN and not settings.TELEGRAM_AUTH_SECRET:
        print("[WARN] TELEGRAM_AUTH_SECRET chưa đặt — /auth/telegram chỉ dựa rate-limit. Nên đặt bí mật chia sẻ với bot.")

    # Auto-seed (skip in production)
    from app.database import async_session
    from app.seed import seed_database
    if settings.APP_ENV == "production":
        print("[INFO] Skipping database seed in production environment")
    else:
        async with async_session() as db:
            try:
                await seed_database(db)
                await db.commit()
            except Exception as e:
                print(f"[WARN] Seed error: {e}")
                await db.rollback()

    print(f"[OK] {settings.APP_NAME} started")
    yield
    print(f"[STOP] {settings.APP_NAME} stopped")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Security headers — áp cho mọi response
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# Health check
@app.get("/health")
async def health():
    from sqlalchemy import text
    from app.database import async_session
    try:
        async with async_session() as db:
            await db.execute(text("SELECT 1"))
    except Exception:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"status": "error", "app": settings.APP_NAME})
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/")
async def root():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "developer": "Dương Anh Thiện",
    }


# Register routers
from app.api.auth import router as auth_router
from app.api.leads import router as leads_router
from app.api.projects import router as projects_router
from app.api.dashboard import router as dashboard_router
from app.api.accounting import router as accounting_router
from app.api.ai import router as ai_router
from app.api.users import router as users_router
from app.api.customers import router as customers_router
from app.api.contracts import router as contracts_router
from app.api.quotations import router as quotations_router
from app.api.inventory import router as inventory_router
from app.api.pl import router as pl_router
from app.api.salary_grades import router as salary_grades_router
from app.api.fixed_costs import router as fixed_costs_router
from app.api.variable_costs import router as variable_costs_router
from app.api.commission_structures import router as commission_structures_router
from app.api.telegram_workflow import router as telegram_workflow_router
from app.api.notifications import router as notifications_router
from app.api.automation import router as automation_router
from app.api.ai_settings import router as ai_settings_router
from app.api.backup import router as backup_router
from app.api.instant_quote import router as instant_quote_router
from app.api.hr import router as hr_router
from app.api.kpi import router as kpi_router

app.include_router(auth_router, prefix="/api/v1")
app.include_router(leads_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(accounting_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(customers_router, prefix="/api/v1")
app.include_router(contracts_router, prefix="/api/v1")
app.include_router(quotations_router, prefix="/api/v1")
app.include_router(inventory_router, prefix="/api/v1")
app.include_router(pl_router, prefix="/api/v1")
app.include_router(salary_grades_router, prefix="/api/v1")
app.include_router(fixed_costs_router, prefix="/api/v1")
app.include_router(variable_costs_router, prefix="/api/v1")
app.include_router(commission_structures_router, prefix="/api/v1")
app.include_router(telegram_workflow_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(automation_router, prefix="/api/v1")
app.include_router(ai_settings_router, prefix="/api/v1")
app.include_router(backup_router, prefix="/api/v1")
app.include_router(instant_quote_router, prefix="/api/v1")
app.include_router(hr_router, prefix="/api/v1")
app.include_router(kpi_router, prefix="/api/v1")

from app.api.feedback import router as feedback_router
app.include_router(feedback_router, prefix="/api/v1")

from app.api.audit import router as audit_router
app.include_router(audit_router, prefix="/api/v1")

from app.api.attendance import router as attendance_router
app.include_router(attendance_router, prefix="/api/v1")

from app.api.approvals import router as approvals_router
app.include_router(approvals_router, prefix="/api/v1")

from app.api.leaves import router as leaves_router
app.include_router(leaves_router, prefix="/api/v1")

from app.api.payroll import router as payroll_router
app.include_router(payroll_router, prefix="/api/v1")
