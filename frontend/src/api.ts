export type Role = "student" | "club" | "admin";
export interface User { id: number; email: string; role: Role; full_name: string;
  profile?: { department: string; academic_year: number; roll_no: string };
  club?: { id: number; name: string; status: string; description: string } }
export interface Ev { id: number; title: string; description: string; category: string; category_id: number; club: string; club_id: number;
  venue: string; venue_id: number; start_at: string; end_at: string; capacity: number; seats_left: number; registered: number;
  registration_deadline: string; poster_url: string; eligibility: string; department: string; academic_year: string;
  contact_info: string; status: string; review_note: string; avg_rating?: number | null;
  my_registration?: { id: number; status: string; attended: boolean } | null; bookmarked?: boolean }
export interface Meta { categories: { id: number; name: string }[]; venues: { id: number; name: string; capacity: number }[]; clubs: { id: number; name: string }[] }

const TOKEN = "cc_token";
export const getToken = () => localStorage.getItem(TOKEN);
export const setToken = (t: string | null) => (t ? localStorage.setItem(TOKEN, t) : localStorage.removeItem(TOKEN));

export class ApiError extends Error {
  constructor(public status: number, message: string, public errors: string[] = []) { super(message); }
}

async function raw(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  const t = getToken();
  if (t) headers.set("Authorization", `Bearer ${t}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const res = await fetch(path, { ...init, headers });
  if (!res.ok) {
    let body: any = {};
    try { body = await res.json(); } catch { /* not json */ }
    const errs: string[] = body.errors ?? (Array.isArray(body.detail?.errors) ? body.detail.errors : []);
    const msg = typeof body.detail === "string" ? body.detail : errs[0] ?? body.detail?.errors?.[0] ?? `Request failed (${res.status})`;
    if (res.status === 401 && t) { setToken(null); window.dispatchEvent(new Event("cc-logout")); }
    throw new ApiError(res.status, msg, errs);
  }
  return res;
}

export async function api<T = any>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await raw(path, init);
  return res.status === 204 ? (undefined as T) : res.json();
}
export const post = <T = any>(p: string, body?: unknown) => api<T>(p, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
export const put = <T = any>(p: string, body: unknown) => api<T>(p, { method: "PUT", body: JSON.stringify(body) });
export const patch = <T = any>(p: string, body: unknown) => api<T>(p, { method: "PATCH", body: JSON.stringify(body) });
export const del = (p: string) => api(p, { method: "DELETE" });

/** Authenticated download (CSV/PDF) - links can't carry the bearer token. */
export async function download(path: string, filename: string) {
  const res = await raw(path);
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a"); a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export async function blobUrl(path: string) { return URL.createObjectURL(await (await raw(path)).blob()); }

export const fmt = (iso: string) => new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
export const toLocalInput = (iso?: string) => { if (!iso) return ""; const d = new Date(iso); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16); };
export const fromLocalInput = (v: string) => new Date(v).toISOString();
