"use client";
import { useEffect, useState } from "react";

type SessionInfo = { authenticated: boolean; user_type: string };

export default function ChangePasswordPage() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const run = async () => {
      try {
        const s = await fetch("/api/session", { credentials: "include" });
        if (!s.ok) throw new Error("Not authenticated");
        const sj: SessionInfo = await s.json();
        setSession(sj);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Error");
      }
    };
    run();
  }, []);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const payload = Object.fromEntries(fd.entries());
    try {
      setSaving(true);
      const res = await fetch("/api/change_password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload),
      });
      const json = await res.json();
      if (!json.success) throw new Error(json.message || "Failed");
      alert("Password changed");
    } catch (e) {
      alert(e instanceof Error ? e.message : "Error");
    } finally {
      setSaving(false);
    }
  }

  if (error) return <div>{error}</div>;
  if (!session) return <div>Loading...</div>;
  return (
    <form onSubmit={onSubmit} style={{ display: "grid", gap: 8, maxWidth: 400 }}>
      <h3>Change Password</h3>
      <input name="current_password" placeholder="Current password" type="password" required />
      <input name="new_password" placeholder="New password" type="password" required />
      <input name="confirm_password" placeholder="Confirm password" type="password" required />
      <button disabled={saving} type="submit">{saving ? "Saving..." : "Save"}</button>
    </form>
  );
}



