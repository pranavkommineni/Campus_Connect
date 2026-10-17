import { FormEvent, useCallback, useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, ApiError, download, Ev, fmt, patch, post } from "../api";
import { Badge, Confirm, Empty, Field, Skeleton, Stat, useToast } from "../ui";
import { CheckIn, EventForm, ImportWizard } from "./Manage";
import EventsTable from "./EventsTable";

const COLORS = ["#818cf8", "#38bdf8", "#34d399", "#fbbf24", "#f472b6", "#a78bfa"];
const tip = { contentStyle: { background: "#0b1030", border: "1px solid rgba(255,255,255,.15)", borderRadius: 12 } };

function Overview() {
  const [a, setA] = useState<any>(null);
  useEffect(() => { api("/api/admin/analytics").then(setA); }, []);
  if (!a) return <Skeleton className="h-64" />;
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><Stat label="Students" value={a.students} /><Stat label="Clubs" value={`${a.clubs}${a.pending_clubs ? ` (${a.pending_clubs} pending)` : ""}`} tone="sky" />
        <Stat label="Events" value={`${a.events}${a.pending_events ? ` (${a.pending_events} pending)` : ""}`} tone="amber" /><Stat label="Avg rating" value={a.avg_rating ?? "–"} tone="emerald" />
        <Stat label="Registrations" value={a.registrations} /><Stat label="Attended" value={a.attended} tone="emerald" /></div>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card"><h3 className="mb-3 font-bold">Registrations by category</h3><div className="h-64"><ResponsiveContainer><BarChart data={a.registrations_by_category}><CartesianGrid stroke="rgba(255,255,255,.08)" /><XAxis dataKey="category" stroke="#94a3b8" fontSize={12} /><YAxis allowDecimals={false} stroke="#94a3b8" fontSize={12} /><Tooltip {...tip} /><Bar dataKey="count" fill="#818cf8" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></div></div>
        <div className="card"><h3 className="mb-3 font-bold">Events by status</h3><div className="h-64"><ResponsiveContainer><PieChart><Pie data={a.events_by_status} dataKey="count" nameKey="status" innerRadius={50} outerRadius={85} label={(d) => d.status}>{a.events_by_status.map((_: any, i: number) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}</Pie><Tooltip {...tip} /></PieChart></ResponsiveContainer></div></div>
      </div>
      <div className="card"><h3 className="mb-2 font-bold">Top events</h3>{a.top_events.length ? a.top_events.map((t: any) => <p key={t.title} className="flex justify-between border-b border-white/5 py-1.5 text-sm"><span>{t.title}</span><span className="text-indigo-300">{t.count}</span></p>) : <p className="text-sm text-slate-400">No registrations yet.</p>}</div>
      <div className="card flex flex-wrap gap-2"><span className="mr-2 self-center text-sm font-bold">Reports</span>
        {["events", "registrations", "attendance"].map((r) => <button key={r} className="btn-ghost capitalize" onClick={() => download(`/api/admin/reports/${r}.csv`, `${r}_report.csv`)}>⬇ {r}</button>)}</div>
    </div>
  );
}

function Events() {
  const [events, setEvents] = useState<Ev[] | null>(null); const [filter, setFilter] = useState(""); const [creating, setCreating] = useState(false);
  const load = useCallback(() => { api<Ev[]>(`/api/events/manage${filter ? `?status=${filter}` : ""}`).then(setEvents); }, [filter]);
  useEffect(load, [load]);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2"><select className="input max-w-xs" aria-label="Status filter" value={filter} onChange={(e) => setFilter(e.target.value)}><option value="">All statuses</option>{["pending_approval", "published", "draft", "rejected", "completed", "cancelled"].map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}</select>
        <button className="btn-primary ml-auto" onClick={() => setCreating(true)}>+ New event</button></div>
      <EventsTable events={events} reload={load} />
      {creating && <EventForm onClose={() => setCreating(false)} onSaved={load} />}
    </div>
  );
}

function Users() {
  const toast = useToast(); const [users, setUsers] = useState<any[] | null>(null); const [target, setTarget] = useState<any>(null);
  const load = useCallback(() => { api("/api/admin/users").then(setUsers); }, []);
  useEffect(load, [load]);
  const run = async (fn: () => Promise<unknown>, ok: string) => { try { await fn(); toast(ok); load(); } catch (x) { toast((x as ApiError).message, "err"); } };
  if (!users) return <Skeleton className="h-48" />;
  return (
    <div className="card overflow-x-auto p-0"><table className="w-full min-w-[680px]"><thead className="border-b border-white/10"><tr><th className="th">User</th><th className="th">Role</th><th className="th">Club status</th><th className="th">Account</th><th className="th text-right">Actions</th></tr></thead>
      <tbody className="divide-y divide-white/5">{users.map((u) => (
        <tr key={u.id}><td className="td"><span className="font-semibold text-white">{u.full_name}</span><br /><span className="text-xs text-slate-400">{u.email}</span></td><td className="td capitalize">{u.role}</td>
          <td className="td">{u.club ? <><Badge s={u.club.status} /> <span className="text-xs text-slate-400">{u.club.name}</span></> : "–"}</td><td className="td"><Badge s={u.is_active ? "approved" : "suspended"} /></td>
          <td className="td"><div className="flex flex-wrap justify-end gap-1.5">
            {u.club && u.club.status !== "approved" && <button className="btn-primary px-3 py-1" onClick={() => run(() => patch(`/api/admin/clubs/${u.club.id}`, { status: "approved" }), "Club approved")}>Approve club</button>}
            {u.club && u.club.status === "approved" && <button className="btn-ghost px-3 py-1" onClick={() => run(() => patch(`/api/admin/clubs/${u.club.id}`, { status: "suspended" }), "Club suspended")}>Suspend club</button>}
            {u.role !== "admin" && <button className="btn-ghost px-3 py-1" onClick={() => (u.is_active ? setTarget(u) : run(() => patch(`/api/admin/users/${u.id}`, { is_active: true }), "Account reactivated"))}>{u.is_active ? "Disable login" : "Enable login"}</button>}
          </div></td></tr>))}</tbody></table>
      {target && <Confirm title="Disable this account?" text={`${target.email} will no longer be able to sign in.`} onClose={() => setTarget(null)} onYes={() => run(() => patch(`/api/admin/users/${target.id}`, { is_active: false }), "Account disabled")} />}
    </div>
  );
}

