import { useState } from "react";
import { ApiError, Ev, fmt, post } from "../api";
import { useAuth } from "../auth";
import { Badge, Confirm, Empty, Modal, Skeleton, useToast } from "../ui";
import { AttendeesModal, EventForm } from "./Manage";

export default function EventsTable({ events, reload }: { events: Ev[] | null; reload: () => void }) {
  const { user } = useAuth(); const toast = useToast();
  const [edit, setEdit] = useState<Ev | null>(null); const [att, setAtt] = useState<Ev | null>(null); const [cancel, setCancel] = useState<Ev | null>(null); const [rej, setRej] = useState<Ev | null>(null); const [note, setNote] = useState("");
  const run = async (fn: () => Promise<unknown>, ok: string) => { try { await fn(); toast(ok); reload(); } catch (x) { const a = x as ApiError; toast(a.message, "err"); } };
  if (!events) return <Skeleton className="h-48" />;
  if (!events.length) return <Empty title="No events yet" hint="Create one manually or import a CSV." />;
  return (
    <>
      <div className="card overflow-x-auto p-0"><table className="w-full min-w-[720px]"><thead className="border-b border-white/10"><tr><th className="th">Event</th>{user?.role === "admin" && <th className="th">Club</th>}<th className="th">When</th><th className="th">Seats</th><th className="th">Status</th><th className="th text-right">Actions</th></tr></thead>
        <tbody className="divide-y divide-white/5">{events.map((e) => (
          <tr key={e.id}><td className="td font-semibold text-white">{e.title}{e.review_note && <p className="text-xs font-normal text-rose-300">Note: {e.review_note}</p>}</td>
            {user?.role === "admin" && <td className="td text-slate-400">{e.club}</td>}
            <td className="td text-slate-400">{fmt(e.start_at)}<br />{e.venue}</td><td className="td">{e.registered}/{e.capacity}</td><td className="td"><Badge s={e.status} /></td>
            <td className="td"><div className="flex flex-wrap justify-end gap-1.5">
              {user?.role === "admin" && e.status === "pending_approval" && <><button className="btn-primary px-3 py-1" onClick={() => run(() => post(`/api/events/${e.id}/approve`), "Event approved")}>Approve</button><button className="btn-ghost px-3 py-1" onClick={() => { setRej(e); setNote(""); }}>Reject</button></>}
              {["draft", "rejected"].includes(e.status) && <button className="btn-primary px-3 py-1" onClick={() => run(() => post(`/api/events/${e.id}/submit`), user?.role === "admin" ? "Published" : "Submitted for approval")}>{user?.role === "admin" ? "Publish" : "Submit"}</button>}
              {!["completed", "cancelled"].includes(e.status) && <button className="btn-ghost px-3 py-1" onClick={() => setEdit(e)}>Edit</button>}
              <button className="btn-ghost px-3 py-1" onClick={() => setAtt(e)}>Attendees</button>
              {!["completed", "cancelled"].includes(e.status) && <button className="btn-ghost px-3 py-1 text-rose-300" onClick={() => setCancel(e)}>Cancel</button>}
            </div></td></tr>))}</tbody></table></div>
      {edit && <EventForm ev={edit} onClose={() => setEdit(null)} onSaved={reload} />}
      {att && <AttendeesModal ev={att} onClose={() => setAtt(null)} />}
      {cancel && <Confirm title="Cancel this event?" text={`All registered students of "${cancel.title}" will be notified.`} onClose={() => setCancel(null)} onYes={() => run(() => post(`/api/events/${cancel.id}/cancel`), "Event cancelled")} />}
      {rej && <Modal title={`Reject "${rej.title}"`} onClose={() => setRej(null)}>
        <textarea className="input mb-3" rows={3} maxLength={500} placeholder="Reason shown to the club" value={note} onChange={(e) => setNote(e.target.value)} />
        <button className="btn-danger w-full" onClick={() => { run(() => post(`/api/events/${rej.id}/reject`, { note }), "Event rejected"); setRej(null); }}>Reject event</button></Modal>}
    </>
  );
}
