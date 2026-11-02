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
type Source = { id: number; name: string; owner: string; official_url: string; access_method: string };
type Account = { id: number; email: string; role: string; contractor_id: number | null };
type Summary = { upcoming_tenders: number; historical_tenders: number; reviewed_sources: number };

async function api<T>(path: string, token?: string | null, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
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
  const dialogRef = useRef<HTMLDialogElement>(null);

  const loadSummary = useCallback(async () => {
    try {
      setSummary(await api<Summary>("/summary"));
    } catch (error) {
      setNotice(`Dashboard totals are unavailable: ${error instanceof Error ? error.message : "API error"}`);
      setIsError(true);
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
        </section>

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
                  <p>{source.owner} · {source.access_method} access</p>
                  <a href={source.official_url} target="_blank" rel="noopener noreferrer">Open official source ↗</a>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState title="No procurement sources have been approved">
              The registry is intentionally empty until a source&apos;s owner, access method, terms, and reuse permission are recorded and reviewed.
            </EmptyState>
          )}
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
