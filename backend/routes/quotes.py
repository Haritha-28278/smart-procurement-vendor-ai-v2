"""
Quotes API Routes
Submit, list, and update quotes for RFQs using direct SQL queries.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from backend.db.connection import get_db_cursor
from backend.routes.auth import get_current_user, require_role

router = APIRouter(prefix="/api/quotes", tags=["Quotes"])


class QuoteCreate(BaseModel):
    rfq_id: int
    vendor_id: int
    quote_amount: float
    delivery_timeline_days: int
    proposal_details: Optional[str] = ""


class QuoteStatusUpdate(BaseModel):
    status: str  # Submitted, Shortlisted, Accepted, Rejected


@router.get("", response_model=List[dict])
def list_quotes(
    rfq_id: Optional[int] = None,
    vendor_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
):
    query = """
        SELECT q.*, v.name as vendor_name, v.category as vendor_category,
               r.title as rfq_title, r.budget as rfq_budget
        FROM quotes q
        JOIN vendors v ON q.vendor_id = v.id
        JOIN rfqs r ON q.rfq_id = r.id
        WHERE 1=1
    """
    params = []
    if rfq_id:
        query += " AND q.rfq_id = %s"
        params.append(rfq_id)
    if vendor_id:
        query += " AND q.vendor_id = %s"
        params.append(vendor_id)

    query += " ORDER BY q.id DESC"

    with get_db_cursor() as cur:
        cur.execute(query, tuple(params))
        quotes = cur.fetchall()
        for q in quotes:
            if "created_at" in q and q["created_at"]:
                q["created_at"] = str(q["created_at"])
            if "quote_amount" in q and q["quote_amount"] is not None:
                q["quote_amount"] = float(q["quote_amount"])
            if "rfq_budget" in q and q["rfq_budget"] is not None:
                q["rfq_budget"] = float(q["rfq_budget"])
        return quotes


@router.post("", status_code=status.HTTP_201_CREATED)
def submit_quote(
    quote: QuoteCreate,
    current_user: dict = Depends(get_current_user),
):
    with get_db_cursor(commit=True) as cur:
        # Verify RFQ exists
        cur.execute("SELECT id, status FROM rfqs WHERE id = %s", (quote.rfq_id,))
        rfq = cur.fetchone()
        if not rfq:
            raise HTTPException(status_code=404, detail="RFQ not found")

        # Verify Vendor exists
        cur.execute("SELECT id, name FROM vendors WHERE id = %s", (quote.vendor_id,))
        vendor = cur.fetchone()
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")

        # Check existing quote for this rfq + vendor
        cur.execute("SELECT id FROM quotes WHERE rfq_id = %s AND vendor_id = %s", (quote.rfq_id, quote.vendor_id))
        existing = cur.fetchone()
        if existing:
            # Update existing quote
            cur.execute(
                """
                UPDATE quotes
                SET quote_amount = %s, delivery_timeline_days = %s, proposal_details = %s, status = 'Submitted'
                WHERE id = %s
                """,
                (quote.quote_amount, quote.delivery_timeline_days, quote.proposal_details, existing["id"]),
            )
            quote_id = existing["id"]
        else:
            cur.execute(
                """
                INSERT INTO quotes (rfq_id, vendor_id, quote_amount, delivery_timeline_days, proposal_details, status)
                VALUES (%s, %s, %s, %s, %s, 'Submitted')
                """,
                (quote.rfq_id, quote.vendor_id, quote.quote_amount, quote.delivery_timeline_days, quote.proposal_details),
            )
            cur.execute("SELECT MAX(id) as id FROM quotes")
            quote_id = cur.fetchone()["id"]

        cur.execute(
            """
            SELECT q.*, v.name as vendor_name, r.title as rfq_title
            FROM quotes q
            JOIN vendors v ON q.vendor_id = v.id
            JOIN rfqs r ON q.rfq_id = r.id
            WHERE q.id = %s
            """,
            (quote_id,),
        )
        saved = cur.fetchone()
        if saved:
            if "created_at" in saved and saved["created_at"]:
                saved["created_at"] = str(saved["created_at"])
            if "quote_amount" in saved and saved["quote_amount"] is not None:
                saved["quote_amount"] = float(saved["quote_amount"])
        return saved


@router.patch("/{quote_id}/status")
def update_quote_status(
    quote_id: int,
    status_update: QuoteStatusUpdate,
    current_user: dict = Depends(require_role(["Admin", "Procurement Manager"])),
):
    valid_statuses = ["Submitted", "Shortlisted", "Accepted", "Rejected"]
    if status_update.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of {valid_statuses}",
        )

    with get_db_cursor(commit=True) as cur:
        cur.execute("SELECT * FROM quotes WHERE id = %s", (quote_id,))
        existing = cur.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Quote not found")

        cur.execute("UPDATE quotes SET status = %s WHERE id = %s", (status_update.status, quote_id))

        # If accepted, we can also set RFQ status to 'Awarded'
        if status_update.status == "Accepted":
            cur.execute("UPDATE rfqs SET status = 'Awarded' WHERE id = %s", (existing["rfq_id"],))

        cur.execute("SELECT * FROM quotes WHERE id = %s", (quote_id,))
        updated = cur.fetchone()
        if updated and "created_at" in updated and updated["created_at"]:
            updated["created_at"] = str(updated["created_at"])
        if updated and "quote_amount" in updated and updated["quote_amount"] is not None:
            updated["quote_amount"] = float(updated["quote_amount"])
        return updated


@router.delete("/{quote_id}")
def delete_quote(
    quote_id: int,
    current_user: dict = Depends(require_role(["Admin", "Procurement Manager"])),
):
    with get_db_cursor(commit=True) as cur:
        cur.execute("SELECT id FROM quotes WHERE id = %s", (quote_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Quote not found")
        cur.execute("DELETE FROM quotes WHERE id = %s", (quote_id,))
        return {"success": True, "message": f"Quote #{quote_id} deleted successfully"}
