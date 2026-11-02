from nlti.models import Contractor, Tender


def _normalise(items):
    return {str(item).strip().casefold() for item in (items or []) if str(item).strip()}


def score_match(contractor: Contractor, tender: Tender) -> dict:
    """Transparent screening score. It is not a legal eligibility determination."""
    c_trades, t_trades = _normalise(contractor.trades), _normalise(tender.trades)
    c_regions, t_region = _normalise(contractor.regions), (tender.region or "").strip().casefold()

    trade_ok = bool(c_trades & t_trades) if t_trades else False
    region_ok = t_region in c_regions if t_region else False
    qualifications = _normalise(contractor.certifications)
    requirements = _normalise(tender.mandatory_requirements)
    qualification_ratio = (len(requirements & qualifications) / len(requirements)) if requirements else 1.0

    score = 30 * trade_ok + 20 * region_ok + 20 * qualification_ratio
    score += 15 if contractor.crew_capacity and contractor.crew_capacity > 0 else 0
    score += 10 if tender.estimated_value is not None else 0
    score += 5 if tender.closing_date is not None else 0

    flags = []
    if requirements - qualifications:
        flags.append("Unconfirmed/missing listed qualifications: " + ", ".join(sorted(requirements - qualifications)))
    if tender.bid_security_required is True:
        flags.append("Tender indicates bid security is required; verify amount, form, and deadline.")
    if not contractor.insurance_verified:
        flags.append("Contractor insurance has not been verified by NLTI.")
    if not trade_ok:
        flags.append("No matching trade recorded in contractor profile.")
    if not region_ok:
        flags.append("Tender region is not listed in contractor service regions.")

    explanation = [
        f"Trade compatibility: {'match' if trade_ok else 'no recorded match'} (30 points max).",
        f"Regional coverage: {'match' if region_ok else 'no recorded match'} (20 points max).",
        f"Listed qualification coverage: {qualification_ratio:.0%} (20 points max).",
        "Crew capacity: recorded." if contractor.crew_capacity and contractor.crew_capacity > 0 else "Crew capacity: not recorded.",
        "Tender value: published." if tender.estimated_value is not None else "Tender value: not published.",
        "Closing date: recorded." if tender.closing_date is not None else "Closing date: not recorded.",
    ]
    return {"score": round(score, 1), "explanation": explanation, "flags": flags}
