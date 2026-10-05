import { useCallback, useEffect, useMemo, useState } from "react";
import { api, clearToken, getToken, setToken } from "./api.js";

const label = (s) => (s || "").replace(/_/g, " ");

export default function App() {
  const [user, setUser] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(Boolean(getToken()));

  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    api
      .me()
      .then(setUser)
      .catch(() => {
        clearToken();
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="page center muted">Loading…</div>;
  if (!user) return <Login onLogin={setUser} error={error} setError={setError} />;
  return <Desk user={user} onLogout={() => { clearToken(); setUser(null); }} />;
}

function Logo() {
  return (
    <span className="mark" aria-hidden="true">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 19V9l8-5 8 5v10" />
        <path d="M9 19v-5h6v5" />
      </svg>
    </span>
  );
}

function Login({ onLogin, error, setError }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const tok = await api.login(email, password);
      setToken(tok.access_token);
      onLogin(await api.me());
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page center">
      <div className="auth">
        <aside className="auth-art">
          <div className="brand">
            <Logo />
            <strong>Dataset Request Desk</strong>
          </div>
          <div>
            <h2>Robot data, delivered on time.</h2>
            <p>Request episodes, track fulfilment, and review deliveries in one place.</p>
            <svg viewBox="0 0 360 120" fill="none" aria-hidden="true">
              <path className="trace" d="M10 100 C60 100 60 30 120 30 S190 90 240 60 S320 20 350 30" stroke="#2fc4b2" strokeWidth="3" strokeLinecap="round" />
              {[[10, 100], [120, 30], [240, 60], [350, 30]].map(([x, y]) => (
                <circle key={x} cx={x} cy={y} r="5" fill="#0d1b2a" stroke="#2fc4b2" strokeWidth="2.5" />
              ))}
            </svg>
          </div>
        </aside>

        <div className="auth-form">
          <h1>Sign in</h1>
          <p className="muted">Use the account your team set up for you.</p>
          <form className="login-form" onSubmit={submit}>
            <label>
              Email
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                autoComplete="username"
                required
              />
            </label>
            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                autoComplete="current-password"
                required
              />
            </label>
            {error && <p className="error" role="alert">{error}</p>}
            <button type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
          </form>
        </div>
      </div>
    </div>
  );
}

function Desk({ user, onLogout }) {
  const isClient = user.role === "client";
  const isOps = user.role === "operator" || user.role === "admin";
  return (
    <div className="page">
      <header className="top">
        <div className="brand">
          <Logo />
          <strong>Dataset Request Desk</strong>
        </div>
        <div className="who">
          <div className="avatar" aria-hidden="true">{(user.name || "?").charAt(0).toUpperCase()}</div>
          <div>
            <div className="name">{user.name}</div>
            <div className="meta">
              {user.role}
              {user.organisation ? ` at ${user.organisation}` : ""}
            </div>
          </div>
          <button className="ghost" onClick={onLogout}>Sign out</button>
        </div>
      </header>
      {isClient && <ClientHome />}
      {isOps && <OperatorHome isAdmin={user.role === "admin"} />}
    </div>
  );
}

function ClientHome() {
  const [requests, setRequests] = useState([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    task_name: "pick cup",
    episodes_requested: 5,
    deadline: "2026-12-01",
    notes: "",
  });

  const load = useCallback(() => {
    api.requests().then(setRequests).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function create(e) {
    e.preventDefault();
    setError("");
    try {
      await api.createRequest({
        ...form,
        episodes_requested: Number(form.episodes_requested),
      });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function act(id, status) {
    setError("");
    try {
      await api.transition(id, status);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="grid">
      <form className="card" onSubmit={create}>
        <h2>New dataset request</h2>
        <p className="muted small">Tell us the task and how many episodes you need.</p>
        <label>
          Task
          <input value={form.task_name} onChange={(e) => setForm({ ...form, task_name: e.target.value })} />
        </label>
        <label>
          Episodes requested
          <input
            type="number"
            min="1"
            value={form.episodes_requested}
            onChange={(e) => setForm({ ...form, episodes_requested: e.target.value })}
          />
        </label>
        <label>
          Deadline
          <input type="date" value={form.deadline} onChange={(e) => setForm({ ...form, deadline: e.target.value })} />
        </label>
        <label>
          Notes
          <textarea
            placeholder="Anything the operators should know"
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
          />
        </label>
        <button type="submit">Submit request</button>
      </form>
      <section className="card">
        <h2>Your requests</h2>
        {error && <p className="error">{error}</p>}
        <RequestTable
          rows={requests}
          emptyText="No requests yet. Submit your first one using the form."
          actions={(row) =>
            row.status === "delivered" ? (
              <>
                <button onClick={() => act(row.id, "accepted")}>Accept</button>
                <button className="danger" onClick={() => act(row.id, "rejected")}>
                  Reject
                </button>
              </>
            ) : (
              <span className="muted small">Waiting on operations</span>
            )
          }
        />
      </section>
    </div>
  );
}

function OperatorHome({ isAdmin }) {
  const [requests, setRequests] = useState([]);
  const [selected, setSelected] = useState(null);
  const [episodes, setEpisodes] = useState([]);
  const [filters, setFilters] = useState({ task_name: "", quality: "", unassigned_only: true });
  const [error, setError] = useState("");
  const [live, setLive] = useState("connecting");
  const [importMsg, setImportMsg] = useState("");

  const loadRequests = useCallback(() => {
    api.requests().then(setRequests).catch((e) => setError(e.message));
  }, []);

  const loadEpisodes = useCallback(() => {
    const params = { unassigned_only: filters.unassigned_only ? "true" : "false", limit: "200" };
    if (filters.task_name) params.task_name = filters.task_name;
    if (filters.quality) params.quality = filters.quality;
    api.episodes(params).then(setEpisodes).catch((e) => setError(e.message));
  }, [filters]);

  useEffect(() => {
    loadRequests();
  }, [loadRequests]);
  useEffect(() => {
    loadEpisodes();
  }, [loadEpisodes]);

  useEffect(() => {
    let cancelled = false;
    const token = getToken();
    async function listen() {
      try {
        const res = await fetch("/api/events", { headers: { Authorization: `Bearer ${token}` } });
        if (!res.ok || !res.body) throw new Error("sse failed");
        setLive("live");
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        while (!cancelled) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          if (buf.includes("\n\n")) {
            loadRequests();
            loadEpisodes();
            buf = buf.slice(buf.lastIndexOf("\n\n") + 2);
          }
        }
      } catch {
        if (!cancelled) setLive("offline");
      }
    }
    listen();
    return () => {
      cancelled = true;
    };
  }, [loadRequests, loadEpisodes]);

  async function changeStatus(id, status) {
    setError("");
    try {
      const row = await api.transition(id, status);
      setSelected(row);
      loadRequests();
    } catch (err) {
      setError(err.message);
    }
  }

  async function assign(episodeId) {
    if (!selected) return;
    setError("");
    try {
      const row = await api.assign(selected.id, [episodeId]);
      setSelected(row);
      loadRequests();
      loadEpisodes();
    } catch (err) {
      setError(err.message);
    }
  }

  async function unassign(episodeId) {
    if (!selected) return;
    setError("");
    try {
      const row = await api.unassign(selected.id, [episodeId]);
      setSelected(row);
      loadRequests();
      loadEpisodes();
    } catch (err) {
      setError(err.message);
    }
  }

  async function onImport(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError("");
    try {
      const result = await api.importCsv(file);
      setImportMsg(`Imported ${result.imported}, skipped ${result.skipped}`);
      loadEpisodes();
    } catch (err) {
      setError(err.message);
    }
  }

  const nextOpsStatus = useMemo(() => {
    if (!selected) return null;
    if (selected.status === "submitted" || selected.status === "rejected") return "in_progress";
    if (selected.status === "in_progress") return "delivered";
    return null;
  }, [selected]);

  return (
    <div className="grid ops">
      <section className="card">
        <div className="row">
          <h2>All requests</h2>
          <span className={`pill ${live}`}>{live}</span>
        </div>
        {error && <p className="error">{error}</p>}
        <RequestTable
          rows={requests}
          showClient
          emptyText="No requests have been submitted yet."
          onRow={(row) => setSelected(row)}
          selectedId={selected?.id}
        />
      </section>

      <section className="card">
        <h2>{selected ? `Request #${selected.id}` : "Request details"}</h2>
        {!selected && <p className="empty">Select a request to assign episodes and update its status.</p>}
        {selected && (
          <>
            <div className="facts">
              <span className="status">{selected.task_name}</span>
              <span className="status">{selected.assigned_count}/{selected.episodes_requested} assigned</span>
              <span className={`status ${selected.status}`}>{label(selected.status)}</span>
            </div>
            {nextOpsStatus && (
              <button onClick={() => changeStatus(selected.id, nextOpsStatus)}>Move to {label(nextOpsStatus)}</button>
            )}
            <h3>Assigned episodes</h3>
            {selected.assignments.length === 0 && <p className="muted small">No episodes assigned yet.</p>}
            <ul className="plain">
              {selected.assignments.map((a) => (
                <li key={a.id}>
                  <span>
                    <span className="mono">{a.episode.episode_id}</span>{" "}
                    <span className="muted small">{a.episode.quality} · {a.episode.robot_id}</span>
                  </span>
                  <button className="ghost" onClick={() => unassign(a.episode.episode_id)}>
                    Unassign
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      <section className="card span-2">
        <div className="row">
          <h2>Episode library</h2>
          <label className="file">
            Import CSV
            <input type="file" accept=".csv" onChange={onImport} />
          </label>
        </div>
        {importMsg && <p className="muted">{importMsg}</p>}
        <div className="filters">
          <input
            placeholder="Filter by task name"
            value={filters.task_name}
            onChange={(e) => setFilters({ ...filters, task_name: e.target.value })}
          />
          <select value={filters.quality} onChange={(e) => setFilters({ ...filters, quality: e.target.value })}>
            <option value="">Any quality</option>
            <option value="good">Good</option>
            <option value="usable">Usable</option>
            <option value="bad">Bad</option>
          </select>
          <label className="inline">
            <input
              type="checkbox"
              checked={filters.unassigned_only}
              onChange={(e) => setFilters({ ...filters, unassigned_only: e.target.checked })}
            />
            &nbsp;Unassigned only
          </label>
        </div>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Task</th>
              <th>Robot</th>
              <th>Quality</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {episodes.length === 0 && (
              <tr>
                <td colSpan="5" className="empty">No episodes match these filters.</td>
              </tr>
            )}
            {episodes.map((ep) => (
              <tr key={ep.id}>
                <td className="id">{ep.episode_id}</td>
                <td>{ep.task_name}</td>
                <td>{ep.robot_id}</td>
                <td>{ep.quality}</td>
                <td>
                  <button disabled={!selected || ep.assigned_request_id} onClick={() => assign(ep.episode_id)}>
                    Assign
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      {isAdmin && <AdminUsers />}
    </div>
  );
}

function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api.users().then(setUsers).catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  async function toggle(user) {
    try {
      await api.updateUser(user.id, { is_active: !user.is_active });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="card span-2">
      <h2>Users</h2>
      {error && <p className="error">{error}</p>}
      <table>
        <thead>
          <tr>
            <th>Email</th>
            <th>Role</th>
            <th>Active</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>{u.email}</td>
              <td>{u.role}</td>
              <td>
                <span className={`status ${u.is_active ? "accepted" : "rejected"}`}>
                  {u.is_active ? "Active" : "Inactive"}
                </span>
              </td>
              <td>
                <button className="ghost" onClick={() => toggle(u)}>
                  {u.is_active ? "Deactivate" : "Reactivate"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function RequestTable({ rows, actions, showClient, onRow, selectedId, emptyText }) {
  return (
    <table>
      <thead>
        <tr>
          <th>#</th>
          {showClient && <th>Client</th>}
          <th>Task</th>
          <th>Fill</th>
          <th>Deadline</th>
          <th>Status</th>
          {actions && <th></th>}
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 && (
          <tr>
            <td colSpan={5 + (showClient ? 1 : 0) + (actions ? 1 : 0)} className="empty">
              {emptyText || "Nothing here yet."}
            </td>
          </tr>
        )}
        {rows.map((row) => {
          const pct = row.episodes_requested
            ? Math.min(100, Math.round((row.assigned_count / row.episodes_requested) * 100))
            : 0;
          return (
            <tr
              key={row.id}
              className={selectedId === row.id ? "selected" : onRow ? "clickable" : ""}
              onClick={() => onRow && onRow(row)}
            >
              <td className="id">{row.id}</td>
              {showClient && <td>{row.client_name}</td>}
              <td>{row.task_name}</td>
              <td>
                <span className="fill">
                  <span className="bar"><i style={{ width: `${pct}%` }} /></span>
                  {row.assigned_count}/{row.episodes_requested}
                </span>
              </td>
              <td>{row.deadline}</td>
              <td>
                <span className={`status ${row.status}`}>{label(row.status)}</span>
              </td>
              {actions && <td onClick={(e) => e.stopPropagation()}>{actions(row)}</td>}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}