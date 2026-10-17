import { FormEvent, useEffect, useState } from "react";
import { api, ApiError, fmt, patch, post } from "../api";
import { useAuth } from "../auth";
import { Empty, Field, Skeleton, useToast } from "../ui";

export function Notifications() {
  const [items, setItems] = useState<{ id: number; message: string; is_read: boolean; created_at: string }[] | null>(null);
  const load = () => api("/api/notifications").then(setItems);
  useEffect(() => { load(); }, []);
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div className="flex items-center justify-between"><h1 className="text-3xl font-bold">Notifications</h1>
        <button className="btn-ghost" onClick={async () => { await post("/api/notifications/read-all"); load(); }}>Mark all read</button></div>
      {!items ? <Skeleton className="h-40" /> : items.length === 0 ? <Empty icon="🔔" title="You're all caught up" /> :
        items.map((n) => <div key={n.id} className={`card pop py-3 ${n.is_read ? "opacity-60" : "border-indigo-400/40"}`}><p className="text-sm text-white">{n.message}</p><p className="mt-1 text-xs text-slate-500">{fmt(n.created_at)}</p></div>)}
    </div>
  );
}

export function Profile() {
  const { user, refresh } = useAuth(); const toast = useToast();
  const [f, setF] = useState({ full_name: user?.full_name ?? "", department: user?.profile?.department ?? "", academic_year: user?.profile?.academic_year ?? 1, description: user?.club?.description ?? "" });
  const save = async (e: FormEvent) => { e.preventDefault(); try { await patch("/api/auth/me", f); await refresh(); toast("Profile saved"); } catch (x) { toast((x as ApiError).message, "err"); } };
  if (!user) return null;
  return (
    <form onSubmit={save} className="card mx-auto max-w-md space-y-4">
      <h1 className="text-2xl font-bold">Profile settings</h1>
      <p className="text-sm text-slate-400">{user.email} · <span className="capitalize">{user.role}</span>{user.club && ` · ${user.club.name} (${user.club.status})`}</p>
      <Field label="Full name"><input className="input" required minLength={2} value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></Field>
      {user.role === "student" && <div className="grid grid-cols-2 gap-3"><Field label="Department"><input className="input" value={f.department} onChange={(e) => setF({ ...f, department: e.target.value })} /></Field>
        <Field label="Year"><select className="input" value={f.academic_year} onChange={(e) => setF({ ...f, academic_year: +e.target.value })}>{[1, 2, 3, 4].map((y) => <option key={y}>{y}</option>)}</select></Field></div>}
      {user.role === "club" && <Field label="About the club"><textarea className="input" rows={4} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>}
      <button className="btn-primary w-full">Save changes</button>
    </form>
  );
}
