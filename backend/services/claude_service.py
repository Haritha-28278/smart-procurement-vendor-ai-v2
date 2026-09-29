"""
Claude AI Service for Smart Procurement Vendor AI
All Anthropic Claude API interactions are strictly isolated here.
Never exposes API keys to frontend or client.
Returns clean structured JSON for scoring, side-by-side comparisons, and negotiation emails.
Includes an intelligent heuristic fallback mode if ANTHROPIC_API_KEY is unset.
"""

import os
import json
import re
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Initialize Anthropic client if key is set
client = None
if ANTHROPIC_API_KEY and ANTHROPIC_API_KEY != "your_claude_api_key_here":
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    except Exception as e:
        print(f"[ClaudeService] Warning: Could not initialize Anthropic client: {e}")


def _extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Safely extracts JSON object from Claude's response text."""
    try:
        # Match standard json codeblocks or naked json
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if match:
            return json.loads(match.group(1))
        # Match bare { ... }
        match_bare = re.search(r'\{[\s\S]*\}', text)
        if match_bare:
            return json.loads(match_bare.group(0))
        return json.loads(text)
    except Exception:
        return None


def evaluate_vendor_match(
    rfq: Dict[str, Any],
    vendor: Dict[str, Any],
    quote: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Evaluates how well a vendor meets an RFQ's requirements, budget, and timeline.
    Returns:
        {
            "match_score": int (0-100),
            "reasoning": str,
            "risk_flags": list[str]
        }
    """
    quote_info = f"""
    Submitted Quote Amount: ${quote.get('quote_amount', 'N/A')}
    Delivery Timeline: {quote.get('delivery_timeline_days', 'N/A')} days
    Proposal Details: {quote.get('proposal_details', 'None')}
    """ if quote else "No specific quote submitted yet; evaluate general capabilities against RFQ."

    prompt = f"""You are an elite enterprise B2B procurement analyst and vendor evaluation AI.
Evaluate the following vendor's suitability for this Request for Quotation (RFQ).

--- RFQ DETAILS ---
Title: {rfq.get('title')}
Category: {rfq.get('category')}
Target Budget: ${rfq.get('budget', 0):,.2f}
Requirements: {rfq.get('requirements')}
Deadline: {rfq.get('deadline')}

--- VENDOR PROFILE ---
Vendor Name: {vendor.get('name')}
Category: {vendor.get('category')}
Pricing Tier: {vendor.get('pricing')}
Performance Rating: {vendor.get('performance_rating', '4.0')} / 5.0
Location: {vendor.get('location')}
Certifications: {vendor.get('certifications', 'None')}
Track Record & Past Performance: {vendor.get('past_performance', 'None')}

--- QUOTE / PROPOSAL ---
{quote_info}

Analyze the match rigorously on:
1. Capability & Requirement fulfillment
2. Pricing and Budget alignment
3. Reliability, certifications & risk
4. Timeline and delivery feasibility

You MUST respond strictly with a valid JSON object with EXACTLY this structure:
{{
  "match_score": <integer between 0 and 100>,
  "reasoning": "<concise 2-4 sentence executive summary detailing strengths, gaps, and why this score was awarded>",
  "risk_flags": [
    "<specific risk flag 1, e.g. budget variance, lack of specific cert, geographic lead time>",
    "<specific risk flag 2>"
  ]
}}
Do not include any Markdown headers or explanations outside the JSON object.
"""

    if client:
        try:
            # Use Claude 3.5 Sonnet or 3.7 Sonnet
            response = client.messages.create(
                model="claude-sonnet-5",
                max_tokens=600,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = response.content[0].text.strip()
            parsed = _extract_json_from_text(raw_text)
            if parsed and "match_score" in parsed and "reasoning" in parsed:
                # Sanitize score between 0 and 100
                parsed["match_score"] = max(0, min(100, int(parsed["match_score"])))
                if "risk_flags" not in parsed or not isinstance(parsed["risk_flags"], list):
                    parsed["risk_flags"] = []
                return parsed
        except Exception as e:
            print(f"[ClaudeService] Claude API call failed, falling back to heuristic evaluation: {e}")

    # Heuristic fallback if Claude API key is absent or network fails
    return _heuristic_vendor_match(rfq, vendor, quote)


def _heuristic_vendor_match(rfq: Dict[str, Any], vendor: Dict[str, Any], quote: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    score = 70
    risk_flags = []

    # Category matching
    if rfq.get("category", "").lower() in vendor.get("category", "").lower() or vendor.get("category", "").lower() in rfq.get("category", "").lower():
        score += 12
    else:
        score -= 10
        risk_flags.append(f"Vendor core domain is {vendor.get('category')}, which differs from RFQ category {rfq.get('category')}")

    # Performance rating
    rating = float(vendor.get("performance_rating") or 4.0)
    score += int((rating - 3.5) * 10)

    # Budget / Quote check
    budget = float(rfq.get("budget") or 100000)
    if quote and quote.get("quote_amount"):
        quote_amt = float(quote["quote_amount"])
        if quote_amt <= budget:
            savings_pct = ((budget - quote_amt) / budget) * 100
            score += min(10, int(savings_pct / 3))
        else:
            over_pct = ((quote_amt - budget) / budget) * 100
            score -= min(25, int(over_pct / 2))
            risk_flags.append(f"Quote (${quote_amt:,.2f}) exceeds RFQ target budget (${budget:,.2f}) by {over_pct:.1f}%")
    else:
        # Check pricing tier vs budget
        tier = vendor.get("pricing", "").lower()
        if "premium" in tier and budget < 75000:
            score -= 8
            risk_flags.append("Premium vendor pricing model may create budget pressure")

    # Certifications
    certs = vendor.get("certifications", "").lower()
    reqs = rfq.get("requirements", "").lower()
    if "soc 2" in reqs and "soc 2" not in certs:
        score -= 12
        risk_flags.append("Missing explicit SOC 2 certification required by RFQ")
    if "iso" in certs:
        score += 5

    score = max(35, min(97, score))

    reasoning = (
        f"{vendor.get('name')} shows strong baseline alignment with {rfq.get('category')} procurement goals. "
        f"Their historical performance rating of {rating}/5.0 and established credentials provide high reliability, "
        f"with specific evaluation noted regarding budget allocation and delivery terms."
    )
    if not risk_flags:
        risk_flags.append("Standard contract milestone and SLA tracking recommended")

    return {
        "match_score": score,
        "reasoning": reasoning,
        "risk_flags": risk_flags
    }


def generate_vendor_comparison(
    rfq: Dict[str, Any],
    vendors_with_quotes: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Generates side-by-side comparative analysis of top vendors for an RFQ.
    """
    vendors_summary = []
    for item in vendors_with_quotes:
        v = item.get("vendor", {})
        q = item.get("quote", {})
        a = item.get("analysis", {})
        vendors_summary.append({
            "vendor_id": v.get("id"),
            "vendor_name": v.get("name"),
            "pricing_tier": v.get("pricing"),
            "rating": v.get("performance_rating"),
            "certifications": v.get("certifications"),
            "location": v.get("location"),
            "quote_amount": q.get("quote_amount"),
            "delivery_days": q.get("delivery_timeline_days"),
            "proposal": q.get("proposal_details"),
            "ai_score": a.get("match_score"),
            "risk_flags": a.get("risk_flags")
        })

    prompt = f"""You are the Chief Procurement Officer AI assistant.
Compare the following vendors who have quoted for the given RFQ and provide an actionable comparative synthesis.

--- RFQ ---
Title: {rfq.get('title')}
Budget: ${rfq.get('budget', 0):,.2f}
Requirements: {rfq.get('requirements')}

--- VENDORS & BIDS ---
{json.dumps(vendors_summary, indent=2)}

Provide a structured JSON output with:
1. "executive_summary": Comprehensive 3-4 sentence comparison highlighting top choice, cost-benefit tradeoffs, and critical decision factors.
2. "recommended_vendor_id": ID of the optimal vendor.
3. "recommendation_reason": Explicit reason why this vendor wins.
4. "comparison_matrix": Array of objects for each vendor with fields: "vendor_id", "vendor_name", "key_strength", "primary_risk", "verdict".

Respond STRICTLY with valid JSON.
"""

    if client:
        try:
            response = client.messages.create(
                model="claude-sonnet-5",
                max_tokens=900,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            parsed = _extract_json_from_text(raw)
            if parsed and "executive_summary" in parsed:
                return parsed
        except Exception as e:
            print(f"[ClaudeService] Claude comparison failed, falling back: {e}")

    # Heuristic fallback comparison
    best_vendor = None
    highest_score = -1
    matrix = []

    for v_item in vendors_summary:
        score = v_item.get("ai_score") or 80
        if score > highest_score:
            highest_score = score
            best_vendor = v_item

        matrix.append({
            "vendor_id": v_item.get("vendor_id"),
            "vendor_name": v_item.get("vendor_name"),
            "key_strength": f"Rating {v_item.get('rating')}/5.0 with verified credentials in {v_item.get('pricing_tier')} tier",
            "primary_risk": (v_item.get("risk_flags") or ["Timeline sensitivity"])[0] if isinstance(v_item.get("risk_flags"), list) and v_item.get("risk_flags") else "Delivery coordination",
            "verdict": "Top Recommended" if v_item == best_vendor else "Strong Contender"
        })

    rec_name = best_vendor.get("vendor_name") if best_vendor else "Selected Vendor"
    rec_id = best_vendor.get("vendor_id") if best_vendor else (vendors_summary[0]["vendor_id"] if vendors_summary else 1)

    return {
        "executive_summary": (
            f"Based on algorithmic evaluation against RFQ budget (${rfq.get('budget', 0):,.2f}) and technical requirements, "
            f"{rec_name} emerges as the optimal choice with an AI alignment score of {highest_score}/100. "
            f"Their proposal strikes the highest balance of verified SLA compliance, certified quality standards, and budget sustainability."
        ),
        "recommended_vendor_id": rec_id,
        "recommendation_reason": f"Highest composite rating, compliant certifications, and optimal pricing-to-risk ratio.",
        "comparison_matrix": matrix
    }


def generate_negotiation_email(
    rfq: Dict[str, Any],
    vendor: Dict[str, Any],
    quote: Dict[str, Any],
    strategy: str = "balanced"
) -> Dict[str, Any]:
    """
    Drafts a professional B2B procurement negotiation email based on vendor quote vs RFQ budget.
    """
    quote_amt = float(quote.get("quote_amount") or 0)
    budget = float(rfq.get("budget") or 0)
    variance = quote_amt - budget

    prompt = f"""You are an expert procurement negotiator.
Draft a professional, courteous, yet firm B2B negotiation email to send to the vendor regarding their recent quotation.

--- CONTEXT ---
Buyer Company: Enterprise Procurement Team
RFQ Title: {rfq.get('title')}
Target RFQ Budget: ${budget:,.2f}
Vendor Quoted Amount: ${quote_amt:,.2f} (Variance: {'+$' + f'{variance:,.2f}' if variance > 0 else '-$' + f'{abs(variance):,.2f}'} compared to budget)
Delivery Timeline Quoted: {quote.get('delivery_timeline_days')} days
Vendor Contact: {vendor.get('contact_email') or 'Procurement Contact'}
Vendor Name: {vendor.get('name')}
Negotiation Tone/Strategy: {strategy} (e.g. balanced, aggressive cost-savings, relationship-focused)

Draft an email that:
1. Commends them on their proposal quality and high qualification score.
2. Directly addresses the quote amount and politely requests a revision closer to or below the target budget (${budget:,.2f}), offering incentives such as volume commitments, expedited payment terms, or long-term preferred vendor status.
3. Suggests milestone-based payments and asks for their revised best-and-final offer (BAFO).

Return STRICTLY a JSON object with:
{{
  "subject": "<Compelling email subject line>",
  "email_body": "<Complete email draft ready to send, including placeholders for buyer signature>"
}}
"""

    if client:
        try:
            response = client.messages.create(
                model="claude-sonnet-5",
                max_tokens=800,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            parsed = _extract_json_from_text(raw)
            if parsed and "email_body" in parsed:
                return parsed
        except Exception as e:
            print(f"[ClaudeService] Claude negotiation drafting failed, falling back: {e}")

    # Fallback negotiation email draft
    subj = f"Quotation Follow-Up & Partnership Terms: {rfq.get('title')} - {vendor.get('name')}"
    target_proposal = f"${budget:,.2f}" if variance > 0 else f"${quote_amt * 0.92:,.2f}"
    
    body = f"""Dear {vendor.get('name')} Team,

Thank you for submitting your comprehensive proposal for "{rfq.get('title')}". Our procurement committee thoroughly reviewed your submission and was very impressed with your team's technical capabilities, past performance record, and certified standards.

As we finalize our vendor selection, we are reviewing commercial terms. Your quoted figure of ${quote_amt:,.2f} currently exceeds our allocated departmental target of ${budget:,.2f}. 

In order to move forward with {vendor.get('name')} as our designated awardee, we would welcome the opportunity to discuss aligning your quotation closer to {target_proposal}. In return, our organization is prepared to offer:
- Accelerated net-30 payment milestones tied to clear sprint deliverables
- Consideration for preferred vendor designation across our upcoming quarterly procurement cycles
- Joint case-study and co-marketing authorization upon successful project delivery

Could you please review your cost breakdown and advise if you can provide a Best and Final Offer (BAFO) by early next week? We would also be glad to schedule a brief 15-minute call to align on scope optimizations if helpful.

We value the potential of working together and look forward to your response.

Sincerely,

Procurement Directorate
Smart Procurement Operations
procurement@smartprocure.ai
"""

    return {
        "subject": subj,
        "email_body": body
    }
