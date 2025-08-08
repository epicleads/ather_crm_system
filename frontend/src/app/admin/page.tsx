"use client";
import { useEffect, useState } from "react";

type SessionInfo = {
  authenticated: boolean;
  user_type: string;
  username?: string;
  branch?: string;
};
type AdminSummary = {
  success: boolean;
  cre_count: number;
  ps_count: number;
  leads_count: number;
  unassigned_leads: number;
};

export default function AdminPage() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<AdminSummary | null>(null);

  useEffect(() => {
    const run = async () => {
      try {
        const res = await fetch("/api/session", { credentials: "include" });
        if (!res.ok) throw new Error("Not authenticated");
        const json: SessionInfo = await res.json();
        if (json.user_type !== "admin") throw new Error("Forbidden");
        setSession(json);
        const sumRes = await fetch("/api/admin_dashboard_summary", { credentials: "include" });
        if (sumRes.ok) setSummary((await sumRes.json()) as AdminSummary);
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
      <h3>Admin Dashboard (Next.js)</h3>
      <div>User: {session.username}</div>
      <div>Branch: {session.branch || "-"}</div>
      {summary && (
        <div style={{ marginTop: 16 }}>
          <div>CREs: {summary.cre_count}</div>
          <div>PSs: {summary.ps_count}</div>
          <div>Total Leads: {summary.leads_count}</div>
          <div>Unassigned: {summary.unassigned_leads}</div>
        </div>
      )}
    </div>
  );
}


