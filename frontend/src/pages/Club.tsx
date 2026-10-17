import { useCallback, useEffect, useState } from "react";
import { api, Ev } from "../api";
import { useAuth } from "../auth";
import { Stat } from "../ui";
import { CheckIn, EventForm, ImportWizard } from "./Manage";
import EventsTable from "./EventsTable";

export default function Club() {
  const { user } = useAuth();
  const [events, setEvents] = useState<Ev[] | null>(null); const [tab, setTab] = useState<"events" | "import" | "checkin">("events"); const [creating, setCreating] = useState(false);
  const load = useCallback(() => { api<Ev[]>("/api/events/manage").then(setEvents); }, []);
  useEffect(load, [load]);
  const approved = user?.club?.status === "approved";
  const reg = events?.reduce((a, e) => a + e.registered, 0) ?? 0;
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><h1 className="text-3xl font-bold">{user?.club?.name}</h1><p className="text-slate-400">Club dashboard</p></div>
        <button className="btn-primary" disabled={!approved} onClick={() => setCreating(true)}>+ New event</button></div>
      {!approved && <div className="card border-amber-400/40 text-sm text-amber-200">Your club is <strong>{user?.club?.status}</strong>. You can publish events once an admin approves it.</div>}
      <div className="grid gap-4 sm:grid-cols-4"><Stat label="Events" value={events?.length ?? "–"} /><Stat label="Published" value={events?.filter((e) => e.status === "published").length ?? "–"} tone="emerald" />
        <Stat label="Awaiting approval" value={events?.filter((e) => e.status === "pending_approval").length ?? "–"} tone="amber" /><Stat label="Registrations" value={reg} tone="sky" /></div>
      <div className="flex gap-2" role="tablist">{([["events", "My events"], ["import", "CSV import"], ["checkin", "Check-in"]] as const).map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "btn-primary" : "btn-ghost"} onClick={() => setTab(k)}>{l}</button>)}</div>
      {tab === "events" && <EventsTable events={events} reload={load} />}
      {tab === "import" && (approved ? <ImportWizard onDone={load} /> : <p className="text-slate-400">Available after approval.</p>)}
      {tab === "checkin" && <CheckIn />}
      {creating && <EventForm onClose={() => setCreating(false)} onSaved={load} />}
    </div>
  );
}
