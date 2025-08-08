"use client";
import { useEffect, useState } from "react";

type SessionInfo = { authenticated: boolean; user_type: string };
type Lead = { uid?: string; customer_name?: string; source?: string; cre_name?: string; final_status?: string };

export default function ManageLeadsPage() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const run = async () => {
      try {
        const s = await fetch("/api/session", { credentials: "include" });
        if (!s.ok) throw new Error("Not authenticated");
        const sj: SessionInfo = await s.json();
        if (sj.user_type !== "admin") throw new Error("Forbidden");
        setSession(sj);
        const res = await fetch("/api/leads_admin?per_page=50", { credentials: "include" });
        const json = await res.json();
        if (!json.success) throw new Error(json.message || "Error");
        setLeads(json.leads || []);
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
      <h3>Manage Leads</h3>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left" }}>UID</th>
            <th style={{ textAlign: "left" }}>Customer</th>
            <th style={{ textAlign: "left" }}>Source</th>
            <th style={{ textAlign: "left" }}>CRE</th>
            <th style={{ textAlign: "left" }}>Final Status</th>
          </tr>
        </thead>
        <tbody>
          {leads.map((l) => (
            <tr key={l.uid}>
              <td>{l.uid}</td>
              <td>{l.customer_name}</td>
              <td>{l.source}</td>
              <td>{l.cre_name}</td>
              <td>{l.final_status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}



