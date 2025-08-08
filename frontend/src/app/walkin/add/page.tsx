"use client";
import { useEffect, useState } from "react";

type SessionInfo = { authenticated: boolean; user_type: string; branch?: string };

export default function AddWalkinLeadPage() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const run = async () => {
      try {
        const s = await fetch("/api/session", { credentials: "include" });
        if (!s.ok) throw new Error("Not authenticated");
        const sj: SessionInfo = await s.json();
        if (sj.user_type !== "rec") throw new Error("Forbidden");
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
      const res = await fetch("/api/add_walkin_lead", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload),
      });
      const json = await res.json();
      if (!json.success) throw new Error(json.message || "Failed");
      alert(`Walk-in lead added: ${json.uid}`);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Error");
    } finally {
      setSaving(false);
    }
  }

  if (error) return <div>{error}</div>;
  if (!session) return <div>Loading...</div>;
  return (
    <form onSubmit={onSubmit} style={{ display: "grid", gap: 8, maxWidth: 500 }}>
      <h3>Add Walk-in Lead</h3>
      <input name="customer_name" placeholder="Customer name" required />
      <input name="mobile_number" placeholder="Mobile number" required />
      <input name="customer_location" placeholder="Location" />
      <input name="model_interested" placeholder="Model interested" />
      <input name="occupation" placeholder="Occupation" />
      <input name="branch" placeholder="Branch" defaultValue={session.branch} />
      <input name="ps_assigned" placeholder="PS assigned" />
      <button disabled={saving} type="submit">{saving ? "Saving..." : "Save"}</button>
    </form>
  );
}


