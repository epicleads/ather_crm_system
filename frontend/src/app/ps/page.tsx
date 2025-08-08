"use client";
import { useEffect, useState } from "react";

type SessionInfo = {
  authenticated: boolean;
  user_type: string;
  username?: string;
  branch?: string;
  ps_name?: string;
};
type Lead = {
  uid?: string;
  customer_name?: string;
  customer_mobile_number?: string;
};

export default function PsPage() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);

  useEffect(() => {
    const run = async () => {
      try {
        const res = await fetch("/api/session", { credentials: "include" });
        if (!res.ok) throw new Error("Not authenticated");
        const json: SessionInfo = await res.json();
        if (json.user_type !== "ps") throw new Error("Forbidden");
        setSession(json);
        const leadsRes = await fetch("/dashboard_leads_optimized?per_page=25", {
          credentials: "include",
        });
        if (leadsRes.ok) {
          const data = await leadsRes.json();
          if (data.success) setLeads(data.leads || []);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Error");
      }
    };
    run();
  }, []);

  if (error) return <div>{error}</div>;
  if (!session) return <div>Loading...</div>;
  return (
    <div>
      <h3>PS Dashboard (Next.js)</h3>
      <div>PS: {session.ps_name || session.username}</div>
      <div>Branch: {session.branch || "-"}</div>
      <div style={{ marginTop: 16 }}>
        <strong>Recent Leads</strong>
        <ul>
          {leads.map((l, i) => (
            <li key={i}>{l.customer_name || l.customer_mobile_number || l.uid}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}



