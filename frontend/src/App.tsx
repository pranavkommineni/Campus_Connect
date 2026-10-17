import { ReactNode, useEffect, useState } from "react";
import { Link, NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { api, Role } from "./api";
import { useAuth } from "./auth";
import { Skeleton } from "./ui";
import Landing from "./pages/Landing";
import { Login, Register } from "./pages/Auth";
import { EventDetail, Events } from "./pages/Events";
import Student from "./pages/Student";
import Club from "./pages/Club";
import Admin from "./pages/Admin";
import { Notifications, Profile } from "./pages/Shared";

const home: Record<Role, string> = { student: "/student", club: "/club", admin: "/admin" };

function Guard({ role, children }: { role?: Role; children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="mx-auto max-w-5xl p-8"><Skeleton className="h-64" /></div>;
  if (!user) return <Navigate to="/login" replace />;
  if (role && user.role !== role) return <Navigate to={home[user.role]} replace />;
  return <>{children}</>;
}

function Nav() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [unread, setUnread] = useState(0);
  useEffect(() => { if (user) api<{ is_read: boolean }[]>("/api/notifications").then((n) => setUnread(n.filter((x) => !x.is_read).length)).catch(() => {}); }, [user]);
  const link = ({ isActive }: { isActive: boolean }) => `rounded-lg px-3 py-1.5 text-sm font-medium ${isActive ? "bg-white/10 text-white" : "text-slate-300 hover:text-white"}`;
  return (
    <header className="sticky top-0 z-30 border-b border-white/10 bg-ink-950/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-2 px-4 py-3">
        <Link to="/" className="mr-4 font-display text-xl font-extrabold text-white">Campus<span className="text-indigo-400">Connect</span></Link>
        <NavLink to="/events" className={link}>Discover</NavLink>
        {user && <NavLink to={home[user.role]} className={link}>{user.role === "student" ? "My Events" : user.role === "club" ? "Club Dashboard" : "Admin Console"}</NavLink>}
        <div className="ml-auto flex items-center gap-2">
          {user ? (<>
            <NavLink to="/notifications" className={link} aria-label="Notifications">🔔{unread > 0 && <span className="ml-1 rounded-full bg-rose-500 px-1.5 text-xs text-white">{unread}</span>}</NavLink>
            <NavLink to="/profile" className={link}>{user.full_name.split(" ")[0]}</NavLink>
            <button className="btn-ghost" onClick={() => { logout(); nav("/"); }}>Log out</button>
          </>) : (<><Link to="/login" className="btn-ghost">Log in</Link><Link to="/register" className="btn-primary">Join</Link></>)}
        </div>
      </div>
    </header>
  );
}

export default function App() {
  return (
    <>
      <Nav />
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/events" element={<Events />} />
          <Route path="/events/:id" element={<EventDetail />} />
          <Route path="/student" element={<Guard role="student"><Student /></Guard>} />
          <Route path="/club/*" element={<Guard role="club"><Club /></Guard>} />
          <Route path="/admin/*" element={<Guard role="admin"><Admin /></Guard>} />
          <Route path="/notifications" element={<Guard><Notifications /></Guard>} />
          <Route path="/profile" element={<Guard><Profile /></Guard>} />
          <Route path="*" element={<div className="card text-center">Page not found. <Link className="text-indigo-300" to="/">Go home</Link></div>} />
        </Routes>
      </main>
    </>
  );
}
