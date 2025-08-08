"use client";
import { useEffect, useState } from "react";

type SessionInfo = { authenticated: boolean; user_type: string; branch?: string };
type KPI = {
  total_walkin_count: number;
  won_leads_count: number;
  lost_leads_count: number;
  pending_leads_count: number;
  first_call_response_rate: number;
  today_leads_count: number;
  conversion_rate: number;
};

export default function RecDashboardPage() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [kpis, setKpis] = useState<KPI | null>(null);
  type WalkinLead = { customer_name?: string; mobile_number?: string; status?: string };
  const [leads, setLeads] = useState<WalkinLead[]>([]);

  useEffect(() => {
    const run = async () => {
      try {
        const s = await fetch("/api/session", { credentials: "include" });
        if (!s.ok) throw new Error("Not authenticated");
        const sj: SessionInfo = await s.json();
        if (sj.user_type !== "rec") throw new Error("Forbidden");
        setSession(sj);
        const res = await fetch("/api/rec_dashboard", { credentials: "include" });
        const json = await res.json();
        if (!json.success) throw new Error(json.message || "Error");
        setKpis(json.kpis);
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
      <h3>Receptionist Dashboard</h3>
      {kpis && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
          <div>Total: {kpis.total_walkin_count}</div>
          <div>Pending: {kpis.pending_leads_count}</div>
          <div>Won: {kpis.won_leads_count}</div>
          <div>Lost: {kpis.lost_leads_count}</div>
          <div>Today: {kpis.today_leads_count}</div>
          <div>FCR: {kpis.first_call_response_rate}%</div>
          <div>CR: {kpis.conversion_rate}%</div>
        </div>
      )}
      <ul>
        {leads.map((l, i) => (
          <li key={i}>{l.customer_name} ({l.mobile_number}) — {l.status}</li>
        ))}
      </ul>
    </div>
  );
}


