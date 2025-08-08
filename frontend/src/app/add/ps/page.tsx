"use client";
import { useEffect, useState } from "react";

type SessionInfo = { authenticated: boolean; user_type: string };
const BRANCHES = [
  "SOMAJIGUDA",
  "ATTAPUR",
  "BEGUMPET",
  "KOMPALLY",
  "MALAKPET",
  "SRINAGAR COLONY",
  "TOLICHOWKI",
  "VANASTHALIPURAM",
] as const;

export default function AddPsPage() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const run = async () => {
      try {
        const s = await fetch("/api/session", { credentials: "include" });
        if (!s.ok) throw new Error("Not authenticated");
        const sj: SessionInfo = await s.json();
        if (sj.user_type !== "admin") throw new Error("Forbidden");
        setSession(sj);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Error");
      }
    };
    run();
  }, []);

  async function onSubmit(formData: FormData) {
    try {
      setSaving(true);
      const payload = Object.fromEntries(formData.entries());
      const res = await fetch("/api/add_ps", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload),
      });
      const json = await res.json();
      if (!json.success) throw new Error(json.message || "Failed");
      alert("PS added");
    } catch (e) {
      alert(e instanceof Error ? e.message : "Error");
    } finally {
      setSaving(false);
    }
  }

  if (error) return <div>{error}</div>;
  if (!session) return <div>Loading...</div>;
  return (
    <form onSubmit={(e) => {
      e.preventDefault();
      const fd = new FormData(e.currentTarget as HTMLFormElement);
      onSubmit(fd);
    }} style={{ display: "grid", gap: 8, maxWidth: 400 }}>
      <h3>Add PS</h3>
      <input name="name" placeholder="Name" required />
      <input name="username" placeholder="Username" required />
      <input name="password" placeholder="Password" required />
      <input name="phone" placeholder="Phone" required />
      <input name="email" placeholder="Email" type="email" required />
      <select name="branch" required>
        <option value="">Select branch</option>
        {BRANCHES.map((b) => (
          <option key={b} value={b}>{b}</option>
        ))}
      </select>
      <button disabled={saving} type="submit">{saving ? "Saving..." : "Save"}</button>
    </form>
  );
}


