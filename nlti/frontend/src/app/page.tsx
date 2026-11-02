"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

const API_BASE = (process.env.NEXT_PUBLIC_NLTI_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

type Tender = {
  id: number;
  title: string;
  location: string;
  region: string;
  trades: string[];
  closing_date: string | null;
  estimated_value: number | null;
  status: string;
  source_name: string;
  source_url: string | null;
};

type Geography = { id: number; code: string; name: string; geography_type: string };
type Source = {
  id: number;
  name: string;
  owner: string;
  official_url: string;
  access_method: string;
  update_frequency: string | null;
  health_status: string;
  health_message: string | null;
  last_checked_at: string | null;
};
type Account = { id: number; email: string; role: string; contractor_id: number | null; email_verified_at: string | null };
type ContractorProfile = {
  id: number;
  company_name: string;
  trades: string[];
  regions: string[];
  crew_capacity: number | null;
  equipment: string[];
  certifications: string[];
  insurance_verified: boolean;
};
type NotificationPreferences = { enabled: boolean; minimum_match_score: number };
type ContractorNotification = {
  id: number;
  tender_id: number;
  tender_title: string;
  score: number;
  created_at: string;
  read_at: string | null;
};
type PublicDocument = {
  id: number;
  source_id: number;
  source_url: string;
  file_name: string;
  sha256: string;
  status: string;
  proposed_fields: Record<string, string>;
  field_confidence: Record<string, number>;
  extractor_name: string | null;
  extractor_version: string | null;
  prompt_version: string | null;
};
type VerifiedOutcome = {
  id: number;
  tender_id: number;
  tender_title: string;
  source_name: string;
  outcome: string;
  published_at: string | null;
  source_url: string;
  source_reference: string;
  verification_method: string;
};
type HistoryCoverage = {
  eligible_historical_notices: number;
  verified_outcomes: number;
  missing_outcomes: number;
  coverage_percent: number | null;
  methodology: string;
};
type Summary = {
  upcoming_tenders: number;
  historical_tenders: number;
  reviewed_sources: number;
  verified_outcomes: number;
};
type DocumentDraft = {
  title: string;
  location: string;
  region: string;
  closing_date: string;
  source_reference: string;
  status: string;
};

async function api<T>(path: string, token?: string | null, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers, cache: "no-store" });
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const body = await response.json();
      message = typeof body.detail === "string" ? body.detail : message;
    } catch {
      // Keep the HTTP status when the server does not return JSON.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

function EmptyState({ title, children }: { title: string; children: string }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <p>{children}</p>
    </div>
  );
}

function TenderCard({ tender, historical }: { tender: Tender; historical: boolean }) {
  const amount =
    tender.estimated_value === null
      ? "Not published"
      : new Intl.NumberFormat("en-CA", { style: "currency", currency: "CAD", maximumFractionDigits: 0 }).format(
          tender.estimated_value,
        );
  return (
    <article className="tender-card">
      <div className="tender-name">
        <strong>{tender.title}</strong>
        <small>{tender.location}{tender.region ? ` · ${tender.region}` : ""}</small>
      </div>
      <div className="tender-meta">
        <span>{tender.closing_date ?? "Not published"}</span>
        <small>{historical ? "Closing date" : "Closes"}</small>
      </div>
      <div className="tender-meta">
        <span>{amount}</span>
        <small>Published value</small>
      </div>
      <div className="tender-status">
        <span className="status-chip">{tender.status}</span>
      </div>
      {tender.source_url ? (
        <a className="tender-action" href={tender.source_url} target="_blank" rel="noopener noreferrer">
          View source ↗
        </a>
      ) : (
        <span className="tender-action">Source unavailable</span>
      )}
    </article>
  );
}

