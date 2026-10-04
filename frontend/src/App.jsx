import { useCallback, useEffect, useMemo, useState } from "react";
import { api, clearToken, getToken, setToken } from "./api.js";

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

  if (loading) return <div className="page muted">Loading…</div>;
  if (!user) return <Login onLogin={setUser} error={error} setError={setError} />;
  return <Desk user={user} onLogout={() => { clearToken(); setUser(null); }} />;
}

function Login({ onLogin, error, setError }) {
  const [email, setEmail] = useState("client-a@example.com");
  const [password, setPassword] = useState("client123");

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      const tok = await api.login(email, password);
      setToken(tok.access_token);
      onLogin(await api.me());
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="page">
      <div className="card login">
        <h1>Dataset Request Desk</h1>
        <p className="muted">Internal platform for robotics dataset fulfilment.</p>
        <form onSubmit={submit}>
          <label>
            Email
            <input value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
          </label>
          <label>
            Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          </label>
          {error && <p className="error">{error}</p>}
          <button type="submit">Sign in</button>
        </form>
        <p className="muted small">
          Seed accounts: client-a@example.com / client123 · ops1@example.com / ops123 · admin@example.com / admin123
        </p>
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
        <div>
          <strong>Dataset Request Desk</strong>
          <div className="muted small">
            {user.name} · {user.role}
            {user.organisation ? ` · ${user.organisation}` : ""}
          </div>
        </div>
        <button className="ghost" onClick={onLogout}>
          Sign out
        </button>
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
          <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </label>
        <button type="submit">Submit request</button>
      </form>
      <section className="card">
        <h2>Your requests</h2>
        {error && <p className="error">{error}</p>}
        <RequestTable
          rows={requests}
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
          onRow={(row) => setSelected(row)}
          selectedId={selected?.id}
        />
      </section>

      <section className="card">
        <h2>{selected ? `Request #${selected.id}` : "Select a request"}</h2>
        {selected && (
          <>
            <p>
              {selected.task_name} · {selected.assigned_count}/{selected.episodes_requested} assigned · {selected.status}
            </p>
            {nextOpsStatus && (
              <button onClick={() => changeStatus(selected.id, nextOpsStatus)}>Move to {nextOpsStatus}</button>
            )}
            <h3>Assigned episodes</h3>
            <ul className="plain">
              {selected.assignments.map((a) => (
                <li key={a.id}>
                  {a.episode.episode_id} · {a.episode.quality} · {a.episode.robot_id}
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
            placeholder="Filter task_name"
            value={filters.task_name}
            onChange={(e) => setFilters({ ...filters, task_name: e.target.value })}
          />
          <select value={filters.quality} onChange={(e) => setFilters({ ...filters, quality: e.target.value })}>
            <option value="">any quality</option>
            <option value="good">good</option>
            <option value="usable">usable</option>
            <option value="bad">bad</option>
          </select>
          <label className="inline">
            <input
              type="checkbox"
              checked={filters.unassigned_only}
              onChange={(e) => setFilters({ ...filters, unassigned_only: e.target.checked })}
            />
            unassigned only
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
            {episodes.map((ep) => (
              <tr key={ep.id}>
                <td>{ep.episode_id}</td>
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
      <h2>Users (admin)</h2>
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
              <td>{u.is_active ? "yes" : "no"}</td>
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

function RequestTable({ rows, actions, showClient, onRow, selectedId }) {
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
        {rows.map((row) => (
          <tr
            key={row.id}
            className={selectedId === row.id ? "selected" : onRow ? "clickable" : ""}
            onClick={() => onRow && onRow(row)}
          >
            <td>{row.id}</td>
            {showClient && <td>{row.client_name}</td>}
            <td>{row.task_name}</td>
            <td>
              {row.assigned_count}/{row.episodes_requested}
            </td>
            <td>{row.deadline}</td>
            <td>
              <span className={`status ${row.status}`}>{row.status}</span>
            </td>
            {actions && <td onClick={(e) => e.stopPropagation()}>{actions(row)}</td>}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
