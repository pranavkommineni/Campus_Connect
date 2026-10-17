// Shared by the club dashboard and the admin console: manual event form, CSV import wizard, check-in.
import { FormEvent, useEffect, useRef, useState } from "react";
import { api, ApiError, download, Ev, fromLocalInput, fmt, Meta, post, put, toLocalInput } from "../api";
import { useAuth } from "../auth";
import { Badge, ErrorList, Field, Modal, useToast } from "../ui";

export function EventForm({ ev, onClose, onSaved }: { ev?: Ev; onClose: () => void; onSaved: () => void }) {
  const { user } = useAuth(); const toast = useToast();
  const [meta, setMeta] = useState<Meta | null>(null); const [errs, setErrs] = useState<string[]>([]); const [busy, setBusy] = useState(false); const [poster, setPoster] = useState<File | null>(null);
  const [f, setF] = useState({ title: ev?.title ?? "", description: ev?.description ?? "", category_id: ev?.category_id ?? 0, venue_id: ev?.venue_id ?? 0, club_id: ev?.club_id ?? 0,
    start_at: toLocalInput(ev?.start_at), end_at: toLocalInput(ev?.end_at), registration_deadline: toLocalInput(ev?.registration_deadline), capacity: ev?.capacity ?? 50,
    eligibility: ev?.eligibility ?? "Open to all students", department: ev?.department ?? "", academic_year: ev?.academic_year ?? "", contact_info: ev?.contact_info ?? "" });
  useEffect(() => { api<Meta>("/api/meta").then((m) => { setMeta(m); setF((s) => ({ ...s, category_id: s.category_id || m.categories[0]?.id, venue_id: s.venue_id || m.venues[0]?.id, club_id: s.club_id || m.clubs[0]?.id })); }); }, []);
  const set = (k: string, v: any) => setF({ ...f, [k]: v });
  const venue = meta?.venues.find((v) => v.id === Number(f.venue_id));
  const submit = async (e: FormEvent, publish: boolean) => {
    e.preventDefault(); setErrs([]);
    const local: string[] = [];
    if (new Date(f.end_at) <= new Date(f.start_at)) local.push("End time must be after start time");
    if (new Date(f.registration_deadline) > new Date(f.start_at)) local.push("Registration deadline must be before the event starts");
    if (venue && f.capacity > venue.capacity) local.push(`Capacity exceeds venue limit (${venue.capacity})`);
    if (local.length) return setErrs(local);
    setBusy(true);
    try {
      const body = { ...f, category_id: +f.category_id, venue_id: +f.venue_id, capacity: +f.capacity, start_at: fromLocalInput(f.start_at), end_at: fromLocalInput(f.end_at),
        registration_deadline: fromLocalInput(f.registration_deadline), club_id: user?.role === "admin" ? +f.club_id : undefined, submit: publish };
      const saved: Ev = ev ? await put(`/api/events/${ev.id}`, body) : await post("/api/events", body);
      if (poster) { const fd = new FormData(); fd.append("file", poster); await api(`/api/events/${saved.id}/poster`, { method: "POST", body: fd }); }
      toast(publish ? (user?.role === "admin" ? "Event published" : "Submitted for approval") : "Draft saved"); onSaved(); onClose();
    } catch (x) { const a = x as ApiError; setErrs(a.errors.length ? a.errors : [a.message]); } finally { setBusy(false); }
  };
  return (
    <Modal title={ev ? "Edit event" : "Create event"} onClose={onClose} wide>
      <form className="grid gap-3 sm:grid-cols-2" onSubmit={(e) => submit(e, true)}>
        <div className="sm:col-span-2"><ErrorList errors={errs} /></div>
        <div className="sm:col-span-2"><Field label="Title"><input className="input" required maxLength={200} value={f.title} onChange={(e) => set("title", e.target.value)} /></Field></div>
        <div className="sm:col-span-2"><Field label="Description"><textarea className="input" rows={3} value={f.description} onChange={(e) => set("description", e.target.value)} /></Field></div>
        {user?.role === "admin" && <Field label="Organizing club"><select className="input" value={f.club_id} onChange={(e) => set("club_id", e.target.value)}>{meta?.clubs.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>}
        <Field label="Category"><select className="input" value={f.category_id} onChange={(e) => set("category_id", e.target.value)}>{meta?.categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
        <Field label="Venue" hint={venue ? `Venue capacity: ${venue.capacity}` : ""}><select className="input" value={f.venue_id} onChange={(e) => set("venue_id", e.target.value)}>{meta?.venues.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}</select></Field>
        <Field label="Starts"><input className="input" type="datetime-local" required value={f.start_at} onChange={(e) => set("start_at", e.target.value)} /></Field>
        <Field label="Ends"><input className="input" type="datetime-local" required value={f.end_at} onChange={(e) => set("end_at", e.target.value)} /></Field>
        <Field label="Registration deadline"><input className="input" type="datetime-local" required value={f.registration_deadline} onChange={(e) => set("registration_deadline", e.target.value)} /></Field>
        <Field label="Capacity"><input className="input" type="number" min={1} required value={f.capacity} onChange={(e) => set("capacity", e.target.value)} /></Field>
        <Field label="Eligibility"><input className="input" value={f.eligibility} onChange={(e) => set("eligibility", e.target.value)} /></Field>
        <Field label="Department"><input className="input" value={f.department} onChange={(e) => set("department", e.target.value)} /></Field>
        <Field label="Academic year"><input className="input" value={f.academic_year} onChange={(e) => set("academic_year", e.target.value)} /></Field>
        <Field label="Contact"><input className="input" value={f.contact_info} onChange={(e) => set("contact_info", e.target.value)} /></Field>
        <div className="sm:col-span-2"><Field label="Poster (PNG/JPEG/WebP, max 5 MB)"><input className="input" type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setPoster(e.target.files?.[0] ?? null)} /></Field></div>
        <div className="flex justify-end gap-2 sm:col-span-2">
          <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
          <button type="button" className="btn-ghost" disabled={busy} onClick={(e) => submit(e as any, false)}>Save as draft</button>
          <button className="btn-primary" disabled={busy}>{busy ? "Saving…" : user?.role === "admin" ? "Publish" : "Submit for approval"}</button>
        </div>
      </form>
    </Modal>
  );
}

interface Row { row: number; ok: boolean; title: string; errors?: string[]; status?: string }
export function ImportWizard({ onDone }: { onDone: () => void }) {
  const toast = useToast(); const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null); const [prev, setPrev] = useState<{ total: number; valid: number; invalid: number; rows: Row[] } | null>(null);
  const [res, setRes] = useState<{ job_id: number; success: number; failed: number; rows: Row[] } | null>(null); const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  const send = async (path: string) => { const fd = new FormData(); fd.append("file", file!); return api(path, { method: "POST", body: fd }); };
  const step = res ? 3 : prev ? 2 : 1;
  const doPreview = async () => { setBusy(true); setErr(""); try { setPrev(await send("/api/imports/preview")); } catch (x) { setErr((x as ApiError).message); } finally { setBusy(false); } };
  const doCommit = async () => { setBusy(true); try { const r = await send("/api/imports/commit"); setRes(r); onDone(); toast(`${r.success} imported, ${r.failed} failed`, r.failed ? "err" : "ok"); } catch (x) { toast((x as ApiError).message, "err"); } finally { setBusy(false); } };
  const reset = () => { setFile(null); setPrev(null); setRes(null); setErr(""); if (input.current) input.current.value = ""; };
  const table = (rows: Row[]) => (
    <div className="max-h-72 overflow-auto rounded-xl border border-white/10"><table className="w-full"><thead className="bg-white/5"><tr><th className="th">Row</th><th className="th">Title</th><th className="th">Result</th></tr></thead>
      <tbody className="divide-y divide-white/5">{rows.map((r) => <tr key={r.row}><td className="td">{r.row}</td><td className="td">{r.title}</td><td className="td">{r.ok ? <span className="text-emerald-300">✓ {r.status}</span> : <span className="text-rose-300">{r.errors?.join("; ")}</span>}</td></tr>)}</tbody></table></div>);
  return (
    <div className="card space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="text-lg font-bold">CSV import</h3>
        <div className="flex items-center gap-1 text-xs text-slate-400">{["Upload", "Preview", "Result"].map((s, i) => <span key={s} className={`rounded-full px-2 py-0.5 ${step === i + 1 ? "bg-indigo-500 text-white" : "bg-white/5"}`}>{i + 1}. {s}</span>)}</div></div>
      {step === 1 && <>
        <p className="text-sm text-slate-400">Required columns: <code className="text-indigo-300">title, category, venue, start_at, end_at, capacity, registration_deadline</code>. Optional: description, eligibility, department, academic_year, contact_info, club (admins only), submit (yes/no). Dates are <code>YYYY-MM-DD HH:MM</code> in UTC. UTF-8 only, max 1000 rows.</p>
        <div className="flex flex-wrap gap-2"><button className="btn-ghost" onClick={() => download("/api/imports/template.csv", "campusconnect_events_template.csv")}>⬇ Download template</button>
          <input ref={input} type="file" accept=".csv,text/csv" aria-label="CSV file" className="input max-w-xs" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <button className="btn-primary" disabled={!file || busy} onClick={doPreview}>{busy ? "Validating…" : "Validate & preview"}</button></div>
        {err && <ErrorList errors={[err]} />}</>}
      {step === 2 && prev && <>
        <p className="text-sm"><span className="text-emerald-300">{prev.valid} valid</span> · <span className="text-rose-300">{prev.invalid} with errors</span> of {prev.total} rows. Nothing is saved yet. Invalid rows will be reported, never silently skipped.</p>
        {table(prev.rows)}
        <div className="flex gap-2"><button className="btn-ghost" onClick={reset}>Start over</button><button className="btn-primary" disabled={busy || prev.valid === 0} onClick={doCommit}>{busy ? "Importing…" : `Import ${prev.valid} valid row(s)`}</button></div></>}
      {step === 3 && res && <>
        <p className="text-sm"><span className="text-emerald-300">{res.success} imported</span> · <span className="text-rose-300">{res.failed} failed</span></p>
        {table(res.rows)}
        <div className="flex gap-2"><button className="btn-ghost" onClick={reset}>Import another file</button>
          {res.failed > 0 && <button className="btn-primary" onClick={() => download(`/api/imports/jobs/${res.job_id}/errors.csv`, `import_${res.job_id}_errors.csv`)}>⬇ Error report (CSV)</button>}</div></>}
    </div>
  );
}

