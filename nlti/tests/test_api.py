from datetime import date, timedelta

from nlti.auth import hash_password
from nlti.models import Account, Contractor, ProcurementSource, Tender


def register_and_login(client):
    registration = client.post(
        "/auth/register",
        json={
            "email": "builder@example.ca",
            "password": "a-strong-password-for-testing",
            "company_name": "North Coast Construction",
            "insurance_verified": True,
        },
    )
    assert registration.status_code == 201
    login = client.post(
        "/auth/token",
        json={"email": "builder@example.ca", "password": "a-strong-password-for-testing"},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def test_public_summary_and_separate_tender_sections(client):
    api_client, sessions = client
    today = date.today()
    with sessions() as db:
        db.add_all(
            [
                Tender(
                    title="Future bridge repair",
                    location="Gander",
                    region="Central Newfoundland",
                    closing_date=today + timedelta(days=14),
                    status="open",
                    is_demo=False,
                ),
                Tender(
                    title="Past paving contract",
                    location="Corner Brook",
                    region="Western Newfoundland",
                    closing_date=today - timedelta(days=7),
                    status="closed",
                    is_demo=False,
                ),
                Tender(
                    title="Fictional demo contract",
                    location="Demo",
                    region="Demo",
                    closing_date=today + timedelta(days=1),
                    status="open",
                    is_demo=True,
                ),
            ]
        )
        db.commit()

    assert api_client.get("/summary").json() == {
        "upcoming_tenders": 1,
        "historical_tenders": 1,
        "reviewed_sources": 0,
    }
    assert [row["title"] for row in api_client.get("/tenders/upcoming").json()] == [
        "Future bridge repair"
    ]
    assert [row["title"] for row in api_client.get("/tenders/historical").json()] == [
        "Past paving contract"
    ]
    assert [row["title"] for row in api_client.get("/tenders?include_demo=true").json()] == [
        "Past paving contract",
        "Fictional demo contract",
        "Future bridge repair",
    ]


def test_registration_scopes_contractor_and_never_accepts_self_verified_insurance(client):
    api_client, sessions = client
    token = register_and_login(api_client)
    profile = api_client.get("/contractors", headers={"Authorization": f"Bearer {token}"})
    assert profile.status_code == 200
    assert len(profile.json()) == 1
    assert profile.json()[0]["company_name"] == "North Coast Construction"
    assert profile.json()[0]["insurance_verified"] is False
    assert api_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    with sessions() as db:
        other = Contractor(company_name="Other Contractor")
        db.add(other)
        db.flush()
        db.add(
            Account(
                email="other@example.ca",
                password_hash="not-used-in-this-test",
                role="contractor",
                contractor_id=other.id,
            )
        )
        db.commit()
        other_id = other.id
    assert api_client.post(
        f"/matches/{other_id}",
        headers={"Authorization": f"Bearer {token}"},
    ).status_code == 403


def test_authentication_and_admin_only_writes(client):
    api_client, _ = client
    assert api_client.get("/contractors").status_code == 401
    assert api_client.post(
        "/tenders",
        json={
            "title": "Public test tender",
            "location": "St. John's",
            "region": "Avalon",
        },
    ).status_code == 401

    token = register_and_login(api_client)
    assert api_client.post(
        "/sources",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Unreviewed source",
            "owner": "Example authority",
            "official_url": "https://example.ca/tenders",
            "is_active": True,
        },
    ).status_code == 403
    assert api_client.post(
        "/sources",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Unreviewed source",
            "owner": "Example authority",
            "official_url": "https://example.ca/tenders",
            "is_active": False,
        },
    ).status_code == 403


def test_admin_can_publish_only_reviewed_sources(client):
    api_client, sessions = client
    with sessions() as db:
        db.add(
            Account(
                email="admin@example.ca",
                password_hash=hash_password("admin-test-password-is-long-enough"),
                role="admin",
            )
        )
        db.commit()
    token = api_client.post(
        "/auth/token",
        json={"email": "admin@example.ca", "password": "admin-test-password-is-long-enough"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    incomplete = api_client.post(
        "/sources",
        headers=headers,
        json={
            "name": "Needs review",
            "owner": "Example authority",
            "official_url": "https://example.ca/tenders",
            "is_active": True,
        },
    )
    assert incomplete.status_code == 422

    approved = api_client.post(
        "/sources",
        headers=headers,
        json={
            "name": "Approved procurement feed",
            "owner": "Example authority",
            "official_url": "https://example.ca/tenders",
            "terms_url": "https://example.ca/terms",
            "terms_reviewed_at": "2026-10-31T12:00:00Z",
            "permitted_reuse": True,
            "is_active": True,
        },
    )
    assert approved.status_code == 201
    assert [source["name"] for source in api_client.get("/sources").json()] == [
        "Approved procurement feed"
    ]


def test_sources_only_show_when_reviewed_and_reuse_is_permitted(client):
    api_client, sessions = client
    with sessions() as db:
        db.add_all(
            [
                ProcurementSource(
                    name="Pending review",
                    owner="Example authority",
                    official_url="https://example.ca",
                    is_active=True,
                    terms_reviewed_at=None,
                    permitted_reuse=None,
                ),
                ProcurementSource(
                    name="Approved source",
                    owner="Example authority",
                    official_url="https://example.ca/official",
                    terms_reviewed_at=None,
                    permitted_reuse=True,
                    is_active=True,
                ),
            ]
        )
        db.commit()
    assert api_client.get("/sources").json() == []
