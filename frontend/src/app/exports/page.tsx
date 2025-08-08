"use client";
import { useEffect, useState } from "react";

type SessionInfo = { authenticated: boolean; user_type: string };

export default function ExportsPage() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  function download(path: string) {
    const base = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:5000";
    window.location.href = `${base}${path}`;
  }

  if (error) return <div>{error}</div>;
  if (!session) return <div>Loading...</div>;
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <h3>Exports</h3>
      <button onClick={() => download("/export_all_cre_leads")}>Export All CRE Leads</button>
      <button onClick={() => download("/export_filtered_leads")}>Export Filtered Leads (use query params)</button>
      <button onClick={() => download("/export_leads_csv")}>Export Leads CSV</button>
      <button onClick={() => download("/export_test_drive_csv")}>Export Test Drive CSV</button>
      <button onClick={() => download("/export_leads_by_date_csv")}>Export Leads By Date CSV</button>
    </div>
  );
}



