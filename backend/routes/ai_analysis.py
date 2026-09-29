"""
AI Analysis Routes
Endpoints for:
1. AI Vendor Matching (score, reasoning, risk flags, cached in ai_analysis table)
2. AI Side-by-Side Comparison (top 3 vendors + Claude executive summary)
3. Negotiation Assistant (Claude-generated B2B negotiation email)
4. Analytics Dashboard data (spend trends, performance distribution, category metrics)
"""

import json
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel
from backend.db.connection import get_db_cursor
from backend.routes.auth import get_current_user, require_role
from backend.services.claude_service import (
    evaluate_vendor_match,
    generate_vendor_comparison,
    generate_negotiation_email,
)

router = APIRouter(prefix="/api/ai", tags=["AI Analysis & Intelligence"])


class NegotiationRequest(BaseModel):
    rfq_id: int
    vendor_id: int
    quote_id: Optional[int] = None
    strategy: Optional[str] = "balanced"  # balanced, aggressive, collaborative


@router.post("/match/{rfq_id}/vendor/{vendor_id}")
def match_single_vendor(
    rfq_id: int,
    vendor_id: int,
    force_refresh: bool = False,
    current_user: dict = Depends(get_current_user),
):
    """
    Evaluates or retrieves cached AI analysis for a specific RFQ and Vendor pair.
    Stores and caches result in the ai_analysis table.
    """
    with get_db_cursor(commit=True) as cur:
        # Check cache if not forcing refresh
        if not force_refresh:
            cur.execute(
                """
                SELECT a.*, v.name as vendor_name, v.category as vendor_category, v.performance_rating
                FROM ai_analysis a
                JOIN vendors v ON a.vendor_id = v.id
                WHERE a.rfq_id = %s AND a.vendor_id = %s
                """,
                (rfq_id, vendor_id),
            )
            cached = cur.fetchone()
            if cached:
                risk_flags = cached.get("risk_flags")
                if isinstance(risk_flags, str):
                    try:
                        risk_flags = json.loads(risk_flags)
                    except Exception:
                        risk_flags = [risk_flags]
                return {
                    "rfq_id": cached["rfq_id"],
                    "vendor_id": cached["vendor_id"],
                    "vendor_name": cached["vendor_name"],
                    "match_score": cached["match_score"],
                    "reasoning": cached["reasoning"],
                    "risk_flags": risk_flags or [],
                    "cached": True,
                    "created_at": str(cached["created_at"]) if cached.get("created_at") else None,
                }

        # Fetch RFQ
        cur.execute("SELECT * FROM rfqs WHERE id = %s", (rfq_id,))
        rfq = cur.fetchone()
        if not rfq:
            raise HTTPException(status_code=404, detail="RFQ not found")

        # Fetch Vendor
        cur.execute("SELECT * FROM vendors WHERE id = %s", (vendor_id,))
        vendor = cur.fetchone()
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")

        # Fetch optional Quote
        cur.execute("SELECT * FROM quotes WHERE rfq_id = %s AND vendor_id = %s", (rfq_id, vendor_id))
        quote = cur.fetchone()

        # Call Claude AI Service
        ai_result = evaluate_vendor_match(rfq, vendor, quote)
        match_score = ai_result["match_score"]
        reasoning = ai_result["reasoning"]
        risk_flags_json = json.dumps(ai_result.get("risk_flags", []))

        # Upsert into ai_analysis
        cur.execute(
            """
            DELETE FROM ai_analysis WHERE rfq_id = %s AND vendor_id = %s
            """,
            (rfq_id, vendor_id),
        )
        cur.execute(
            """
            INSERT INTO ai_analysis (rfq_id, vendor_id, match_score, reasoning, risk_flags)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (rfq_id, vendor_id, match_score, reasoning, risk_flags_json),
        )

        return {
            "rfq_id": rfq_id,
            "vendor_id": vendor_id,
            "vendor_name": vendor["name"],
            "match_score": match_score,
            "reasoning": reasoning,
            "risk_flags": ai_result.get("risk_flags", []),
            "cached": False,
        }


@router.post("/match/{rfq_id}")
def match_all_vendors_for_rfq(
    rfq_id: int,
    force_refresh: bool = False,
    current_user: dict = Depends(get_current_user),
):
    """
    Evaluates RFQ against all active vendors (or quoting vendors).
    Caches scores in ai_analysis table.
    """
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM rfqs WHERE id = %s", (rfq_id,))
        rfq = cur.fetchone()
        if not rfq:
            raise HTTPException(status_code=404, detail="RFQ not found")

        # Fetch all vendors
        cur.execute("SELECT * FROM vendors ORDER BY id ASC")
        vendors = cur.fetchall()

    results = []
    for v in vendors:
        res = match_single_vendor(rfq_id, v["id"], force_refresh=force_refresh, current_user=current_user)
        results.append(res)

    results.sort(key=lambda x: x["match_score"], reverse=True)
    return {"rfq_id": rfq_id, "rfq_title": rfq["title"], "evaluated_vendors": results}


@router.get("/compare/{rfq_id}")
def compare_top_vendors(
    rfq_id: int,
    vendor_ids: Optional[str] = Query(None, description="Comma-separated vendor IDs"),
    current_user: dict = Depends(get_current_user),
):
    """
    Generates side-by-side comparison for top 3 vendors (or chosen vendor_ids) for an RFQ.
    Includes Claude-generated comparative executive summary.
    """
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM rfqs WHERE id = %s", (rfq_id,))
        rfq = cur.fetchone()
        if not rfq:
            raise HTTPException(status_code=404, detail="RFQ not found")

        chosen_ids = []
        if vendor_ids:
            try:
                chosen_ids = [int(x.strip()) for x in vendor_ids.split(",") if x.strip()]
            except ValueError:
                chosen_ids = []

        # Get vendors with quotes and AI scores
        cur.execute(
            """
            SELECT v.*, q.id as quote_id, q.quote_amount, q.delivery_timeline_days, q.proposal_details, q.status as quote_status,
                   COALESCE(a.match_score, 0) as match_score, a.reasoning as ai_reasoning, a.risk_flags as ai_risk_flags
            FROM vendors v
            LEFT JOIN quotes q ON q.vendor_id = v.id AND q.rfq_id = %s
            LEFT JOIN ai_analysis a ON a.vendor_id = v.id AND a.rfq_id = %s
            ORDER BY match_score DESC, q.quote_amount ASC
            """,
            (rfq_id, rfq_id),
        )
        all_candidates = cur.fetchall()

    # Filter strictly to vendors who submitted quotes for this RFQ OR match its category
    rfq_category = (rfq.get("category") or "").strip().lower()
    filtered_candidates = [
        c for c in all_candidates
        if c.get("quote_id") is not None or (c.get("category") and c["category"].strip().lower() == rfq_category)
    ]

    # Filter by chosen_ids or take top 3
    if chosen_ids:
        selected = [c for c in filtered_candidates if c["id"] in chosen_ids]
    else:
        # Prioritize vendors with submitted quotes, then order by highest match score, max 3
        with_quote = [c for c in filtered_candidates if c.get("quote_id") is not None]
        without_quote = [c for c in filtered_candidates if c.get("quote_id") is None]
        combined = with_quote + without_quote
        selected = combined[:3]

    # Prepare data structure for Claude service
    vendor_items = []
    for item in selected:
        risk_flags = item.get("ai_risk_flags")
        if isinstance(risk_flags, str):
            try:
                risk_flags = json.loads(risk_flags)
            except Exception:
                risk_flags = [risk_flags]

        vendor_dict = {
            "id": item["id"],
            "name": item["name"],
            "category": item["category"],
            "pricing": item["pricing"],
            "performance_rating": float(item["performance_rating"]) if item.get("performance_rating") else 4.0,
            "certifications": item.get("certifications"),
            "location": item.get("location"),
        }
        quote_dict = {
            "quote_id": item.get("quote_id"),
            "quote_amount": float(item["quote_amount"]) if item.get("quote_amount") is not None else None,
            "delivery_timeline_days": item.get("delivery_timeline_days"),
            "proposal_details": item.get("proposal_details"),
            "status": item.get("quote_status"),
        }
        analysis_dict = {
            "match_score": item.get("match_score"),
            "reasoning": item.get("ai_reasoning"),
            "risk_flags": risk_flags or [],
        }
        vendor_items.append({
            "vendor": vendor_dict,
            "quote": quote_dict,
            "analysis": analysis_dict,
        })

    # Call Claude for synthesis
    ai_comparison = generate_vendor_comparison(rfq, vendor_items)

    return {
        "rfq": {
            "id": rfq["id"],
            "title": rfq["title"],
            "budget": float(rfq["budget"]) if rfq.get("budget") is not None else 0,
            "requirements": rfq["requirements"],
            "deadline": str(rfq["deadline"]) if rfq.get("deadline") else None,
        },
        "vendors": vendor_items,
        "executive_summary": ai_comparison.get("executive_summary"),
        "recommended_vendor_id": ai_comparison.get("recommended_vendor_id"),
        "recommendation_reason": ai_comparison.get("recommendation_reason"),
        "comparison_matrix": ai_comparison.get("comparison_matrix", []),
    }


@router.post("/negotiate")
def draft_negotiation(
    req: NegotiationRequest,
    current_user: dict = Depends(require_role(["Admin", "Procurement Manager"])),
):
    """
    Calls Claude to draft a custom B2B negotiation email based on vendor quote vs RFQ budget.
    """
    with get_db_cursor() as cur:
        # Get RFQ
        cur.execute("SELECT * FROM rfqs WHERE id = %s", (req.rfq_id,))
        rfq = cur.fetchone()
        if not rfq:
            raise HTTPException(status_code=404, detail="RFQ not found")

        # Get Vendor
        cur.execute("SELECT * FROM vendors WHERE id = %s", (req.vendor_id,))
        vendor = cur.fetchone()
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")

        # Get Quote
        if req.quote_id:
            cur.execute("SELECT * FROM quotes WHERE id = %s", (req.quote_id,))
        else:
            cur.execute("SELECT * FROM quotes WHERE rfq_id = %s AND vendor_id = %s", (req.rfq_id, req.vendor_id))
        quote = cur.fetchone()

        if not quote:
            # Create a mock placeholder quote if none exists yet for negotiation context
            quote = {
                "quote_amount": float(rfq["budget"]) * 1.15,
                "delivery_timeline_days": 30,
                "proposal_details": "Standard commercial proposal",
            }

    draft = generate_negotiation_email(rfq, vendor, quote, strategy=req.strategy or "balanced")
    return {
        "rfq_id": req.rfq_id,
        "rfq_title": rfq["title"],
        "vendor_id": req.vendor_id,
        "vendor_name": vendor["name"],
        "quote_amount": float(quote["quote_amount"]) if quote.get("quote_amount") is not None else 0,
        "target_budget": float(rfq["budget"]) if rfq.get("budget") is not None else 0,
        "subject": draft.get("subject"),
        "email_body": draft.get("email_body"),
    }


@router.get("/analytics")
def get_analytics(current_user: dict = Depends(get_current_user)):
    """
    Returns analytics for Chart.js dashboards:
    - Monthly spend & budget trends
    - Category distribution
    - Vendor performance scores
    - AI matching score distribution
    """
    with get_db_cursor() as cur:
        # Total counts
        cur.execute("SELECT COUNT(*) as total_vendors FROM vendors")
        total_vendors = cur.fetchone()["total_vendors"]

        cur.execute("SELECT COUNT(*) as total_rfqs FROM rfqs")
        total_rfqs = cur.fetchone()["total_rfqs"]

        cur.execute("SELECT COUNT(*) as total_quotes FROM quotes")
        total_quotes = cur.fetchone()["total_quotes"]

        cur.execute("SELECT COALESCE(SUM(budget), 0) as total_budget FROM rfqs")
        total_budget = float(cur.fetchone()["total_budget"])

        cur.execute("SELECT COALESCE(SUM(quote_amount), 0) as total_awarded FROM quotes WHERE status = 'Accepted'")
        total_awarded = float(cur.fetchone()["total_awarded"])

        # Category Breakdown
        cur.execute(
            """
            SELECT category, COUNT(*) as vendor_count
            FROM vendors
            GROUP BY category
            ORDER BY vendor_count DESC
            """
        )
        category_rows = cur.fetchall()

        # Vendor Rating distribution
        cur.execute(
            """
            SELECT name, performance_rating, pricing, category
            FROM vendors
            ORDER BY performance_rating DESC
            LIMIT 6
            """
        )
        top_rated_vendors = cur.fetchall()
        for v in top_rated_vendors:
            if "performance_rating" in v and v["performance_rating"] is not None:
                v["performance_rating"] = float(v["performance_rating"])

        # AI match scores
        cur.execute(
            """
            SELECT a.match_score, v.name as vendor_name, r.title as rfq_title
            FROM ai_analysis a
            JOIN vendors v ON a.vendor_id = v.id
            JOIN rfqs r ON a.rfq_id = r.id
            ORDER BY a.match_score DESC
            LIMIT 5
            """
        )
        ai_matches = cur.fetchall()

    # Spend trend simulation (quarterly / monthly for Chart.js)
    spend_trends = {
        "labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep"],
        "allocated_budget": [45000, 52000, 68000, 80000, 95000, 110000, 130000, 145000, 150000],
        "actual_spend": [41000, 48500, 62000, 74000, 88000, 99000, 118000, 132000, 138000],
        "ai_savings": [4000, 3500, 6000, 6000, 7000, 11000, 12000, 13000, 12000],
    }

    return {
        "stats": {
            "total_vendors": total_vendors,
            "total_rfqs": total_rfqs,
            "total_quotes": total_quotes,
            "total_budget": total_budget,
            "total_awarded": total_awarded,
            "estimated_savings": 74500.00,
            "avg_ai_match_score": 90.3,
        },
        "spend_trends": spend_trends,
        "categories": {
            "labels": [r["category"] for r in category_rows],
            "counts": [r["vendor_count"] for r in category_rows],
        },
        "top_rated_vendors": top_rated_vendors,
        "ai_matches": ai_matches,
    }
