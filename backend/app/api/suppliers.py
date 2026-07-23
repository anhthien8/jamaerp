"""Suppliers API — NCC management & price comparison."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.supplier import Supplier, SupplierQuote, PriceComparison
from app.schemas.supplier import (
    SupplierCreate,
    SupplierUpdate,
    SupplierResponse,
    SupplierQuoteCreate,
    SupplierQuoteResponse,
    CompareRequest,
)

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


def _escape_like(term: str) -> str:
    return term.replace("%", "\\%").replace("_", "\\_")


def require_supplier_write(current_user: User = Depends(get_current_user)) -> User:
    """Only admin and supervisor (purchasing) can create/edit suppliers."""
    if current_user.role not in ("admin", "supervisor"):
        raise HTTPException(
            status_code=403,
            detail="Không có quyền chỉnh sửa thông tin nhà cung cấp",
        )
    return current_user


# ---------------------------------------------------------------------------
# Supplier CRUD
# ---------------------------------------------------------------------------


@router.get("")
async def list_suppliers(
    search: str | None = None,
    category: str | None = None,
    region: str | None = None,
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List all suppliers with optional filters."""
    q = select(Supplier).order_by(Supplier.name)
    if search:
        escaped = _escape_like(search)
        q = q.where(
            Supplier.name.ilike(f"%{escaped}%", escape="\\")
            | Supplier.contact_name.ilike(f"%{escaped}%", escape="\\")
        )
    if category:
        q = q.where(Supplier.category == category)
    if region:
        q = q.where(Supplier.region == region)
    if is_active is not None:
        q = q.where(Supplier.is_active == is_active)

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    suppliers = result.scalars().all()

    return {
        "items": [SupplierResponse.model_validate(s) for s in suppliers],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.post("", response_model=SupplierResponse)
async def create_supplier(
    data: SupplierCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_supplier_write),
):
    """Create a new supplier."""
    supplier = Supplier(**data.model_dump())
    db.add(supplier)
    await db.flush()
    return SupplierResponse.model_validate(supplier)


@router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get supplier detail."""
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Nhà cung cấp không tồn tại")
    return SupplierResponse.model_validate(supplier)


@router.put("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: str,
    data: SupplierUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_supplier_write),
):
    """Update supplier."""
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Nhà cung cấp không tồn tại")

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(supplier, k, v)
    supplier.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return SupplierResponse.model_validate(supplier)


# ---------------------------------------------------------------------------
# Supplier Quotes
# ---------------------------------------------------------------------------


@router.get("/{supplier_id}/quotes")
async def list_supplier_quotes(
    supplier_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all price quotes for a supplier."""
    # Verify supplier exists
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Nhà cung cấp không tồn tại")

    q = (
        select(SupplierQuote)
        .where(SupplierQuote.supplier_id == supplier_id)
        .order_by(desc(SupplierQuote.quote_date))
    )
    result = await db.execute(q)
    quotes = result.scalars().all()
    return {
        "items": [SupplierQuoteResponse.model_validate(q) for q in quotes],
        "total": len(quotes),
    }


@router.post("/{supplier_id}/quotes", response_model=SupplierQuoteResponse)
async def create_supplier_quote(
    supplier_id: str,
    data: SupplierQuoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_supplier_write),
):
    """Add a price quote for a supplier."""
    # Verify supplier exists
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Nhà cung cấp không tồn tại")

    quote = SupplierQuote(supplier_id=supplier_id, **data.model_dump())
    db.add(quote)
    await db.flush()
    return SupplierQuoteResponse.model_validate(quote)


# ---------------------------------------------------------------------------
# Price Comparison
# ---------------------------------------------------------------------------


@router.post("/compare")
async def compare_prices(
    data: CompareRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compare prices across suppliers for a list of materials."""
    results = []
    for mat_name in data.materials:
        # Get latest quotes for each supplier for this material
        q = (
            select(SupplierQuote, Supplier.name.label("supplier_name"))
            .join(Supplier, SupplierQuote.supplier_id == Supplier.id)
            .where(SupplierQuote.material_name == mat_name)
            .where(Supplier.is_active == True)
            .order_by(desc(SupplierQuote.quote_date))
        )
        result = await db.execute(q)
        rows = result.all()

        # Deduplicate: keep only the latest quote per supplier
        seen_suppliers: dict[str, tuple[SupplierQuote, str]] = {}
        for quote, supplier_name in rows:
            if quote.supplier_id not in seen_suppliers:
                seen_suppliers[quote.supplier_id] = (quote, supplier_name)

        quotes = []
        best_price = None
        best_supplier_id = None
        best_supplier_name = None

        for sid, (quote, sname) in seen_suppliers.items():
            quotes.append({
                "supplier_id": sid,
                "supplier_name": sname,
                "unit_price": quote.unit_price,
                "unit": quote.unit,
                "min_quantity": quote.min_quantity,
                "lead_time_days": quote.lead_time_days,
                "quote_date": quote.quote_date.isoformat(),
            })
            if best_price is None or quote.unit_price < best_price:
                best_price = quote.unit_price
                best_supplier_id = sid
                best_supplier_name = sname

        # Sort by price ascending
        quotes.sort(key=lambda x: x["unit_price"])

        results.append({
            "material_name": mat_name,
            "quote_count": len(quotes),
            "best_supplier_id": best_supplier_id,
            "best_supplier_name": best_supplier_name,
            "best_price": best_price,
            "quotes": quotes,
        })

    return {"comparisons": results}


@router.get("/price-history/{material_name:path}")
async def price_history(
    material_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get price history for a material across all suppliers."""
    q = (
        select(SupplierQuote, Supplier.name.label("supplier_name"))
        .join(Supplier, SupplierQuote.supplier_id == Supplier.id)
        .where(SupplierQuote.material_name == material_name)
        .order_by(desc(SupplierQuote.quote_date))
    )
    result = await db.execute(q)
    rows = result.all()

    history = []
    for quote, supplier_name in rows:
        history.append({
            "id": quote.id,
            "supplier_id": quote.supplier_id,
            "supplier_name": supplier_name,
            "unit_price": quote.unit_price,
            "unit": quote.unit,
            "min_quantity": quote.min_quantity,
            "lead_time_days": quote.lead_time_days,
            "quote_date": quote.quote_date.isoformat(),
            "notes": quote.notes,
        })

    return {
        "material_name": material_name,
        "total": len(history),
        "history": history,
    }
