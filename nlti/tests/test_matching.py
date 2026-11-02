from types import SimpleNamespace

from nlti.matching import score_match


def test_trade_and_region_match_scores_expected_points():
    contractor = SimpleNamespace(
        trades=["Roofing"], regions=["Labrador"], certifications=[],
        crew_capacity=5, insurance_verified=False
    )
    tender = SimpleNamespace(
        trades=["roofing"], region="Labrador", mandatory_requirements=[],
        estimated_value=None, closing_date=None, bid_security_required=False
    )
    result = score_match(contractor, tender)
    assert result["score"] == 85.0
    assert any("insurance" in flag.lower() for flag in result["flags"])


def test_missing_mandatory_qualification_is_flagged():
    contractor = SimpleNamespace(
        trades=["electrical"], regions=["Avalon"], certifications=[],
        crew_capacity=3, insurance_verified=True
    )
    tender = SimpleNamespace(
        trades=["electrical"], region="Avalon",
        mandatory_requirements=["electrical licence"],
        estimated_value=100000, closing_date=None, bid_security_required=True
    )
    result = score_match(contractor, tender)
    assert any("missing listed qualifications" in flag.lower() for flag in result["flags"])
    assert any("bid security" in flag.lower() for flag in result["flags"])
