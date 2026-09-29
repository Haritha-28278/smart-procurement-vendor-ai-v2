"""
RFQ (Request for Quotation) API Routes
Create and manage RFQs with raw SQL queries.
"""

from typing import Optional, List
from datetime import date
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from backend.db.connection import get_db_cursor
from backend.routes.auth import get_current_user, require_role

router = APIRouter(prefix="/api/rfq", tags=["RFQs"])


class RFQCreate(BaseModel):
    title: str
    category: str
    requirements: str
    budget: float
    deadline: date


class RFQUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    requirements: Optional[str] = None
    budget: Optional[float] = None
    deadline: Optional[date] = None
    status: Optional[str] = None  # Open, In Review, Awarded, Closed


@router.get("", response_model=List[dict])
def list_rfqs(
    category: Optional[str] = None,
    status_filter: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    query = """
        SELECT r.*, u.full_name as creator_name,
               (SELECT COUNT(*) FROM quotes q WHERE q.rfq_id = r.id) as quote_count
        FROM rfqs r
        LEFT JOIN users u ON r.created_by = u.id
        WHERE 1=1
    """
    params = []

    if category and category != "All":
        query += " AND r.category = %s"
        params.append(category)

    if status_filter and status_filter != "All":
        query += " AND r.status = %s"
        params.append(status_filter)

    query += " ORDER BY r.id DESC"

    with get_db_cursor() as cur:
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        for r in rows:
            if "deadline" in r and r["deadline"]:
                r["deadline"] = str(r["deadline"])
            if "created_at" in r and r["created_at"]:
                r["created_at"] = str(r["created_at"])
            if "budget" in r and r["budget"] is not None:
                r["budget"] = float(r["budget"])
        return rows


@router.get("/{rfq_id}")
def get_rfq(rfq_id: int, current_user: dict = Depends(get_current_user)):
    with get_db_cursor() as cur:
        cur.execute(
            """
            SELECT r.*, u.full_name as creator_name
            FROM rfqs r
            LEFT JOIN users u ON r.created_by = u.id
            WHERE r.id = %s
            """,
            (rfq_id,),
        )
        rfq = cur.fetchone()
        if not rfq:
            raise HTTPException(status_code=404, detail="RFQ not found")

        # Fetch quotes with vendor info and cached AI score
        cur.execute(
            """
            SELECT q.*, v.name as vendor_name, v.category as vendor_category,
                   v.performance_rating as vendor_rating, v.location as vendor_location,
                   v.pricing as vendor_pricing, v.certifications as vendor_certifications,
                   a.match_score as ai_match_score, a.reasoning as ai_reasoning,
                   a.risk_flags as ai_risk_flags
            FROM quotes q
            JOIN vendors v ON q.vendor_id = v.id
            LEFT JOIN ai_analysis a ON a.rfq_id = q.rfq_id AND a.vendor_id = q.vendor_id
            WHERE q.rfq_id = %s
            ORDER BY q.quote_amount ASC
            """,
            (rfq_id,),
        )
        quotes = cur.fetchall()

        # Clean types
        if "deadline" in rfq and rfq["deadline"]:
            rfq["deadline"] = str(rfq["deadline"])
        if "created_at" in rfq and rfq["created_at"]:
            rfq["created_at"] = str(rfq["created_at"])
        if "budget" in rfq and rfq["budget"] is not None:
            rfq["budget"] = float(rfq["budget"])

        for q in quotes:
            if "created_at" in q and q["created_at"]:
                q["created_at"] = str(q["created_at"])
            if "quote_amount" in q and q["quote_amount"] is not None:
                q["quote_amount"] = float(q["quote_amount"])
            if "vendor_rating" in q and q["vendor_rating"] is not None:
                q["vendor_rating"] = float(q["vendor_rating"])

        rfq["quotes"] = quotes
        return rfq


@router.post("", status_code=status.HTTP_201_CREATED)
def create_rfq(
    rfq_data: RFQCreate,
    current_user: dict = Depends(require_role(["Admin", "Procurement Manager"])),
):
    with get_db_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO rfqs (title, category, requirements, budget, deadline, status, created_by)
            VALUES (%s, %s, %s, %s, %s, 'Open', %s)
            """,
            (
                rfq_data.title,
                rfq_data.category,
                rfq_data.requirements,
                rfq_data.budget,
                rfq_data.deadline,
                current_user["id"],
            ),
        )
        cur.execute("SELECT * FROM rfqs WHERE id = (SELECT MAX(id) FROM rfqs)")
        created = cur.fetchone()
        if created:
            if "deadline" in created and created["deadline"]:
                created["deadline"] = str(created["deadline"])
            if "created_at" in created and created["created_at"]:
                created["created_at"] = str(created["created_at"])
            if "budget" in created and created["budget"] is not None:
                created["budget"] = float(created["budget"])
        return created


@router.put("/{rfq_id}")
def update_rfq(
    rfq_id: int,
    rfq_data: RFQUpdate,
    current_user: dict = Depends(require_role(["Admin", "Procurement Manager"])),
):
    with get_db_cursor(commit=True) as cur:
        cur.execute("SELECT * FROM rfqs WHERE id = %s", (rfq_id,))
        existing = cur.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="RFQ not found")

        fields = []
        params = []
        for k, v in rfq_data.model_dump(exclude_unset=True).items():
            if v is not None:
                fields.append(f"{k} = %s")
                params.append(v)

        if not fields:
            return existing

        params.append(rfq_id)
        update_sql = f"UPDATE rfqs SET {', '.join(fields)} WHERE id = %s"
        cur.execute(update_sql, tuple(params))

        cur.execute("SELECT * FROM rfqs WHERE id = %s", (rfq_id,))
        updated = cur.fetchone()
        if updated:
            if "deadline" in updated and updated["deadline"]:
                updated["deadline"] = str(updated["deadline"])
            if "created_at" in updated and updated["created_at"]:
                updated["created_at"] = str(updated["created_at"])
            if "budget" in updated and updated["budget"] is not None:
                updated["budget"] = float(updated["budget"])
        return updated


@router.delete("/{rfq_id}")
def delete_rfq(
    rfq_id: int,
    current_user: dict = Depends(require_role(["Admin", "Procurement Manager"])),
):
    with get_db_cursor(commit=True) as cur:
        cur.execute("SELECT id FROM rfqs WHERE id = %s", (rfq_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="RFQ not found")
        cur.execute("DELETE FROM rfqs WHERE id = %s", (rfq_id,))
        return {"success": True, "message": f"RFQ #{rfq_id} deleted successfully"}
