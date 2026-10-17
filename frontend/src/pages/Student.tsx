import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, blobUrl, del, download, Ev, fmt, post } from "../api";
import { useAuth } from "../auth";
import { Badge, Confirm, Empty, EventCard, Modal, Skeleton, Stat, useToast } from "../ui";

interface Reg { id: number; status: string; attended: boolean; ticket_code: string; event: Ev; feedback_given: boolean }

function QrModal({ reg, onClose }: { reg: Reg; onClose: () => void }) {
  const [src, setSrc] = useState("");
  useEffect(() => { let u = ""; blobUrl(`/api/registrations/${reg.id}/qr.png`).then((x) => { u = x; setSrc(x); }); return () => { if (u) URL.revokeObjectURL(u); }; }, [reg.id]);
  return (
    <Modal title="Your event pass" onClose={onClose}>
      <div className="text-center"><p className="font-semibold text-white">{reg.event.title}</p><p className="text-xs text-slate-400">{fmt(reg.event.start_at)} · {reg.event.venue}</p>
        <div className="mx-auto my-4 flex h-56 w-56 items-center justify-center rounded-2xl bg-white p-3">{src ? <img src={src} alt="Ticket QR code" className="h-full w-full" /> : <Skeleton className="h-full w-full" />}</div>
        <p className="text-xs text-slate-400">Show this at the entrance. It works once.</p></div>
    </Modal>
  );
}

function FeedbackModal({ reg, onClose, onDone }: { reg: Reg; onClose: () => void; onDone: () => void }) {
  const toast = useToast(); const [rating, setRating] = useState(5); const [comment, setComment] = useState("");
  const send = async () => { try { await post(`/api/events/${reg.event.id}/feedback`, { rating, comment }); toast("Thanks for your feedback!"); onDone(); onClose(); } catch (x) { toast((x as ApiError).message, "err"); } };
  return (
    <Modal title={`Rate: ${reg.event.title}`} onClose={onClose}>
      <div className="mb-3 flex gap-1" role="radiogroup" aria-label="Rating">{[1, 2, 3, 4, 5].map((n) => <button key={n} role="radio" aria-checked={rating === n} aria-label={`${n} stars`} onClick={() => setRating(n)} className={`text-3xl ${n <= rating ? "text-amber-300" : "text-slate-600"}`}>★</button>)}</div>
      <textarea className="input mb-4" rows={4} maxLength={2000} placeholder="What did you think?" value={comment} onChange={(e) => setComment(e.target.value)} />
      <button className="btn-primary w-full" onClick={send}>Submit feedback</button>
    </Modal>
  );
}

