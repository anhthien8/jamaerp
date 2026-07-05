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
    from app.models import User, Team, Lead, Activity, Project, Task, TaskActivity, Transaction, Commission, Payroll  # noqa
    from app.models import Customer, Material, MaterialUsage  # noqa — ERP models
    from app.models import SalaryGrade, FixedCost, VariableCost, CommissionStructure  # noqa
    from app.api.telegram_workflow import MaterialRequest  # noqa — ensure table created
    from app.models.contract import Contract  # noqa
    from app.models.quotation import Quotation  # noqa

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Auto-seed
    from app.database import async_session
    from app.seed import seed_database
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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}


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