function Campus() {
  const toast = useToast(); const [meta, setMeta] = useState<any>(null); const [v, setV] = useState({ name: "", location: "", capacity: 100 }); const [cat, setCat] = useState("");
  const load = () => api("/api/meta").then(setMeta); useEffect(() => { load(); }, []);
  const add = async (e: FormEvent, path: string, body: any, reset: () => void) => { e.preventDefault(); try { await post(path, body); toast("Saved"); reset(); load(); } catch (x) { toast((x as ApiError).message, "err"); } };
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <form className="card space-y-3" onSubmit={(e) => add(e, "/api/admin/venues", v, () => setV({ name: "", location: "", capacity: 100 }))}><h3 className="font-bold">Venues</h3>
        <ul className="mb-2 space-y-1 text-sm">{meta?.venues.map((x: any) => <li key={x.id} className="flex justify-between border-b border-white/5 py-1"><span>{x.name}</span><span className="text-slate-400">cap. {x.capacity}</span></li>)}</ul>
        <Field label="Name"><input className="input" required minLength={2} value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} /></Field>
        <Field label="Location"><input className="input" value={v.location} onChange={(e) => setV({ ...v, location: e.target.value })} /></Field>
        <Field label="Capacity"><input className="input" type="number" min={1} required value={v.capacity} onChange={(e) => setV({ ...v, capacity: +e.target.value })} /></Field><button className="btn-primary">Add venue</button></form>
      <form className="card space-y-3" onSubmit={(e) => add(e, "/api/admin/categories", { name: cat }, () => setCat(""))}><h3 className="font-bold">Categories</h3>
        <div className="mb-2 flex flex-wrap gap-2">{meta?.categories.map((c: any) => <span key={c.id} className="rounded-full bg-indigo-500/15 px-3 py-1 text-xs text-indigo-200">{c.name}</span>)}</div>
        <Field label="New category"><input className="input" required minLength={2} value={cat} onChange={(e) => setCat(e.target.value)} /></Field><button className="btn-primary">Add category</button></form>
    </div>
  );
}

function Audit() {
  const [rows, setRows] = useState<any[] | null>(null); useEffect(() => { api("/api/admin/audit").then(setRows); }, []);
  if (!rows) return <Skeleton className="h-48" />; if (!rows.length) return <Empty title="No activity yet" />;
  return <div className="card overflow-x-auto p-0"><table className="w-full min-w-[600px]"><thead className="border-b border-white/10"><tr><th className="th">When</th><th className="th">Actor</th><th className="th">Action</th><th className="th">Detail</th></tr></thead>
    <tbody className="divide-y divide-white/5">{rows.map((r) => <tr key={r.id}><td className="td text-slate-400">{fmt(r.created_at)}</td><td className="td">#{r.actor_id ?? "–"}</td><td className="td font-mono text-xs text-indigo-300">{r.action}</td><td className="td text-slate-300">{r.detail}</td></tr>)}</tbody></table></div>;
}

function ImportJobs() {
  const [jobs, setJobs] = useState<any[]>([]); const [n, setN] = useState(0);
  useEffect(() => { api("/api/imports/jobs").then(setJobs); }, [n]);
  return (
    <div className="space-y-4"><ImportWizard onDone={() => setN(n + 1)} />
      <div className="card"><h3 className="mb-2 font-bold">Import history</h3>{jobs.length === 0 ? <p className="text-sm text-slate-400">No imports yet.</p> : jobs.map((j) => (
        <div key={j.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 py-2 text-sm"><span>{j.filename} · {fmt(j.created_at)}</span><span><span className="text-emerald-300">{j.success} ok</span> · <span className="text-rose-300">{j.failed} failed</span>
          {j.failed > 0 && <button className="btn-ghost ml-3 px-3 py-1" onClick={() => download(`/api/imports/jobs/${j.id}/errors.csv`, `import_${j.id}_errors.csv`)}>Error report</button>}</span></div>))}</div></div>
  );
}

const TABS = [["overview", "Overview"], ["events", "Events"], ["users", "Users & clubs"], ["campus", "Venues & categories"], ["import", "CSV import"], ["checkin", "Check-in"], ["audit", "Audit log"]] as const;
export default function Admin() {
  const [tab, setTab] = useState<(typeof TABS)[number][0]>("overview");
  return (
    <div className="space-y-6"><div><h1 className="text-3xl font-bold">Admin console</h1><p className="text-slate-400">Platform-wide control and analytics.</p></div>
      <div className="flex flex-wrap gap-2" role="tablist">{TABS.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "btn-primary" : "btn-ghost"} onClick={() => setTab(k)}>{l}</button>)}</div>
      {tab === "overview" && <Overview />}{tab === "events" && <Events />}{tab === "users" && <Users />}{tab === "campus" && <Campus />}{tab === "import" && <ImportJobs />}{tab === "checkin" && <CheckIn />}{tab === "audit" && <Audit />}
    </div>
  );
}
