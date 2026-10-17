import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Ev, fmt } from "./api";

// ---- toasts ----
const ToastCtx = createContext<(msg: string, kind?: "ok" | "err") => void>(() => {});
export const useToast = () => useContext(ToastCtx);
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<{ id: number; msg: string; kind: string }[]>([]);
  const push = useCallback((msg: string, kind: "ok" | "err" = "ok") => {
    const id = Date.now() + Math.random();
    setItems((s) => [...s, { id, msg, kind }]);
    setTimeout(() => setItems((s) => s.filter((i) => i.id !== id)), 4000);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2" role="status" aria-live="polite">
        {items.map((i) => (
          <div key={i.id} className={`pop rounded-xl px-4 py-3 text-sm font-medium shadow-xl ${i.kind === "ok" ? "bg-emerald-600" : "bg-rose-600"} text-white`}>{i.msg}</div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

// ---- modal / confirm ----
export function Modal({ title, onClose, children, wide }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  useEffect(() => { const h = (e: KeyboardEvent) => e.key === "Escape" && onClose(); window.addEventListener("keydown", h); return () => window.removeEventListener("keydown", h); }, [onClose]);
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label={title} className={`pop card max-h-[90vh] w-full overflow-auto bg-ink-900 ${wide ? "max-w-3xl" : "max-w-md"}`} onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between"><h3 className="text-lg font-bold">{title}</h3><button className="text-slate-400 hover:text-white" aria-label="Close" onClick={onClose}>✕</button></div>
        {children}
      </div>
    </div>
  );
}
export function Confirm({ title, text, onYes, onClose, danger = true }: { title: string; text: string; onYes: () => void; onClose: () => void; danger?: boolean }) {
  return (
    <Modal title={title} onClose={onClose}>
      <p className="mb-5 text-sm text-slate-300">{text}</p>
      <div className="flex justify-end gap-2"><button className="btn-ghost" onClick={onClose}>Cancel</button>
        <button className={danger ? "btn-danger" : "btn-primary"} onClick={() => { onYes(); onClose(); }}>Confirm</button></div>
    </Modal>
  );
}

// ---- small pieces ----
export const Skeleton = ({ className = "h-24" }: { className?: string }) => <div className={`animate-pulse rounded-2xl bg-white/5 ${className}`} />;
export const Empty = ({ icon = "✦", title, hint }: { icon?: string; title: string; hint?: string }) => (
  <div className="card py-12 text-center"><div className="mb-2 text-3xl text-indigo-300">{icon}</div><p className="font-semibold text-white">{title}</p>{hint && <p className="mt-1 text-sm text-slate-400">{hint}</p>}</div>
);
const colors: Record<string, string> = { published: "emerald", registered: "emerald", approved: "emerald", completed: "sky", draft: "slate", pending_approval: "amber", pending: "amber", waitlisted: "amber", rejected: "rose", cancelled: "rose", suspended: "rose" };
export const Badge = ({ s }: { s: string }) => {
  const c = colors[s] ?? "slate";
  const map: Record<string, string> = { emerald: "bg-emerald-500/15 text-emerald-300", sky: "bg-sky-500/15 text-sky-300", slate: "bg-slate-500/20 text-slate-300", amber: "bg-amber-500/15 text-amber-300", rose: "bg-rose-500/15 text-rose-300" };
  return <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${map[c]}`}>{s.replace("_", " ")}</span>;
};
export const Field = ({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) => (
  <label className="block"><span className="label">{label}</span>{children}{hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}</label>
);
export const ErrorList = ({ errors }: { errors: string[] }) => errors.length ? (
  <ul role="alert" className="mb-3 list-disc rounded-xl bg-rose-500/10 py-2 pl-8 pr-3 text-sm text-rose-300">{errors.map((e, i) => <li key={i}>{e}</li>)}</ul>) : null;
export const Stat = ({ label, value, tone = "indigo" }: { label: string; value: ReactNode; tone?: string }) => (
  <div className="card"><p className="text-xs uppercase tracking-wide text-slate-400">{label}</p><p className={`mt-1 font-display text-3xl font-extrabold text-${tone}-300`}>{value}</p></div>
);

const grads = ["from-indigo-600 to-violet-600", "from-sky-600 to-indigo-700", "from-fuchsia-600 to-indigo-700", "from-emerald-600 to-sky-700", "from-amber-500 to-rose-600"];
export function Poster({ ev, className = "h-40" }: { ev: Pick<Ev, "id" | "title" | "poster_url" | "category">; className?: string }) {
  const [bad, setBad] = useState(false);
  if (ev.poster_url && !bad) return <img src={ev.poster_url} alt={`${ev.title} poster`} onError={() => setBad(true)} className={`${className} w-full rounded-xl object-cover`} />;
  return (
    <div className={`${className} flex w-full flex-col justify-end rounded-xl bg-gradient-to-br ${grads[ev.id % grads.length]} p-4`}>
      <span className="text-xs font-semibold uppercase tracking-widest text-white/70">{ev.category}</span>
      <span className="font-display text-lg font-extrabold leading-tight text-white">{ev.title}</span>
    </div>
  );
}

export function EventCard({ ev, onBookmark }: { ev: Ev; onBookmark?: (e: Ev) => void }) {
  const low = ev.seats_left > 0 && ev.seats_left <= Math.max(3, ev.capacity * 0.1);
  return (
    <article className="card pop flex flex-col gap-3 transition hover:-translate-y-1 hover:border-indigo-400/40">
      <Link to={`/events/${ev.id}`}><Poster ev={ev} /></Link>
      <div className="flex items-start justify-between gap-2">
        <Link to={`/events/${ev.id}`} className="font-display text-base font-bold text-white hover:text-indigo-300">{ev.title}</Link>
        {onBookmark && <button aria-label={ev.bookmarked ? "Remove bookmark" : "Bookmark"} onClick={() => onBookmark(ev)} className={`text-xl ${ev.bookmarked ? "text-amber-300" : "text-slate-500 hover:text-amber-200"}`}>{ev.bookmarked ? "★" : "☆"}</button>}
      </div>
      <p className="text-xs text-slate-400">{fmt(ev.start_at)} · {ev.venue}</p>
      <p className="text-xs text-indigo-300">by {ev.club}</p>
      <div className="mt-auto flex items-center justify-between">
        <span className={`text-xs font-semibold ${ev.seats_left === 0 ? "text-rose-300" : low ? "text-amber-300" : "text-emerald-300"}`}>{ev.seats_left === 0 ? "Full · waitlist open" : `${ev.seats_left} seats left`}</span>
        {ev.my_registration && <Badge s={ev.my_registration.status} />}
      </div>
    </article>
  );
}
