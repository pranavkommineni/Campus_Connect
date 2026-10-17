import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Ev } from "../api";
import { useAuth } from "../auth";
import { EventCard, Skeleton } from "../ui";

export default function Landing() {
  const { user } = useAuth();
  const [evs, setEvs] = useState<Ev[] | null>(null);
  useEffect(() => { api<{ items: Ev[] }>("/api/events?page_size=3").then((r) => setEvs(r.items)).catch(() => setEvs([])); }, []);
  return (
    <div className="space-y-14">
      <section className="pt-8 text-center">
        <p className="mb-3 inline-block rounded-full border border-indigo-400/30 bg-indigo-500/10 px-3 py-1 text-xs font-semibold text-indigo-300">One home for every campus event</p>
        <h1 className="mx-auto max-w-3xl text-4xl font-extrabold leading-tight sm:text-6xl">Find it. <span className="bg-gradient-to-r from-indigo-400 to-sky-300 bg-clip-text text-transparent">Join it.</span> Be there.</h1>
        <p className="mx-auto mt-4 max-w-xl text-slate-400">Discover hackathons, workshops and cultural nights, grab a QR pass in one tap, and collect certificates - while clubs and admins run it all from a single place.</p>
        <div className="mt-7 flex justify-center gap-3">
          <Link to="/events" className="btn-primary px-6 py-3">Browse events</Link>
          {!user && <Link to="/register" className="btn-ghost px-6 py-3">Create account</Link>}
        </div>
      </section>
      <section className="grid gap-4 sm:grid-cols-3">
        {[["🎟️", "Instant QR passes", "Register in a tap, get a unique ticket, check in at the door."],
          ["⏳", "Smart waitlists", "Full event? You are queued and auto-promoted when a seat frees up."],
          ["📊", "Live organizer insights", "Registrations, attendance and feedback in real time."]].map(([i, t, d]) => (
          <div key={t} className="card"><div className="text-2xl">{i}</div><h3 className="mt-2 font-bold">{t}</h3><p className="mt-1 text-sm text-slate-400">{d}</p></div>))}
      </section>
      <section>
        <div className="mb-4 flex items-end justify-between"><h2 className="text-2xl font-bold">Happening soon</h2><Link to="/events" className="text-sm text-indigo-300">See all →</Link></div>
        <div className="grid gap-4 sm:grid-cols-3">{evs ? evs.map((e) => <EventCard key={e.id} ev={e} />) : [1, 2, 3].map((i) => <Skeleton key={i} className="h-72" />)}</div>
      </section>
    </div>
  );
}