export default function Home() {
  const [upcoming, setUpcoming] = useState<Tender[] | null>(null);
  const [historical, setHistorical] = useState<Tender[] | null>(null);
  const [sources, setSources] = useState<Source[] | null>(null);
  const [geographies, setGeographies] = useState<Geography[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [historyCoverage, setHistoryCoverage] = useState<HistoryCoverage | null>(null);
  const [outcomes, setOutcomes] = useState<VerifiedOutcome[]>([]);
  const [profile, setProfile] = useState<ContractorProfile | null>(null);
  const [notificationPreferences, setNotificationPreferences] = useState<NotificationPreferences>({ enabled: false, minimum_match_score: 0 });
  const [notifications, setNotifications] = useState<ContractorNotification[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [documents, setDocuments] = useState<PublicDocument[]>([]);
  const [documentDrafts, setDocumentDrafts] = useState<Record<number, DocumentDraft>>({});
  const [workflowNotice, setWorkflowNotice] = useState("");
  const [notice, setNotice] = useState("");
  const [isError, setIsError] = useState(false);
  const [search, setSearch] = useState("");
  const [region, setRegion] = useState("");
  const [trade, setTrade] = useState("");
  const [appliedFilters, setAppliedFilters] = useState({ search: "", region: "", trade: "" });
  const [account, setAccount] = useState<Account | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "register" | null>(null);
  const [authError, setAuthError] = useState("");
  const [authBusy, setAuthBusy] = useState(false);
  const [verificationUrl, setVerificationUrl] = useState("");
  const dialogRef = useRef<HTMLDialogElement>(null);

  const loadSummary = useCallback(async () => {
    try {
      setSummary(await api<Summary>("/summary"));
    } catch (error) {
      setNotice(`Dashboard totals are unavailable: ${error instanceof Error ? error.message : "API error"}`);
      setIsError(true);
    }
  }, []);

  const loadHistory = useCallback(async () => {
    try {
      const [coverage, verified] = await Promise.all([
        api<HistoryCoverage>("/history/coverage"),
        api<VerifiedOutcome[]>("/outcomes"),
      ]);
      setHistoryCoverage(coverage);
      setOutcomes(verified);
    } catch {
      setHistoryCoverage(null);
      setOutcomes([]);
    }
  }, []);

  const loadDocuments = useCallback(async (token: string) => {
    try {
      const rows = await api<PublicDocument[]>("/documents?status=needs_review", token);
      setDocuments(rows);
      setDocumentDrafts(Object.fromEntries(rows.map((document) => [document.id, {
        title: document.proposed_fields.title ?? "",
        location: document.proposed_fields.location ?? "",
        region: document.proposed_fields.region ?? "",
        closing_date: document.proposed_fields.closing_date ?? "",
        source_reference: document.proposed_fields.source_reference ?? "",
        status: "open",
      }])));
    } catch {
      setDocuments([]);
    }
  }, []);

  const loadTenders = useCallback(async () => {
    const params = new URLSearchParams({ limit: "100" });
    if (appliedFilters.search) params.set("q", appliedFilters.search);
    if (appliedFilters.region) params.set("region", appliedFilters.region);
    if (appliedFilters.trade) params.set("trade", appliedFilters.trade);
    try {
      const [next, past] = await Promise.all([
        api<Tender[]>(`/tenders/upcoming?${params}`),
        api<Tender[]>(`/tenders/historical?${params}`),
      ]);
      setUpcoming(next);
      setHistorical(past);
    } catch (error) {
      setNotice(`Tender data could not be loaded: ${error instanceof Error ? error.message : "API error"}`);
      setIsError(true);
    }
  }, [appliedFilters]);

  const loadReferences = useCallback(async () => {
    setNotice("");
    setIsError(false);
    const results = await Promise.allSettled([
      api<Geography[]>("/geographies"),
      api<Source[]>("/sources"),
    ]);
    if (results[0].status === "fulfilled") setGeographies(results[0].value);
    else {
      setNotice("Geography reference data is unavailable.");
      setIsError(true);
    }
    if (results[1].status === "fulfilled") setSources(results[1].value);
    else {
      setNotice("The reviewed source registry is unavailable.");
      setIsError(true);
    }
  }, []);

  useEffect(() => {
    void loadReferences();
  }, [loadReferences]);

  useEffect(() => {
    void loadSummary();
  }, [loadSummary]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    void loadTenders();
  }, [loadTenders]);

  useEffect(() => {
    const stored = sessionStorage.getItem("nlti_access_token");
    if (!stored) return;
    void api<Account>("/auth/me", stored)
      .then(setAccount)
      .catch(() => {
        sessionStorage.removeItem("nlti_access_token");
      });
  }, []);

  useEffect(() => {
    const verificationToken = new URLSearchParams(window.location.search).get("verify");
    if (!verificationToken) return;
    void api<Account>("/auth/verify-email", null, {
      method: "POST",
      body: JSON.stringify({ token: verificationToken }),
    }).then((verified) => {
      setAccount(verified);
      setVerificationUrl("");
      setWorkflowNotice("Email verified. Contractor features are available.");
    }).catch((error) => {
      setWorkflowNotice(error instanceof Error ? error.message : "Email verification failed.");
    }).finally(() => {
      window.history.replaceState({}, "", window.location.pathname);
    });
  }, []);

  useEffect(() => {
    if (!account) {
      setProfile(null);
      setNotifications([]);
      setAccounts([]);
      setDocuments([]);
      return;
    }
    const token = sessionStorage.getItem("nlti_access_token");
    if (!token) return;
    if (account.role === "contractor") {
      void Promise.all([
        api<ContractorProfile>("/contractors/me", token),
        api<NotificationPreferences>("/contractors/me/notifications", token),
        api<ContractorNotification[]>("/notifications", token),
      ]).then(([nextProfile, preferences, nextNotifications]) => {
        setProfile(nextProfile);
        setNotificationPreferences(preferences);
        setNotifications(nextNotifications);
      }).catch(() => setWorkflowNotice("Contractor workspace data is unavailable."));
    }
    if (account.role === "admin") {
      void Promise.all([
        api<Account[]>("/accounts", token),
        loadDocuments(token),
      ]).then(([nextAccounts]) => setAccounts(nextAccounts))
        .catch(() => setWorkflowNotice("Administrative workflow data is unavailable."));
    }
  }, [account, loadDocuments]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (authMode && !dialog.open) dialog.showModal();
    else if (!authMode && dialog.open) dialog.close();
  }, [authMode]);

  function showAuth(mode: "login" | "register") {
    setAuthError("");
    setAuthMode(mode);
  }

  async function submitAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const creatingAccount = authMode === "register";
    setAuthBusy(true);
    setAuthError("");
    const data = new FormData(event.currentTarget);
    const email = String(data.get("email") ?? "").trim();
    const password = String(data.get("password") ?? "");
    try {
      if (authMode === "register") {
        await api<Account>("/auth/register", null, {
          method: "POST",
          body: JSON.stringify({
            email,
            password,
            company_name: String(data.get("company_name") ?? "").trim(),
            trades: [],
            regions: [],
            equipment: [],
            certifications: [],
          }),
        });
      }
      const result = await api<{ access_token: string }>("/auth/token", null, {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      const signedInAccount = await api<Account>("/auth/me", result.access_token);
      sessionStorage.setItem("nlti_access_token", result.access_token);
      setAccount(signedInAccount);
      setAuthMode(null);
      if (creatingAccount && !signedInAccount.email_verified_at) {
        const verification = await api<{ verification_url: string | null }>("/auth/verification", result.access_token, { method: "POST" });
        setVerificationUrl(verification.verification_url ?? "");
        setWorkflowNotice(verification.verification_url
          ? "Open the development verification link below to confirm your email."
          : "Verification email sent. Check your inbox to unlock contractor features.");
      }
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Authentication failed.");
    } finally {
      setAuthBusy(false);
    }
  }

  function signOut() {
    sessionStorage.removeItem("nlti_access_token");
    setAccount(null);
  }

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAppliedFilters({ search: search.trim(), region, trade: trade.trim() });
  }

  function accessToken() {
    return sessionStorage.getItem("nlti_access_token");
  }

  async function requestVerification() {
    const token = accessToken();
    if (!token) return;
    try {
      const verification = await api<{ verification_url: string | null }>("/auth/verification", token, { method: "POST" });
      setVerificationUrl(verification.verification_url ?? "");
      setWorkflowNotice(verification.verification_url
        ? "Open the development verification link below to confirm your email."
        : "Verification email sent. Check your inbox.");
    } catch (error) {
      setWorkflowNotice(error instanceof Error ? error.message : "Verification email could not be sent.");
    }
  }

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = accessToken();
    if (!token) return;
    const data = new FormData(event.currentTarget);
    try {
      const updated = await api<ContractorProfile>("/contractors/me", token, {
        method: "PATCH",
        body: JSON.stringify({
          company_name: String(data.get("company_name") ?? "").trim(),
          trades: String(data.get("trades") ?? "").split(",").map((item) => item.trim()).filter(Boolean),
          regions: String(data.get("regions") ?? "").split(",").map((item) => item.trim()).filter(Boolean),
          equipment: String(data.get("equipment") ?? "").split(",").map((item) => item.trim()).filter(Boolean),
          certifications: String(data.get("certifications") ?? "").split(",").map((item) => item.trim()).filter(Boolean),
          crew_capacity: data.get("crew_capacity") ? Number(data.get("crew_capacity")) : null,
        }),
      });
      setProfile(updated);
      setWorkflowNotice("Contractor profile saved.");
    } catch (error) {
      setWorkflowNotice(error instanceof Error ? error.message : "Profile could not be saved.");
    }
  }

  async function savePreferences(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = accessToken();
    if (!token) return;
    const data = new FormData(event.currentTarget);
    const preferences = {
      enabled: data.get("enabled") === "on",
      minimum_match_score: Number(data.get("minimum_match_score") ?? 0),
    };
    try {
      setNotificationPreferences(await api<NotificationPreferences>("/contractors/me/notifications", token, {
        method: "PUT",
        body: JSON.stringify(preferences),
      }));
      setWorkflowNotice("Notification preferences saved.");
    } catch (error) {
      setWorkflowNotice(error instanceof Error ? error.message : "Preferences could not be saved.");
    }
  }

  async function runMatches() {
    const token = accessToken();
    if (!token || !account?.contractor_id) return;
    try {
      await api(`/matches/${account.contractor_id}`, token, { method: "POST" });
      setNotifications(await api<ContractorNotification[]>("/notifications", token));
      setWorkflowNotice("Screening completed. Matches are not eligibility decisions.");
    } catch (error) {
      setWorkflowNotice(error instanceof Error ? error.message : "Matching is unavailable.");
    }
  }

  async function markNotificationRead(notificationId: number) {
    const token = accessToken();
    if (!token) return;
    try {
      await api(`/notifications/${notificationId}/read`, token, { method: "POST" });
      setNotifications((current) => current.map((item) => item.id === notificationId
        ? { ...item, read_at: new Date().toISOString() }
        : item));
    } catch (error) {
      setWorkflowNotice(error instanceof Error ? error.message : "Notification could not be updated.");
    }
  }

  async function verifyAccount(accountId: number) {
    const token = accessToken();
    if (!token) return;
    try {
      const updated = await api<Account>(`/accounts/${accountId}/verify`, token, { method: "POST" });
      setAccounts((current) => current.map((item) => item.id === accountId ? updated : item));
      setWorkflowNotice(`Verified ${updated.email}.`);
    } catch (error) {
      setWorkflowNotice(error instanceof Error ? error.message : "Account verification failed.");
    }
  }

  async function submitDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = accessToken();
    if (!token) return;
    const form = new FormData(event.currentTarget);
    try {
      await api<PublicDocument>("/documents", token, { method: "POST", body: form });
      event.currentTarget.reset();
      await loadDocuments(token);
      setWorkflowNotice("Public document queued for human review.");
    } catch (error) {
      setWorkflowNotice(error instanceof Error ? error.message : "Document upload failed.");
    }
  }

  async function reviewDocument(form: HTMLFormElement, document: PublicDocument, decision: "approve" | "reject") {
    const token = accessToken();
    if (!token) return;
    const data = new FormData(form);
    const draft = documentDrafts[document.id];
    const body: { decision: string; reason: string; tender?: Record<string, unknown> } = {
      decision,
      reason: String(data.get("reason") ?? "").trim(),
    };
    if (decision === "approve") {
      body.tender = {
        title: draft.title,
        location: draft.location,
        region: draft.region,
        closing_date: draft.closing_date || null,
        source_reference: draft.source_reference || null,
        status: draft.status,
        source_name: "Reviewed public notice",
        source_url: document.source_url,
      };
    }
    try {
      await api(`/documents/${document.id}/review`, token, { method: "POST", body: JSON.stringify(body) });
      await Promise.all([loadDocuments(token), loadTenders(), loadSummary()]);
      setWorkflowNotice(`Document ${decision === "approve" ? "approved" : "rejected"}.`);
    } catch (error) {
      setWorkflowNotice(error instanceof Error ? error.message : "Document review failed.");
    }
  }

  async function submitSource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = accessToken();
    if (!token) return;
    const data = new FormData(event.currentTarget);
    try {
      await api("/sources", token, {
        method: "POST",
        body: JSON.stringify({
          name: data.get("name"),
          owner: data.get("owner"),
          official_url: data.get("official_url"),
          access_method: data.get("access_method"),
          update_frequency: data.get("update_frequency"),
          terms_url: data.get("terms_url"),
          terms_reviewed_at: data.get("terms_reviewed_at") ? new Date(String(data.get("terms_reviewed_at"))).toISOString() : null,
          permitted_reuse: data.get("permitted_reuse") === "on",
          rate_limit_notes: data.get("rate_limit_notes"),
          is_active: data.get("activate") === "on",
        }),
      });
      event.currentTarget.reset();
      await loadReferences();
      setWorkflowNotice("Source registry entry saved.");
    } catch (error) {
      setWorkflowNotice(error instanceof Error ? error.message : "Source could not be saved.");
    }
  }

  async function submitSourceBatch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = accessToken();
    if (!token) return;
    const data = new FormData(event.currentTarget);
    try {
      const records = JSON.parse(String(data.get("records") ?? "[]")) as unknown;
      const archived_references = String(data.get("archived_references") ?? "")
        .split("\n").map((reference) => reference.trim()).filter(Boolean);
      if (!Array.isArray(records)) throw new Error("Records must be a JSON array.");
      const result = await api<{ records_created: number; records_updated: number; records_archived: number }>(
        `/sources/${String(data.get("source_id"))}/ingest`,
        token,
        { method: "POST", body: JSON.stringify({ retrieved_at: new Date().toISOString(), records, archived_references }) },
      );
      setWorkflowNotice(`Batch complete: ${result.records_created} new, ${result.records_updated} corrected, ${result.records_archived} archived.`);
      event.currentTarget.reset();
      await Promise.all([loadReferences(), loadTenders(), loadSummary()]);
    } catch (error) {
      setWorkflowNotice(error instanceof Error ? error.message : "Source batch could not be imported.");
    }
  }

  async function submitOutcome(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = accessToken();
    if (!token) return;
    const data = new FormData(event.currentTarget);
    try {
      await api(`/tenders/${String(data.get("tender_id"))}/outcome`, token, {
        method: "POST",
        body: JSON.stringify({
          source_id: Number(data.get("source_id")),
          outcome: data.get("outcome"),
          published_at: data.get("published_at") || null,
          source_url: data.get("source_url"),
          source_reference: data.get("source_reference"),
          verification_method: data.get("verification_method"),
        }),
      });
      event.currentTarget.reset();
      await Promise.all([loadHistory(), loadSummary()]);
      setWorkflowNotice("Public outcome saved with verification provenance.");
    } catch (error) {
      setWorkflowNotice(error instanceof Error ? error.message : "Outcome could not be saved.");
    }
  }

  async function recordSourceCheck(event: FormEvent<HTMLFormElement>, sourceId: number) {
    event.preventDefault();
    const token = accessToken();
    if (!token) return;
    const data = new FormData(event.currentTarget);
    try {
      await api(`/sources/${sourceId}/checks`, token, {
        method: "POST",
        body: JSON.stringify({
          status: data.get("status"),
          checked_at: new Date().toISOString(),
          message: data.get("message"),
        }),
      });
      await loadReferences();
      setWorkflowNotice("Source health check recorded.");
    } catch (error) {
      setWorkflowNotice(error instanceof Error ? error.message : "Source check could not be recorded.");
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#overview" aria-label="NLTI home">
          <span className="brand-mark" aria-hidden="true">N</span>
          <span><strong>NLTI</strong><small>PUBLIC PROCUREMENT INTELLIGENCE</small></span>
        </a>
        <div className="sidebar-label">WORKSPACE</div>
        <nav className="main-nav" aria-label="Main navigation">
          <a className="nav-link active" href="#overview"><span>◫</span> Overview</a>
          <a className="nav-link" href="#upcoming"><span>◷</span> Upcoming tenders</a>
          <a className="nav-link" href="#historical"><span>↗</span> Historical tenders</a>
          <a className="nav-link" href="#sources"><span>≋</span> Source registry</a>
          {account?.role === "contractor" && <a className="nav-link" href="#contractor-workspace"><span>◉</span> My workspace</a>}
          {account?.role === "admin" && <a className="nav-link" href="#admin-workflows"><span>⚙</span> Admin workflows</a>}
          <a className="nav-link" href="#history-intelligence"><span>▤</span> History coverage</a>
        </nav>
        <div className="sidebar-note">
          <span className="status-dot" />
          <div><strong>Data integrity first</strong><p>Notices are shown with their source. No source connections are enabled by default.</p></div>
        </div>
        <div className="sidebar-bottom">
          <span className="province-tag">NL</span>
          <div><strong>Newfoundland &amp; Labrador</strong><small>Province-wide workspace</small></div>
        </div>
      </aside>

      <main className="main-content" id="overview">
        <header className="topbar">
          <div className="breadcrumb">NLTI <span>/</span> <strong>Intelligence</strong></div>
          <div className="account-area">
            <span className="account-label">{account?.email ?? "Public view"}</span>
            {account ? (
              <button className="button button-quiet" onClick={signOut} type="button">Sign out</button>
            ) : (
              <button className="button button-quiet" onClick={() => showAuth("login")} type="button">Sign in</button>
            )}
          </div>
        </header>

        <section className="page-heading">
          <div>
            <div className="eyebrow"><span className="live-pip" /> PROVINCIAL CONSTRUCTION INTELLIGENCE</div>
            <h1>Procurement overview</h1>
            <p className="lead">A source-attributed view of public construction opportunities across Newfoundland and Labrador.</p>
          </div>
          <button className="button button-outline" onClick={() => void Promise.all([loadReferences(), loadSummary(), loadTenders()])} type="button"><span aria-hidden="true">↻</span> Refresh data</button>
        </section>

        {notice && <div className={`notice${isError ? " error" : ""}`} role={isError ? "alert" : "status"}>{notice}</div>}

        <section className="metric-grid" aria-label="Live data counts">
          <article className="metric-card">
            <div className="metric-top"><span>UPCOMING NOTICES</span><span className="metric-icon teal">◷</span></div>
            <div className="metric-value">{summary?.upcoming_tenders ?? "—"}</div>
            <div className="metric-caption">Published closing date is today or later</div>
          </article>
          <article className="metric-card">
            <div className="metric-top"><span>HISTORICAL NOTICES</span><span className="metric-icon blue">↗</span></div>
            <div className="metric-value">{summary?.historical_tenders ?? "—"}</div>
            <div className="metric-caption">Past closing dates or completed notices</div>
          </article>
          <article className="metric-card">
            <div className="metric-top"><span>REVIEWED SOURCES</span><span className="metric-icon gold">≋</span></div>
            <div className="metric-value">{summary?.reviewed_sources ?? "—"}</div>
            <div className="metric-caption">Terms checked and reuse marked as permitted</div>
          </article>
          <article className="metric-card">
            <div className="metric-top"><span>VERIFIED OUTCOMES</span><span className="metric-icon coral">✓</span></div>
            <div className="metric-value">{summary?.verified_outcomes ?? "—"}</div>
            <div className="metric-caption">Independently checked public notices</div>
          </article>
        </section>

        {workflowNotice && <div className="notice" role="status">{workflowNotice}</div>}
        {verificationUrl && <a className="verification-link" href={verificationUrl}>Verify this development account</a>}

        <section className="filter-panel" aria-label="Tender search and filters">
          <form className="filter-form" onSubmit={submitSearch}>
            <label className="search-field">
              <span aria-hidden="true">⌕</span>
              <span className="sr-only">Search tenders</span>
              <input value={search} onChange={(event) => setSearch(event.target.value)} type="search" placeholder="Search project, location, or keywords" />
            </label>
            <label className="filter-field">
              <span className="sr-only">Filter by region</span>
              <select value={region} onChange={(event) => setRegion(event.target.value)}>
                <option value="">All regions</option>
                {geographies.filter((item) => item.geography_type === "region").map((item) => (
                  <option value={item.name} key={item.id}>{item.name}</option>
                ))}
              </select>
            </label>
            <label className="filter-field">
              <span className="sr-only">Filter by trade</span>
              <input value={trade} onChange={(event) => setTrade(event.target.value)} type="search" placeholder="Trade" />
            </label>
            <button className="button button-primary" type="submit">Search</button>
          </form>
          <div className="filter-caption">Showing published information only. Missing dates and values are not estimated. Lists are limited to 100 matches.</div>
        </section>

        <section className="section-block" id="upcoming">
          <div className="section-heading">
            <div><div className="eyebrow">LIVE OPPORTUNITIES</div><h2>Upcoming tenders</h2></div>
            <a className="text-link" href="#upcoming">View all <span aria-hidden="true">→</span></a>
          </div>
          <div className="tender-list" aria-live="polite">
            {upcoming === null ? <div className="loading-state">Tender data is not available yet.</div> : upcoming.length ? upcoming.map((tender) => <TenderCard key={tender.id} tender={tender} historical={false} />) : (
              <EmptyState title="No verified upcoming notices yet">
                This workspace has no verified upcoming notices for these filters. Procurement sources are not connected until their access and reuse terms have been reviewed.
              </EmptyState>
            )}
          </div>
        </section>

        <section className="section-block historical-section" id="historical">
          <div className="section-heading">
            <div><div className="eyebrow">PUBLIC RECORD</div><h2>Historical tenders</h2></div>
            <a className="text-link" href="#historical">View all <span aria-hidden="true">→</span></a>
          </div>
          <div className="tender-list" aria-live="polite">
            {historical === null ? <div className="loading-state">Tender data is not available yet.</div> : historical.length ? historical.map((tender) => <TenderCard key={tender.id} tender={tender} historical />) : (
              <EmptyState title="No historical notices found">
                No historical procurement records match these filters. No award or bid data is inferred.
              </EmptyState>
            )}
          </div>
        </section>

        <section className="section-block" id="sources">
          <div className="section-heading">
            <div><div className="eyebrow">TRANSPARENCY</div><h2>Reviewed source registry</h2></div>
            <span className="registry-lock">Only approved public sources</span>
          </div>
          {sources === null ? (
            <div className="loading-state">Source registry is not available yet.</div>
          ) : sources.length ? (
            <div className="source-grid">
              {sources.map((source) => (
                <article className="source-card" key={source.id}>
                  <strong>{source.name}</strong>
                  <p>{source.owner} · {source.access_method} access · {source.update_frequency ?? "No cadence recorded"}</p>
                  <div className={`source-health ${source.health_status}`}>
                    <span>{source.health_status}</span>
                    {source.last_checked_at && <time dateTime={source.last_checked_at}>{new Date(source.last_checked_at).toLocaleString("en-CA")}</time>}
                  </div>
                  {source.health_message && <small className="source-health-message">{source.health_message}</small>}
                  <a href={source.official_url} target="_blank" rel="noopener noreferrer">Open official source ↗</a>
                  {account?.role === "admin" && (
                    <form className="inline-form" onSubmit={(event) => void recordSourceCheck(event, source.id)}>
                      <label>Health<select name="status" defaultValue="healthy"><option value="healthy">Healthy</option><option value="warning">Warning</option><option value="failed">Failed</option></select></label>
                      <label>Note<input name="message" maxLength={1000} placeholder="Optional check note" /></label>
                      <button className="button button-outline" type="submit">Record check</button>
                    </form>
                  )}
                </article>
              ))}
            </div>
          ) : (
            <EmptyState title="No procurement sources have been approved">
              The registry is intentionally empty until a source&apos;s owner, access method, terms, and reuse permission are recorded and reviewed.
            </EmptyState>
          )}
        </section>

        {account?.role === "contractor" && (
          <section className="section-block" id="contractor-workspace">
            <div className="section-heading">
              <div><div className="eyebrow">PRIVATE ACCOUNT</div><h2>Contractor workspace</h2></div>
              <button className="button button-outline" type="button" onClick={() => void runMatches()}>Refresh matches</button>
            </div>
            <div className="workflow-grid">
              <article className="workflow-panel">
                <h3>Company profile</h3>
                {!account.email_verified_at && <div className="verification-prompt"><span>Email verification pending</span><button className="button button-outline" type="button" onClick={() => void requestVerification()}>Send verification link</button></div>}
                <form className="workflow-form" key={profile?.id ?? "profile-loading"} onSubmit={saveProfile}>
                  <label>Company name<input name="company_name" defaultValue={profile?.company_name ?? ""} minLength={2} required /></label>
                  <label>Trades<input name="trades" defaultValue={profile?.trades.join(", ") ?? ""} placeholder="Roofing, electrical" /></label>
                  <label>Service regions<input name="regions" defaultValue={profile?.regions.join(", ") ?? ""} placeholder="Labrador, Avalon Peninsula" /></label>
                  <label>Crew capacity<input name="crew_capacity" type="number" min="0" defaultValue={profile?.crew_capacity ?? ""} /></label>
                  <label>Equipment<input name="equipment" defaultValue={profile?.equipment.join(", ") ?? ""} /></label>
                  <label>Qualifications<input name="certifications" defaultValue={profile?.certifications.join(", ") ?? ""} /></label>
                  <p className="field-note">Insurance and eligibility are not self-verified by profile edits.</p>
                  <button className="button button-primary" type="submit">Save profile</button>
                </form>
              </article>
              <article className="workflow-panel">
                <h3>Opportunity alerts</h3>
                <form className="workflow-form" key={`${notificationPreferences.enabled}-${notificationPreferences.minimum_match_score}`} onSubmit={savePreferences}>
                  <label className="check-row"><input name="enabled" type="checkbox" defaultChecked={notificationPreferences.enabled} /> Enable in-app match alerts</label>
                  <label>Minimum score <output>{notificationPreferences.minimum_match_score}</output>
                    <input name="minimum_match_score" type="range" min="0" max="100" step="5" defaultValue={notificationPreferences.minimum_match_score} />
                  </label>
                  <p className="field-note">Alerts are private to this account and use explainable screening, not eligibility decisions.</p>
                  <button className="button button-primary" type="submit">Save alert settings</button>
                </form>
              </article>
            </div>
            <div className="section-heading subsection-heading"><div><div className="eyebrow">ACCOUNT ONLY</div><h3>Opportunity notifications</h3></div></div>
            {notifications.length ? (
              <div className="notification-list">
                {notifications.map((notification) => (
                  <article className={`notification-row${notification.read_at ? " read" : ""}`} key={notification.id}>
                    <div><strong>{notification.tender_title}</strong><span>Screening score {notification.score.toFixed(0)} · {new Date(notification.created_at).toLocaleDateString("en-CA")}</span></div>
                    {!notification.read_at && <button className="button button-outline" type="button" onClick={() => void markNotificationRead(notification.id)}>Mark read</button>}
                  </article>
                ))}
              </div>
            ) : <EmptyState title="No notifications yet">Run a screening refresh after saving your profile. Alerts only appear when you opt in.</EmptyState>}
          </section>
        )}

        {account?.role === "admin" && (
          <section className="section-block" id="admin-workflows">
            <div className="section-heading">
              <div><div className="eyebrow">REVIEW AND OPERATIONS</div><h2>Administrative workflows</h2></div>
            </div>
            <div className="workflow-grid">
              <article className="workflow-panel">
                <h3>Register a procurement source</h3>
                <form className="workflow-form" onSubmit={submitSource}>
                  <label>Source name<input name="name" minLength={2} required /></label>
                  <label>Owner<input name="owner" minLength={2} required /></label>
                  <label>Official URL<input name="official_url" type="url" required /></label>
                  <label>Access method<select name="access_method"><option value="manual">Manual</option><option value="api">API</option><option value="feed">Feed</option><option value="download">Download</option></select></label>
                  <label>Update cadence<input name="update_frequency" placeholder="Manual review, on demand" maxLength={100} /></label>
                  <label>Terms URL<input name="terms_url" type="url" /></label>
                  <label>Terms reviewed at<input name="terms_reviewed_at" type="datetime-local" /></label>
                  <label>Access and rate-limit notes<textarea name="rate_limit_notes" rows={2} maxLength={500} required /></label>
                  <label className="check-row"><input name="permitted_reuse" type="checkbox" /> Reuse explicitly permitted</label>
                  <label className="check-row"><input name="activate" type="checkbox" /> Activate after review</label>
                  <button className="button button-primary" type="submit">Save source</button>
                </form>
              </article>
              <article className="workflow-panel">
                <h3>Manual source batch</h3>
                <form className="workflow-form" onSubmit={submitSourceBatch}>
                  <label>Reviewed source<select name="source_id" required defaultValue="">
                    <option value="" disabled>Select source</option>
                    {sources?.map((source) => <option value={source.id} key={source.id}>{source.name}</option>)}
                  </select></label>
                  <label>Tender records as JSON<textarea name="records" rows={8} required placeholder={'[{"title":"...","location":"...","region":"...","source_reference":"..."}]'} /></label>
                  <label>References explicitly withdrawn<textarea name="archived_references" rows={3} placeholder="One source reference per line" /></label>
                  <p className="field-note">Only enter records reviewed from the official source. This does not fetch source pages.</p>
                  <button className="button button-primary" type="submit">Import reviewed batch</button>
                </form>
              </article>
              <article className="workflow-panel">
                <h3>Public-document intake</h3>
                <form className="workflow-form" onSubmit={submitDocument}>
                  <label>Reviewed source<select name="source_id" required defaultValue="">
                    <option value="" disabled>Select source</option>
                    {sources?.map((source) => <option value={source.id} key={source.id}>{source.name}</option>)}
                  </select></label>
                  <label>Official document URL<input name="source_url" type="url" required /></label>
                  <label>Public PDF or text file<input name="document" type="file" accept="application/pdf,.pdf,text/plain,.txt" required /></label>
                  <p className="field-note">Maximum 10 MB. Text extraction is a draft; no notice is published until a person reviews the source.</p>
                  <button className="button button-primary" type="submit">Queue document</button>
                </form>
              </article>
              <article className="workflow-panel">
                <h3>Account verification</h3>
                <div className="account-list">
                  {accounts.filter((item) => item.role === "contractor").map((item) => (
                    <div className="account-row" key={item.id}>
                      <span>{item.email}<small>{item.email_verified_at ? `Verified ${new Date(item.email_verified_at).toLocaleDateString("en-CA")}` : "Verification pending"}</small></span>
                      {!item.email_verified_at && <button className="button button-outline" type="button" onClick={() => void verifyAccount(item.id)}>Verify</button>}
                    </div>
                  ))}
                </div>
                <button className="button button-outline" type="button" onClick={() => {
                  const token = accessToken();
                  if (token) void api<Account[]>("/accounts", token).then(setAccounts);
                }}>Refresh accounts</button>
              </article>
            </div>
            <div className="section-heading subsection-heading" id="document-queue"><div><div className="eyebrow">HUMAN REVIEW REQUIRED</div><h3>Document review queue</h3></div></div>
            {documents.length ? (
              <div className="document-list">
                {documents.map((document) => {
                  const draft = documentDrafts[document.id] ?? { title: "", location: "", region: "", closing_date: "", source_reference: "", status: "open" };
                  const setDraft = (key: keyof DocumentDraft, value: string) => setDocumentDrafts((current) => ({
                    ...current,
                    [document.id]: { ...draft, [key]: value },
                  }));
                  return (
                    <article className="document-card" key={document.id}>
                      <div className="document-heading"><div><strong>{document.file_name}</strong><span>SHA-256 {document.sha256}</span></div><a href={`${API_BASE}/documents/${document.id}/file`} onClick={async (event) => {
                        event.preventDefault();
                        const token = accessToken();
                        if (!token) return;
                        const response = await fetch(`${API_BASE}/documents/${document.id}/file`, { headers: { Authorization: `Bearer ${token}` } });
                        if (response.ok) window.open(URL.createObjectURL(await response.blob()), "_blank", "noopener,noreferrer");
                      }}>Open original</a></div>
                      <p className="field-note">Draft fields from {document.extractor_name} {document.extractor_version}; prompt {document.prompt_version}. Check each against the original.</p>
                      <div className="confidence-list">{Object.entries(document.field_confidence).map(([field, confidence]) => <span key={field}>{field}: {Math.round(confidence * 100)}%</span>)}</div>
                      <form className="workflow-form review-form" onSubmit={(event) => {
                        event.preventDefault();
                        void reviewDocument(event.currentTarget, document, "approve");
                      }}>
                        <label>Title<input value={draft.title} onChange={(event) => setDraft("title", event.target.value)} required /></label>
                        <label>Location<input value={draft.location} onChange={(event) => setDraft("location", event.target.value)} required /></label>
                        <label>Region<input value={draft.region} onChange={(event) => setDraft("region", event.target.value)} required /></label>
                        <label>Closing date<input type="date" value={draft.closing_date} onChange={(event) => setDraft("closing_date", event.target.value)} /></label>
                        <label>Source reference<input value={draft.source_reference} onChange={(event) => setDraft("source_reference", event.target.value)} /></label>
                        <label>Status<select value={draft.status} onChange={(event) => setDraft("status", event.target.value)}><option value="planned">Planned</option><option value="open">Open</option><option value="closed">Closed</option></select></label>
                        <label className="review-reason">Review note<input name="reason" minLength={3} required /></label>
                        <div className="review-actions">
                          <button className="button button-primary" type="submit">Approve and publish</button>
                          <button className="button button-outline" type="button" onClick={(event) => {
                            const form = event.currentTarget.closest(".document-card")?.querySelector<HTMLFormElement>("form");
                            if (form?.reportValidity()) void reviewDocument(form, document, "reject");
                          }}>Reject draft</button>
                        </div>
                      </form>
                    </article>
                  );
                })}
              </div>
            ) : <EmptyState title="No documents awaiting review">Approved records appear publicly only after a human checks the original notice.</EmptyState>}
            <div className="section-heading subsection-heading" id="outcome-management"><div><div className="eyebrow">INDEPENDENT PUBLIC RECORD</div><h3>Record verified outcome</h3></div></div>
            <article className="workflow-panel outcome-form-panel">
              <form className="workflow-form outcome-form" onSubmit={submitOutcome}>
                <label>Historical notice<select name="tender_id" required defaultValue=""><option value="" disabled>Select notice</option>{historical?.map((tender) => <option value={tender.id} key={tender.id}>{tender.title}</option>)}</select></label>
                <label>Reviewed source<select name="source_id" required defaultValue=""><option value="" disabled>Select source</option>{sources?.map((source) => <option value={source.id} key={source.id}>{source.name}</option>)}</select></label>
                <label>Public outcome<select name="outcome"><option value="awarded">Awarded</option><option value="cancelled">Cancelled</option><option value="no_award">No award</option></select></label>
                <label>Publication date<input name="published_at" type="date" /></label>
                <label>Official outcome URL<input name="source_url" type="url" required /></label>
                <label>Source reference<input name="source_reference" required /></label>
                <label className="wide-field">Verification method<textarea name="verification_method" minLength={10} maxLength={500} required /></label>
                <p className="field-note wide-field">Do not enter award amounts, bidders, or confidential pricing. Outcomes contain public status and verification provenance only.</p>
                <button className="button button-primary" type="submit">Save verified outcome</button>
              </form>
            </article>
          </section>
        )}

        <section className="section-block" id="history-intelligence">
          <div className="section-heading">
            <div><div className="eyebrow">KNOWN COVERAGE</div><h2>Verified historical outcomes</h2></div>
            <span className="registry-lock">No market-wide inference</span>
          </div>
          {historyCoverage && (
            <div className="coverage-strip">
              <div><strong>{historyCoverage.coverage_percent === null ? "—" : `${historyCoverage.coverage_percent}%`}</strong><span>outcome coverage</span></div>
              <div><strong>{historyCoverage.verified_outcomes}</strong><span>verified</span></div>
              <div><strong>{historyCoverage.missing_outcomes}</strong><span>missing</span></div>
              <p>{historyCoverage.methodology}</p>
            </div>
          )}
          {outcomes.length ? (
            <div className="outcome-list">{outcomes.map((outcome) => (
              <article className="outcome-row" key={outcome.id}>
                <div><strong>{outcome.tender_title}</strong><span>{outcome.outcome.replaceAll("_", " ")} · {outcome.published_at ?? "Publication date not recorded"}</span></div>
                <div><span>{outcome.source_name} · {outcome.source_reference}</span><a href={outcome.source_url} target="_blank" rel="noopener noreferrer">Verify source ↗</a></div>
              </article>
            ))}</div>
          ) : <EmptyState title="No independently verified outcomes">Outcome coverage is currently empty. No awards or pricing are inferred.</EmptyState>}
        </section>

        <footer className="page-footer">
          <span>NLTI · Newfoundland and Labrador Tender Intelligence</span>
          <span>Screening information only · Verify every notice at its source</span>
        </footer>
      </main>

      <dialog className="auth-dialog" ref={dialogRef} onClose={() => setAuthMode(null)} onCancel={() => setAuthMode(null)}>
        <form method="dialog" className="dialog-close-row"><button className="dialog-close" aria-label="Close sign-in window">×</button></form>
        <div className="dialog-heading">
          <span className="brand-mark">N</span>
          <div className="eyebrow">CONTRACTOR WORKSPACE</div>
          <h2>{authMode === "register" ? "Create your contractor account" : "Sign in to NLTI"}</h2>
          <p>Access your own company profile and explainable opportunity matches.</p>
        </div>
        <form className="auth-form" onSubmit={submitAuth}>
          {authMode === "register" && <label>Company name<input name="company_name" autoComplete="organization" minLength={2} required /></label>}
          <label>Email address<input name="email" type="email" autoComplete="email" required /></label>
          <label>Password<input name="password" type="password" autoComplete={authMode === "register" ? "new-password" : "current-password"} minLength={authMode === "register" ? 12 : 1} required /></label>
          {authError && <div className="form-error" role="alert">{authError}</div>}
          <button className="button button-primary button-wide" type="submit" disabled={authBusy}>
            {authBusy ? "Working…" : authMode === "register" ? "Create account" : "Sign in"}
          </button>
        </form>
        <p className="switch-auth">
          {authMode === "register" ? "Already registered?" : "New to NLTI?"}{" "}
          <button type="button" onClick={() => showAuth(authMode === "register" ? "login" : "register")}>
            {authMode === "register" ? "Sign in" : "Create an account"}
          </button>
        </p>
        <p className="privacy-note">Your account is separate from other contractors. Never share confidential bid pricing or strategy.</p>
      </dialog>
    </div>
  );
}