export default function Student() {
  const { user } = useAuth(); const toast = useToast();
  const [regs, setRegs] = useState<Reg[] | null>(null); const [marks, setMarks] = useState<Ev[] | null>(null);
  const [tab, setTab] = useState<"upcoming" | "history" | "saved" | "calendar">("upcoming");
  const [qr, setQr] = useState<Reg | null>(null); const [fb, setFb] = useState<Reg | null>(null); const [cancel, setCancel] = useState<Reg | null>(null);
  const load = useCallback(() => { api<Reg[]>("/api/me/registrations").then(setRegs); api<Ev[]>("/api/me/bookmarks").then(setMarks); }, []);
  useEffect(load, [load]);
  const now = Date.now();
  const upcoming = regs?.filter((r) => new Date(r.event.end_at).getTime() >= now && r.event.status !== "cancelled") ?? [];
  const history = regs?.filter((r) => !upcoming.includes(r)) ?? [];
  const attended = regs?.filter((r) => r.attended).length ?? 0;
  const run = async (fn: () => Promise<unknown>, ok: string) => { try { await fn(); toast(ok); load(); } catch (x) { toast((x as ApiError).message, "err"); } };
  const Row = ({ r }: { r: Reg }) => (
    <div className="card pop flex flex-wrap items-center gap-3">
      <div className="min-w-0 flex-1"><Link to={`/events/${r.event.id}`} className="font-display font-bold text-white hover:text-indigo-300">{r.event.title}</Link>
        <p className="text-xs text-slate-400">{fmt(r.event.start_at)} · {r.event.venue} · {r.event.club}</p></div>
      <Badge s={r.event.status === "cancelled" ? "cancelled" : r.status} />{r.attended && <Badge s="completed" />}
      <div className="flex flex-wrap gap-2">
        {r.status === "registered" && !r.attended && r.event.status === "published" && <button className="btn-primary" onClick={() => setQr(r)}>QR pass</button>}
        {!r.attended && r.event.status === "published" && new Date(r.event.start_at) > new Date() && <button className="btn-ghost" onClick={() => setCancel(r)}>Cancel</button>}
        {r.attended && !r.feedback_given && <button className="btn-ghost" onClick={() => setFb(r)}>Give feedback</button>}
        {r.attended && new Date(r.event.end_at) < new Date() && <button className="btn-ghost" onClick={() => download(`/api/registrations/${r.id}/certificate`, "certificate.pdf").catch((x) => toast(x.message, "err"))}>Certificate</button>}
      </div>
    </div>
  );
  const byMonth = upcoming.reduce<Record<string, Reg[]>>((a, r) => { const k = new Date(r.event.start_at).toLocaleString(undefined, { month: "long", year: "numeric" }); (a[k] ||= []).push(r); return a; }, {});
  return (
    <div className="space-y-6">
      <div><h1 className="text-3xl font-bold">Hi {user?.full_name.split(" ")[0]} 👋</h1><p className="text-slate-400">Your registrations, passes and saved events.</p></div>
      <div className="grid gap-4 sm:grid-cols-3"><Stat label="Upcoming" value={upcoming.length} /><Stat label="Attended" value={attended} tone="emerald" /><Stat label="Saved" value={marks?.length ?? 0} tone="amber" /></div>
      <div className="flex flex-wrap gap-2" role="tablist">{(["upcoming", "calendar", "saved", "history"] as const).map((t) => <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "btn-primary capitalize" : "btn-ghost capitalize"} onClick={() => setTab(t)}>{t}</button>)}</div>
      {!regs || !marks ? <Skeleton className="h-40" /> : <>
        {tab === "upcoming" && (upcoming.length ? <div className="space-y-3">{upcoming.map((r) => <Row key={r.id} r={r} />)}</div> : <Empty title="No upcoming events" hint="Find something fun in Discover." />)}
        {tab === "history" && (history.length ? <div className="space-y-3">{history.map((r) => <Row key={r.id} r={r} />)}</div> : <Empty title="No history yet" />)}
        {tab === "saved" && (marks.length ? <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{marks.map((e) => <EventCard key={e.id} ev={e} onBookmark={(x) => run(() => del(`/api/events/${x.id}/bookmark`), "Removed")} />)}</div> : <Empty icon="☆" title="Nothing saved" hint="Tap the star on any event to save it." />)}
        {tab === "calendar" && (Object.keys(byMonth).length ? Object.entries(byMonth).map(([m, rs]) => (
          <div key={m} className="mb-4"><h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-indigo-300">{m}</h3>
            <div className="space-y-2">{rs.map((r) => <div key={r.id} className="card flex items-center gap-4 py-3"><div className="w-12 text-center"><div className="font-display text-2xl font-extrabold text-white">{new Date(r.event.start_at).getDate()}</div><div className="text-xs text-slate-400">{new Date(r.event.start_at).toLocaleString(undefined, { weekday: "short" })}</div></div><div><p className="font-semibold text-white">{r.event.title}</p><p className="text-xs text-slate-400">{new Date(r.event.start_at).toLocaleTimeString(undefined, { timeStyle: "short" })} · {r.event.venue}</p></div></div>)}</div></div>)) : <Empty title="Your calendar is clear" />)}
      </>}
      {qr && <QrModal reg={qr} onClose={() => setQr(null)} />}
      {fb && <FeedbackModal reg={fb} onClose={() => setFb(null)} onDone={load} />}
      {cancel && <Confirm title="Cancel registration?" text={`Release your seat for "${cancel.event.title}"?`} onClose={() => setCancel(null)} onYes={() => run(() => del(`/api/events/${cancel.event.id}/register`), "Registration cancelled")} />}
    </div>
  );
}
