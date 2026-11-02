from datetime import UTC, date, datetime, timedelta
from urllib.parse import parse_qs, urlparse

from nlti.auth import hash_password
from nlti.models import Account, Contractor, ProcurementSource, Tender


def register_and_login(client, email="builder@example.ca"):
    registration = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "a-strong-password-for-testing",
            "company_name": "North Coast Construction",
            "insurance_verified": True,
        },
    )
    assert registration.status_code == 201
    login = client.post(
        "/auth/token",
        json={"email": email, "password": "a-strong-password-for-testing"},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def create_admin(client):
    api_client, sessions = client
    with sessions() as db:
        db.add(
            Account(
                email="workflow-admin@example.ca",
                password_hash=hash_password("workflow-admin-password-long-enough"),
                role="admin",
            )
        )
        db.commit()
    response = api_client.post(
        "/auth/token",
        json={
            "email": "workflow-admin@example.ca",
            "password": "workflow-admin-password-long-enough",
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_reviewed_source(api_client, headers):
    response = api_client.post(
        "/sources",
        headers=headers,
        json={
            "name": "Reviewed workflow source",
            "owner": "Example public authority",
            "official_url": "https://example.ca/procurement",
            "update_frequency": "Manual review, on demand",
            "terms_url": "https://example.ca/terms",
            "terms_reviewed_at": "2026-10-31T12:00:00Z",
            "permitted_reuse": True,
            "rate_limit_notes": "Manual access only; no automated requests.",
            "is_active": True,
        },
    )
    assert response.status_code == 201
    return response.json()


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
        "verified_outcomes": 0,
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


def test_email_verification_tokens_are_throttled_single_use_and_expiring(client, monkeypatch):
    api_client, _ = client
    token = register_and_login(api_client)
    headers = {"Authorization": f"Bearer {token}"}
    first = api_client.post("/auth/verification", headers=headers)
    assert first.status_code == 200
    assert first.json()["sent"] is True
    raw_token = parse_qs(urlparse(first.json()["verification_url"]).query)["verify"][0]
    assert api_client.post("/auth/verification", headers=headers).status_code == 200
    assert api_client.post("/auth/verification", headers=headers).status_code == 200
    assert api_client.post("/auth/verification", headers=headers).status_code == 429

    verified = api_client.post("/auth/verify-email", json={"token": raw_token})
    assert verified.status_code == 200
    assert verified.json()["email_verified_at"] is not None
    assert api_client.post("/auth/verify-email", json={"token": raw_token}).status_code == 400

    monkeypatch.setattr("nlti.api.main.settings.nlti_env", "production")
    monkeypatch.setattr("nlti.api.main.settings.smtp_host", None)
    monkeypatch.setattr("nlti.api.main.settings.smtp_sender", None)
    new_token = register_and_login(api_client, "smtp-required@example.ca")
    assert api_client.post(
        "/auth/verification",
        headers={"Authorization": f"Bearer {new_token}"},
    ).status_code == 503
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
            "update_frequency": "Manual review, on demand",
            "rate_limit_notes": "Manual access only; no automated requests.",
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


def test_source_ingestion_deduplicates_corrects_archives_and_tracks_health(client):
    api_client, _ = client
    headers = create_admin(client)
    source = create_reviewed_source(api_client, headers)
    retrieved_at = datetime.now(UTC).isoformat()
    first = api_client.post(
        f"/sources/{source['id']}/ingest",
        headers=headers,
        json={
            "retrieved_at": retrieved_at,
            "records": [
                {
                    "title": "Bridge deck repairs",
                    "location": "Gander",
                    "region": "Central Newfoundland",
                    "closing_date": "2099-02-01",
                    "status": "open",
                    "source_reference": "AUTH-2026-01",
                }
            ],
        },
    )
    assert first.status_code == 200
    assert first.json()["records_created"] == 1

    corrected = api_client.post(
        f"/sources/{source['id']}/ingest",
        headers=headers,
        json={
            "retrieved_at": retrieved_at,
            "records": [
                {
                    "title": "Corrected bridge deck repairs",
                    "location": "Gander",
                    "region": "Central Newfoundland",
                    "closing_date": "2099-02-15",
                    "status": "open",
                    "source_reference": "AUTH-2026-01",
                }
            ],
            "archived_references": ["AUTH-2026-01"],
        },
    )
    assert corrected.status_code == 422

    corrected = api_client.post(
        f"/sources/{source['id']}/ingest",
        headers=headers,
        json={
            "retrieved_at": retrieved_at,
            "records": [
                {
                    "title": "Corrected bridge deck repairs",
                    "location": "Gander",
                    "region": "Central Newfoundland",
                    "closing_date": "2099-02-15",
                    "status": "open",
                    "source_reference": "AUTH-2026-01",
                }
            ],
        },
    )
    assert corrected.status_code == 200
    assert corrected.json()["records_updated"] == 1
    assert api_client.get("/tenders/upcoming").json()[0]["title"] == "Corrected bridge deck repairs"

    archived = api_client.post(
        f"/sources/{source['id']}/ingest",
        headers=headers,
        json={
            "retrieved_at": retrieved_at,
            "records": [],
            "archived_references": ["AUTH-2026-01"],
        },
    )
    assert archived.status_code == 200
    assert archived.json()["records_archived"] == 1
    assert api_client.get("/tenders/upcoming").json() == []
    revisions = api_client.get(
        "/tenders/1/revisions",
        headers=headers,
    )
    assert revisions.status_code == 200
    assert revisions.json()[0]["action"] == "archived"
    assert revisions.json()[0]["snapshot"]["before"]["is_active"] is True
    assert revisions.json()[0]["snapshot"]["after"]["is_active"] is False
    runs = api_client.get(f"/sources/{source['id']}/runs", headers=headers)
    assert runs.status_code == 200
    assert len(runs.json()) == 3


def test_public_document_is_hash_deduplicated_and_requires_human_approval(client, tmp_path, monkeypatch):
    from nlti.api import main

    monkeypatch.setattr(main.settings, "document_store_path", str(tmp_path))
    api_client, _ = client
    headers = create_admin(client)
    source = create_reviewed_source(api_client, headers)
    document = b"Title: Roof replacement\nLocation: Gander\nRegion: Central Newfoundland\n"
    upload = {
        "source_id": str(source["id"]),
        "source_url": "https://example.ca/procurement/notice.pdf",
    }
    files = {"document": ("notice.txt", document, "text/plain")}
    queued = api_client.post("/documents", headers=headers, data=upload, files=files)
    assert queued.status_code == 201
    row = queued.json()
    assert row["status"] == "needs_review"
    assert row["proposed_fields"]["title"] == "Roof replacement"
    assert row["field_confidence"]["title"] > 0
    assert api_client.get(f"/documents/{row['id']}/file", headers=headers).content == document
    duplicate = api_client.post("/documents", headers=headers, data=upload, files=files)
    assert duplicate.status_code == 409

    approved = api_client.post(
        f"/documents/{row['id']}/review",
        headers=headers,
        json={
            "decision": "approve",
            "reason": "Compared every entered field with the source notice.",
            "tender": {
                "title": "Roof replacement",
                "location": "Gander",
                "region": "Central Newfoundland",
                "closing_date": "2099-01-15",
                "status": "open",
                "source_reference": "AUTH-DOC-01",
            },
        },
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["tender_id"] is not None
    assert api_client.get("/tenders/upcoming").json()[0]["source_name"] == source["name"]

    import fitz

    pdf = fitz.open()
    pdf.new_page().insert_text((72, 72), "Title: Supplemental roof notice\nLocation: Gander")
    pdf_bytes = pdf.tobytes()
    pdf.close()
    pdf_upload = api_client.post(
        "/documents",
        headers=headers,
        data=upload,
        files={"document": ("notice.pdf", pdf_bytes, "application/pdf")},
    )
    assert pdf_upload.status_code == 201
    assert pdf_upload.json()["proposed_fields"]["title"] == "Supplemental roof notice"
    malformed = api_client.post(
        "/documents",
        headers=headers,
        data=upload,
        files={"document": ("broken.pdf", b"not a PDF", "application/pdf")},
    )
    assert malformed.status_code == 422


def test_contractor_profile_notifications_and_verified_outcome_coverage(client, monkeypatch):
    api_client, sessions = client
    token = register_and_login(api_client)
    headers = {"Authorization": f"Bearer {token}"}
    profile = api_client.patch(
        "/contractors/me",
        headers=headers,
        json={"trades": ["roofing"], "regions": ["Labrador"], "insurance_verified": True},
    )
    assert profile.status_code == 200
    assert profile.json()["insurance_verified"] is False
    preferences = api_client.put(
        "/contractors/me/notifications",
        headers=headers,
        json={"enabled": True, "minimum_match_score": 0},
    )
    assert preferences.status_code == 200
    with sessions() as db:
        db.add(
            Tender(
                title="Labrador roof tender",
                location="Happy Valley-Goose Bay",
                region="Labrador",
                trades=["roofing"],
                closing_date=date.today() + timedelta(days=10),
                status="open",
                source_name="Verified example source",
                source_reference="NOTIFY-001",
                is_demo=False,
            )
        )
        db.add(
            Tender(
                title="Past Labrador roof tender",
                location="Happy Valley-Goose Bay",
                region="Labrador",
                trades=["roofing"],
                closing_date=date.today() - timedelta(days=1),
                status="closed",
                source_name="Verified example source",
                source_reference="NOTIFY-PAST-001",
                is_demo=False,
            )
        )
        db.commit()
    matches = api_client.post("/matches/1", headers=headers)
    assert matches.status_code == 200
    assert [match["tender_title"] for match in matches.json()] == ["Labrador roof tender"]
    notifications = api_client.get("/notifications", headers=headers)
    assert notifications.status_code == 200
    assert notifications.json()[0]["tender_title"] == "Labrador roof tender"

    admin_headers = create_admin(client)
    source = create_reviewed_source(api_client, admin_headers)
    with sessions() as db:
        historical = Tender(
            title="Completed public works",
            location="Gander",
            region="Central Newfoundland",
            closing_date=date.today() - timedelta(days=20),
            status="closed",
            source_name=source["name"],
            source_id=source["id"],
            source_reference="HIST-001",
            is_demo=False,
        )
        db.add(historical)
        db.commit()
        historical_id = historical.id
    outcome = api_client.post(
        f"/tenders/{historical_id}/outcome",
        headers=admin_headers,
        json={
            "source_id": source["id"],
            "outcome": "awarded",
            "published_at": date.today().isoformat(),
            "source_url": "https://example.ca/procurement/outcomes/HIST-001",
            "source_reference": "OUTCOME-001",
            "verification_method": "Compared with the official public award notice.",
        },
    )
    assert outcome.status_code == 200
    assert "award_amount" not in outcome.json()
    assert "contractor_name" not in outcome.json()
    coverage = api_client.get("/history/coverage").json()
    assert coverage["eligible_historical_notices"] == 2
    assert coverage["verified_outcomes"] == 1
    assert coverage["missing_outcomes"] == 1
    assert coverage["coverage_percent"] == 50.0

    monkeypatch.setattr("nlti.api.main.settings.nlti_env", "production")
    unverified_token = register_and_login(api_client, "unverified@example.ca")
    unverified_headers = {"Authorization": f"Bearer {unverified_token}"}
    assert api_client.post("/matches/2", headers=unverified_headers).status_code == 403
    account_id = api_client.get("/auth/me", headers=unverified_headers).json()["id"]
    assert api_client.post(f"/accounts/{account_id}/verify", headers=admin_headers).status_code == 200
    assert api_client.post("/matches/2", headers=unverified_headers).status_code == 200
