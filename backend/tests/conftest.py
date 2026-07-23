"""Shared test fixtures — async SQLite DB, test client, seeded data."""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.database import Base, get_db
from app.main import app
from app.middleware.auth import create_access_token, hash_password

# ---------------------------------------------------------------------------
# Import every model so Base.metadata knows about all tables
# ---------------------------------------------------------------------------
from app.models.user import User, Team  # noqa
from app.models.lead import Lead, Activity  # noqa
from app.models.project import Project, Task, TaskActivity  # noqa
from app.models.contract import Contract  # noqa
from app.models.quotation import Quotation  # noqa
from app.models.inventory import Material, MaterialUsage  # noqa
from app.models.payroll import Transaction, Commission, Payroll  # noqa
from app.models.customer import Customer  # noqa
from app.models.salary_grade import SalaryGrade  # noqa
from app.models.fixed_cost import FixedCost  # noqa
from app.models.variable_cost import VariableCost  # noqa
from app.models.commission_structure import CommissionStructure  # noqa
from app.models.notification import Notification, SystemSetting  # noqa
from app.models.pricing import PriceItem  # noqa
from app.models.audit import AuditLog  # noqa
from app.models.attendance import AttendanceRecord  # noqa
from app.models.approval import ApprovalRequest  # noqa
from app.models.leave import LeaveBalance, LeaveRequest  # noqa
from app.models.zalo import ZaloSession, ZaloGroup, ZaloMessage, ZaloSignal  # noqa
from app.models.payroll import SalaryAdvance  # noqa
from app.api.telegram_workflow import MaterialRequest  # noqa
from app.models.supplier import Supplier, SupplierQuote, PriceComparison  # noqa


# ---------------------------------------------------------------------------
# Reset in-memory login rate-limiter between tests so attempts don't leak
# across tests sharing the same client IP (avoids spurious 429s).
# ---------------------------------------------------------------------------
from app.api.auth import _login_attempts, _reset_codes  # noqa


@pytest.fixture(autouse=True)
def _reset_login_rate_limit():
    _login_attempts.clear()
    _reset_codes.clear()
    yield
    _login_attempts.clear()
    _reset_codes.clear()


# ---------------------------------------------------------------------------
# Engine & session factory per test
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


async def _override_get_db(db_session):
    yield db_session


@pytest_asyncio.fixture
async def client(db_engine, db_session):
    """AsyncClient wired to a fresh in-memory SQLite DB.

    Uses the same session as ``db_session`` so that ``flush()``-only
    endpoints leave data visible to direct DB queries in tests.
    """
    async def _get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# User helpers
# ---------------------------------------------------------------------------

def _uid() -> str:
    return str(uuid.uuid4())


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    user = User(
        id=_uid(),
        full_name="Admin Test",
        email="admin@test.com",
        password_hash=hash_password("admin123"),
        role="admin",
        department="EXEC",
        is_active=True,
        telegram_user_id=900001,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def accountant_user(db_session: AsyncSession) -> User:
    user = User(
        id=_uid(),
        full_name="Accountant Test",
        email="accountant@test.com",
        password_hash=hash_password("acct123"),
        role="accountant",
        department="ACCT",
        is_active=True,
        telegram_user_id=900002,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def sales_user(db_session: AsyncSession) -> User:
    user = User(
        id=_uid(),
        full_name="Sales Test",
        email="sales@test.com",
        password_hash=hash_password("sales123"),
        role="data_entry",
        department="SALES",
        is_active=True,
        telegram_user_id=900003,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def designer_user(db_session: AsyncSession) -> User:
    user = User(
        id=_uid(),
        full_name="Supervisor Test",
        email="supervisor@test.com",
        password_hash=hash_password("super123"),
        role="supervisor",
        department="OPS",
        is_active=True,
        telegram_user_id=900004,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def purchasing_user(db_session: AsyncSession) -> User:
    user = User(
        id=_uid(),
        full_name="Supervisor Test 2",
        email="supervisor2@test.com",
        password_hash=hash_password("super123"),
        role="supervisor",
        department="OPS",
        is_active=True,
        telegram_user_id=900005,
    )
    db_session.add(user)
    await db_session.commit()
    return user


def auth_header(user: User, role: str | None = None) -> dict[str, str]:
    token = create_access_token(str(user.id), role or user.role, user.department)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Project fixture (used by P&L and Telegram tests)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def project(db_session: AsyncSession, admin_user: User) -> Project:
    proj = Project(
        id=_uid(),
        code="JMH-TEST",
        name="Test Project Alpha",
        client_name="Nguyen Van A",
        client_phone="0901234567",
        address="123 Le Loi, Q1, HCMC",
        stage="design",
        status="active",
        total_value=5_000_000_000,
        spent=1_200_000_000,
        progress=30,
        pm_id=admin_user.id,
        designer_id=admin_user.id,
        sales_id=admin_user.id,
    )
    db_session.add(proj)

    # Seed 3 tasks
    for i, title in enumerate(["Thiet ke 2D", "Thiet ke 3D", "Hoan thanh"], start=1):
        task = Task(
            id=_uid(),
            project_id=proj.id,
            title=title,
            status="in_progress" if i == 2 else ("done" if i == 1 else "not_started"),
            stage="design",
            order=i,
        )
        db_session.add(task)

    await db_session.commit()
    return proj


@pytest_asyncio.fixture
async def project_with_financials(
    db_session: AsyncSession, project: Project, admin_user: User
) -> Project:
    """Project seeded with a signed contract + material usage + transaction."""
    # Signed contract = revenue
    contract = Contract(
        id=_uid(),
        code="HD-TEST-001",
        project_id=project.id,
        title="Hop dong thiet ke",
        status="signed",
        total_value=4_500_000_000,
    )
    db_session.add(contract)

    # Material usage = cost
    material = Material(
        id=_uid(),
        code="MAT-001",
        name="Go oc cho",
        category="wood",
        unit="m2",
        unit_price=150_000,
        quantity_in_stock=100,
    )
    db_session.add(material)
    await db_session.flush()

    usage = MaterialUsage(
        id=_uid(),
        material_id=material.id,
        project_id=project.id,
        quantity=20,
        unit_price_at_use=150_000,
        total_cost=3_000_000,
        date=datetime.now(timezone.utc),
    )
    db_session.add(usage)

    # Transaction expense
    txn = Transaction(
        id=_uid(),
        code="TXN-TEST-001",
        type="expense",
        category="labor",
        description="Nhan cong thi cong",
        amount=500_000_000,
        project_id=project.id,
        created_by=admin_user.id,
        status="completed",
        date=datetime.now(timezone.utc),
    )
    db_session.add(txn)

    await db_session.commit()
    return project
