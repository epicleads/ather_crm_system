"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

type SessionInfo = { authenticated: boolean; user_type: string };
type Lead = { uid?: string; customer_name?: string; lead_status?: string; final_status?: string };

export default function PsLeadDetailPage() {
  const params = useParams<{ uid: string }>();
  const uid = params?.uid;
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [lead, setLead] = useState<Lead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const run = async () => {
      try {
        const s = await fetch("/api/session", { credentials: "include" });
        if (!s.ok) throw new Error("Not authenticated");
        const sj: SessionInfo = await s.json();
        if (sj.user_type !== "ps") throw new Error("Forbidden");
        setSession(sj);
        const res = await fetch(`/api/ps_lead/${uid}`, { credentials: "include" });
        const json = await res.json();
        if (!json.success) throw new Error(json.message || "Failed");
        setLead(json.lead);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Error");
      }
    };
    if (uid) run();
  }, [uid]);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const payload = Object.fromEntries(fd.entries());
    try {
      setSaving(true);
      const res = await fetch(`/api/ps_lead/${uid}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload),
      });
      const json = await res.json();
      if (!json.success) throw new Error(json.message || "Failed");
      alert("Updated");
    } catch (e) {
      alert(e instanceof Error ? e.message : "Error");
    } finally {
      setSaving(false);
    }
  }

  if (error) return <div>{error}</div>;
  if (!session || !lead) return <div>Loading...</div>;
  return (
    <form onSubmit={onSubmit} style={{ display: "grid", gap: 8, maxWidth: 600 }}>
      <h3>Lead {lead.uid}</h3>
      <label>
        <div>Customer Name</div>
        <input name="customer_name" defaultValue={lead.customer_name} />
      </label>
      <label>
        <div>Lead Status</div>
        <input name="lead_status" defaultValue={lead.lead_status} />
      </label>
      <label>
        <div>Final Status</div>
        <input name="final_status" defaultValue={lead.final_status} />
      </label>
      <button disabled={saving} type="submit">{saving ? "Saving..." : "Save"}</button>
    </form>
  );
}



