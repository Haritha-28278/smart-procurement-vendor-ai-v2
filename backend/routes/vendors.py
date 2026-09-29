"""
Vendors API Routes
CRUD operations for Vendor Registry using direct raw SQL queries with psycopg2 / SQLite fallback.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, EmailStr
from backend.db.connection import get_db_cursor
from backend.routes.auth import get_current_user, require_role

router = APIRouter(prefix="/api/vendors", tags=["Vendors"])


class VendorCreate(BaseModel):
    name: str
    category: str
    pricing: str  # Budget, Moderate, Premium, Enterprise
    certifications: Optional[str] = ""
    past_performance: Optional[str] = ""
    performance_rating: Optional[float] = 4.0
    location: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    website: Optional[str] = None


class VendorUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    pricing: Optional[str] = None
    certifications: Optional[str] = None
    past_performance: Optional[str] = None
    performance_rating: Optional[float] = None
    location: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    website: Optional[str] = None


@router.get("", response_model=List[dict])
def list_vendors(
    category: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    query = "SELECT * FROM vendors WHERE 1=1"
    params = []

    if category and category != "All":
        query += " AND category = %s"
        params.append(category)

    if search:
        query += " AND (LOWER(name) LIKE %s OR LOWER(category) LIKE %s OR LOWER(location) LIKE %s OR LOWER(certifications) LIKE %s)"
        pattern = f"%{search.lower()}%"
        params.extend([pattern, pattern, pattern, pattern])

    query += " ORDER BY id DESC"

    with get_db_cursor() as cur:
        cur.execute(query, tuple(params))
        vendors = cur.fetchall()
        # Convert created_at and performance_rating to clean types
        for v in vendors:
            if "created_at" in v and v["created_at"]:
                v["created_at"] = str(v["created_at"])
            if "performance_rating" in v and v["performance_rating"] is not None:
                v["performance_rating"] = float(v["performance_rating"])
        return vendors


@router.get("/categories")
def get_categories(current_user: dict = Depends(get_current_user)):
    with get_db_cursor() as cur:
        cur.execute("SELECT DISTINCT category FROM vendors ORDER BY category ASC")
        rows = cur.fetchall()
        return [r["category"] for r in rows if r.get("category")]


@router.get("/{vendor_id}")
def get_vendor(vendor_id: int, current_user: dict = Depends(get_current_user)):
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM vendors WHERE id = %s", (vendor_id,))
        vendor = cur.fetchone()
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")
        if "created_at" in vendor and vendor["created_at"]:
            vendor["created_at"] = str(vendor["created_at"])
        if "performance_rating" in vendor and vendor["performance_rating"] is not None:
            vendor["performance_rating"] = float(vendor["performance_rating"])
        return vendor


@router.post("", status_code=status.HTTP_201_CREATED)
def create_vendor(
    vendor: VendorCreate,
    current_user: dict = Depends(require_role(["Admin", "Procurement Manager"])),
):
    with get_db_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO vendors (name, category, pricing, certifications, past_performance, performance_rating, location, contact_email, contact_phone, website)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                vendor.name,
                vendor.category,
                vendor.pricing,
                vendor.certifications or "",
                vendor.past_performance or "",
                vendor.performance_rating if vendor.performance_rating is not None else 4.0,
                vendor.location,
                vendor.contact_email,
                vendor.contact_phone,
                vendor.website,
            ),
        )
        cur.execute("SELECT * FROM vendors WHERE id = (SELECT MAX(id) FROM vendors)")
        created = cur.fetchone()
        if created and "created_at" in created and created["created_at"]:
            created["created_at"] = str(created["created_at"])
        if created and "performance_rating" in created and created["performance_rating"] is not None:
            created["performance_rating"] = float(created["performance_rating"])
        return created


@router.put("/{vendor_id}")
def update_vendor(
    vendor_id: int,
    vendor: VendorUpdate,
    current_user: dict = Depends(require_role(["Admin", "Procurement Manager"])),
):
    with get_db_cursor(commit=True) as cur:
        cur.execute("SELECT * FROM vendors WHERE id = %s", (vendor_id,))
        existing = cur.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Vendor not found")

        fields = []
        params = []
        for k, v in vendor.model_dump(exclude_unset=True).items():
            if v is not None:
                fields.append(f"{k} = %s")
                params.append(v)

        if not fields:
            return existing

        params.append(vendor_id)
        update_sql = f"UPDATE vendors SET {', '.join(fields)} WHERE id = %s"
        cur.execute(update_sql, tuple(params))

        cur.execute("SELECT * FROM vendors WHERE id = %s", (vendor_id,))
        updated = cur.fetchone()
        if updated and "created_at" in updated and updated["created_at"]:
            updated["created_at"] = str(updated["created_at"])
        if updated and "performance_rating" in updated and updated["performance_rating"] is not None:
            updated["performance_rating"] = float(updated["performance_rating"])
        return updated


@router.delete("/{vendor_id}", status_code=status.HTTP_200_OK)
def delete_vendor(
    vendor_id: int,
    current_user: dict = Depends(require_role(["Admin", "Procurement Manager"])),
):
    with get_db_cursor(commit=True) as cur:
        cur.execute("SELECT id FROM vendors WHERE id = %s", (vendor_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Vendor not found")
        cur.execute("DELETE FROM vendors WHERE id = %s", (vendor_id,))
        return {"success": True, "message": f"Vendor #{vendor_id} successfully deleted"}