export function CheckIn() {
  const toast = useToast(); const [code, setCode] = useState(""); const [last, setLast] = useState<string>("");
  const go = async (e: FormEvent) => { e.preventDefault();
    try { const r = await post("/api/checkin", { ticket_code: code.trim() }); setLast(`✓ ${r.student} checked in to ${r.event}`); toast("Checked in"); }
    catch (x) { setLast(`✗ ${(x as ApiError).message}`); toast((x as ApiError).message, "err"); } setCode(""); };
  return (
    <form onSubmit={go} className="card max-w-xl space-y-3"><h3 className="text-lg font-bold">QR check-in</h3>
      <p className="text-sm text-slate-400">Scan the student's QR with a handheld scanner (it types the code) or paste the ticket code, then press Enter. The server verifies the ticket belongs to one of your events.</p>
      <input className="input font-mono" autoFocus placeholder="Ticket code" aria-label="Ticket code" value={code} onChange={(e) => setCode(e.target.value)} required minLength={10} />
      <button className="btn-primary">Verify & check in</button>{last && <p role="status" className={`text-sm ${last.startsWith("✓") ? "text-emerald-300" : "text-rose-300"}`}>{last}</p>}</form>
  );
}

export function AttendeesModal({ ev, onClose }: { ev: Ev; onClose: () => void }) {
  const [rows, setRows] = useState<any[] | null>(null); const [fb, setFb] = useState<any[]>([]);
  useEffect(() => { api(`/api/events/${ev.id}/attendees`).then(setRows); api(`/api/events/${ev.id}/feedback`).then(setFb); }, [ev.id]);
  const avg = fb.length ? (fb.reduce((a, b) => a + b.rating, 0) / fb.length).toFixed(1) : "–";
  return (
    <Modal title={`Attendees · ${ev.title}`} onClose={onClose} wide>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-sm text-slate-300"><span>{rows?.filter((r) => r.status === "registered").length ?? 0} registered · {rows?.filter((r) => r.attended).length ?? 0} attended · {rows?.filter((r) => r.status === "waitlisted").length ?? 0} waitlisted · rating {avg} ({fb.length})</span>
        <button className="btn-ghost" onClick={() => download(`/api/events/${ev.id}/attendees.csv`, `attendees_${ev.id}.csv`)}>⬇ Export CSV</button></div>
      <div className="max-h-80 overflow-auto"><table className="w-full"><thead><tr><th className="th">Name</th><th className="th">Email</th><th className="th">Status</th><th className="th">Attended</th></tr></thead>
        <tbody className="divide-y divide-white/5">{rows?.map((r) => <tr key={r.id}><td className="td">{r.name}</td><td className="td text-slate-400">{r.email}</td><td className="td"><Badge s={r.status} /></td><td className="td">{r.attended ? "✓" : "–"}</td></tr>)}</tbody></table></div>
      {fb.length > 0 && <div className="mt-4 space-y-2"><h4 className="font-semibold text-white">Feedback</h4>{fb.slice(0, 5).map((f, i) => <p key={i} className="text-sm text-slate-300"><span className="text-amber-300">{"★".repeat(f.rating)}</span> {f.comment}</p>)}</div>}
    </Modal>
  );
}

export function when(ev: Ev) { return fmt(ev.start_at); }
