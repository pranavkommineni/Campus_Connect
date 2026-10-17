import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError, del, Ev, fmt, Meta, post } from "../api";
import { useAuth } from "../auth";
import { Badge, Confirm, Empty, EventCard, Poster, Skeleton, useToast } from "../ui";

export function Events() {
  const { user } = useAuth(); const toast = useToast();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [q, setQ] = useState(""); const [cat, setCat] = useState(""); const [club, setClub] = useState(""); const [from, setFrom] = useState(""); const [sort, setSort] = useState("start"); const [page, setPage] = useState(1);
  const [data, setData] = useState<{ items: Ev[]; total: number; page_size: number } | null>(null);
  useEffect(() => { api<Meta>("/api/meta").then(setMeta).catch(() => {}); }, []);
  const load = useCallback(() => {
    const p = new URLSearchParams({ sort, page: String(page), page_size: "9" });
    if (q) p.set("q", q); if (cat) p.set("category_id", cat); if (club) p.set("club_id", club); if (from) p.set("date_from", new Date(from).toISOString());
    setData(null); api(`/api/events?${p}`).then(setData).catch((e) => { toast(e.message, "err"); setData({ items: [], total: 0, page_size: 9 }); });
  }, [q, cat, club, from, sort, page, toast]);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);
  const bookmark = async (e: Ev) => { if (user?.role !== "student") return toast("Log in as a student to bookmark events", "err");
    try { e.bookmarked ? await del(`/api/events/${e.id}/bookmark`) : await post(`/api/events/${e.id}/bookmark`); load(); } catch (x) { toast((x as ApiError).message, "err"); } };
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const reset = (fn: () => void) => { fn(); setPage(1); };
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Discover events</h1>
      <div className="card grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <input className="input lg:col-span-2" placeholder="Search events…" aria-label="Search" value={q} onChange={(e) => reset(() => setQ(e.target.value))} />
        <select className="input" aria-label="Category" value={cat} onChange={(e) => reset(() => setCat(e.target.value))}><option value="">All categories</option>{meta?.categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
        <select className="input" aria-label="Club" value={club} onChange={(e) => reset(() => setClub(e.target.value))}><option value="">All clubs</option>{meta?.clubs.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
        <select className="input" aria-label="Sort" value={sort} onChange={(e) => setSort(e.target.value)}><option value="start">Soonest first</option><option value="-start">Latest first</option><option value="title">Title A–Z</option></select>
        <input className="input" type="date" aria-label="From date" value={from} onChange={(e) => reset(() => setFrom(e.target.value))} />
      </div>
      {!data ? <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-72" />)}</div>
        : data.items.length === 0 ? <Empty title="No events match your filters" hint="Try clearing the search or picking another category." />
        : <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{data.items.map((e) => <EventCard key={e.id} ev={e} onBookmark={bookmark} />)}</div>}
      <div className="flex items-center justify-center gap-3"><button className="btn-ghost" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Prev</button><span className="text-sm text-slate-400">Page {page} / {pages}</span><button className="btn-ghost" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next →</button></div>
    </div>
  );
}

export function EventDetail() {
  const { id } = useParams(); const { user } = useAuth(); const nav = useNavigate(); const toast = useToast();
  const [ev, setEv] = useState<Ev | null>(null); const [missing, setMissing] = useState(false); const [confirm, setConfirm] = useState(false); const [busy, setBusy] = useState(false);
  const load = useCallback(() => { api<Ev>(`/api/events/${id}`).then(setEv).catch(() => setMissing(true)); }, [id]);
  useEffect(load, [load]);
  if (missing) return <Empty icon="🔍" title="Event not found" hint="It may be unpublished or removed." />;
  if (!ev) return <Skeleton className="h-96" />;
  const reg = ev.my_registration; const open = ev.status === "published" && new Date(ev.registration_deadline) > new Date();
  const act = async (fn: () => Promise<unknown>, ok: string) => { setBusy(true); try { await fn(); toast(ok); load(); } catch (x) { toast((x as ApiError).message, "err"); } finally { setBusy(false); } };
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-4 lg:col-span-2">
        <Poster ev={ev} className="h-72" />
        <div className="flex flex-wrap items-center gap-3"><h1 className="text-3xl font-bold">{ev.title}</h1><Badge s={ev.status} /></div>
        <p className="whitespace-pre-line text-slate-300">{ev.description || "No description provided."}</p>
        <div className="card grid gap-3 text-sm sm:grid-cols-2">
          <div><span className="label">Starts</span>{fmt(ev.start_at)}</div><div><span className="label">Ends</span>{fmt(ev.end_at)}</div>
          <div><span className="label">Venue</span>{ev.venue}</div><div><span className="label">Organizer</span>{ev.club}</div>
          <div><span className="label">Register by</span>{fmt(ev.registration_deadline)}</div><div><span className="label">Eligibility</span>{ev.eligibility}</div>
          {ev.contact_info && <div><span className="label">Contact</span>{ev.contact_info}</div>}
          {ev.avg_rating && <div><span className="label">Rating</span>{"★".repeat(Math.round(ev.avg_rating))} {ev.avg_rating}</div>}
        </div>
      </div>
      <aside className="card h-fit space-y-4">
        <div><p className="text-xs uppercase tracking-wide text-slate-400">Seat availability</p>
          <p className="font-display text-3xl font-extrabold text-white">{ev.seats_left}<span className="text-base font-medium text-slate-400"> / {ev.capacity}</span></p>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/10"><div className="h-full bg-gradient-to-r from-indigo-400 to-sky-400" style={{ width: `${Math.min(100, (ev.registered / ev.capacity) * 100)}%` }} /></div></div>
        {!user ? <button className="btn-primary w-full" onClick={() => nav("/login")}>Log in to register</button>
          : user.role !== "student" ? <p className="text-sm text-slate-400">Only student accounts can register for events.</p>
          : reg ? (<div className="space-y-2"><div className="flex items-center justify-between"><span className="text-sm">Your status</span><Badge s={reg.status} /></div>
              {reg.status === "registered" && <Link to="/student" className="btn-primary w-full">View my QR pass</Link>}
              {!reg.attended && <button className="btn-ghost w-full" disabled={busy} onClick={() => setConfirm(true)}>Cancel registration</button>}</div>)
          : <button className="btn-primary w-full" disabled={busy || !open} onClick={() => act(() => post(`/api/events/${ev.id}/register`), ev.seats_left ? "You're registered!" : "Added to the waitlist")}>
              {!open ? "Registration closed" : ev.seats_left ? "Register now" : "Join waitlist"}</button>}
        {user?.role === "student" && <button className="btn-ghost w-full" onClick={() => act(() => (ev.bookmarked ? del(`/api/events/${ev.id}/bookmark`) : post(`/api/events/${ev.id}/bookmark`)), ev.bookmarked ? "Bookmark removed" : "Bookmarked")}>{ev.bookmarked ? "★ Bookmarked" : "☆ Bookmark"}</button>}
      </aside>
      {confirm && <Confirm title="Cancel registration?" text="Your seat will be released to the next person on the waitlist." onClose={() => setConfirm(false)} onYes={() => act(() => del(`/api/events/${ev.id}/register`), "Registration cancelled")} />}
    </div>
  );
}
