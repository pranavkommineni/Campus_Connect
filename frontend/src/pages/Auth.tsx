import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, post } from "../api";
import { useAuth } from "../auth";
import { ErrorList, Field } from "../ui";

const home = { student: "/student", club: "/club", admin: "/admin" } as const;

export function Login() {
  const { login } = useAuth(); const nav = useNavigate();
  const [f, setF] = useState({ email: "", password: "" }); const [err, setErr] = useState<string[]>([]); const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => { e.preventDefault(); setBusy(true); setErr([]);
    try { const r = await post("/api/auth/login", f); login(r.token, r.user); nav(home[r.user.role as keyof typeof home]); }
    catch (x) { setErr([(x as ApiError).message]); } finally { setBusy(false); } };
  return (
    <form onSubmit={submit} className="card pop mx-auto max-w-md space-y-4">
      <h1 className="text-2xl font-bold">Welcome back</h1><ErrorList errors={err} />
      <Field label="Email"><input className="input" type="email" required autoComplete="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
      <Field label="Password"><input className="input" type="password" required autoComplete="current-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></Field>
      <button className="btn-primary w-full" disabled={busy}>{busy ? "Signing in…" : "Log in"}</button>
      <p className="text-center text-sm text-slate-400">New here? <Link className="text-indigo-300" to="/register">Create an account</Link></p>
    </form>
  );
}

export function Register() {
  const { login } = useAuth(); const nav = useNavigate();
  const [kind, setKind] = useState<"student" | "club">("student");
  const [f, setF] = useState({ email: "", password: "", full_name: "", department: "", academic_year: 1, club_name: "", description: "" });
  const [err, setErr] = useState<string[]>([]); const [busy, setBusy] = useState(false);
  const set = (k: string, v: any) => setF({ ...f, [k]: v });
  const submit = async (e: FormEvent) => { e.preventDefault(); setBusy(true); setErr([]);
    try { const r = kind === "student" ? await post("/api/auth/register", f) : await post("/api/auth/register-club", f);
      login(r.token, r.user); nav(home[r.user.role as keyof typeof home]); }
    catch (x) { const a = x as ApiError; setErr(a.errors.length ? a.errors : [a.message]); } finally { setBusy(false); } };
  return (
    <form onSubmit={submit} className="card pop mx-auto max-w-md space-y-4">
      <h1 className="text-2xl font-bold">Create your account</h1>
      <div className="grid grid-cols-2 gap-2" role="tablist">{(["student", "club"] as const).map((k) => (
        <button type="button" key={k} role="tab" aria-selected={kind === k} onClick={() => setKind(k)} className={kind === k ? "btn-primary" : "btn-ghost"}>{k === "student" ? "I'm a student" : "I run a club"}</button>))}</div>
      <ErrorList errors={err} />
      <Field label="Full name"><input className="input" required minLength={2} value={f.full_name} onChange={(e) => set("full_name", e.target.value)} /></Field>
      <Field label="Email"><input className="input" type="email" required value={f.email} onChange={(e) => set("email", e.target.value)} /></Field>
      <Field label="Password" hint="At least 8 characters"><input className="input" type="password" required minLength={8} maxLength={72} value={f.password} onChange={(e) => set("password", e.target.value)} /></Field>
      {kind === "student" ? (<div className="grid grid-cols-2 gap-3">
        <Field label="Department"><input className="input" value={f.department} onChange={(e) => set("department", e.target.value)} /></Field>
        <Field label="Year"><select className="input" value={f.academic_year} onChange={(e) => set("academic_year", +e.target.value)}>{[1, 2, 3, 4].map((y) => <option key={y}>{y}</option>)}</select></Field></div>)
        : (<><Field label="Club name"><input className="input" required minLength={2} value={f.club_name} onChange={(e) => set("club_name", e.target.value)} /></Field>
          <Field label="About the club"><textarea className="input" rows={3} value={f.description} onChange={(e) => set("description", e.target.value)} /></Field>
          <p className="text-xs text-amber-300">Club accounts need admin approval before they can publish events.</p></>)}
      <button className="btn-primary w-full" disabled={busy}>{busy ? "Creating…" : "Create account"}</button>
      <p className="text-center text-sm text-slate-400">Already registered? <Link className="text-indigo-300" to="/login">Log in</Link></p>
    </form>
  );
}
