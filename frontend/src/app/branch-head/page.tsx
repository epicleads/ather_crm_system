"use client";
import { useEffect, useState } from "react";

type SessionInfo = { authenticated: boolean; user_type: string; username?: string; branch?: string };
type BranchData = Record<string, unknown>;

export default function BranchHeadPage() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<BranchData | null>(null);

  useEffect(() => {
    const run = async () => {
      try {
        const s = await fetch("/api/session", { credentials: "include" });
        if (!s.ok) throw new Error("Not authenticated");
        const sj: SessionInfo = await s.json();
        if (sj.user_type !== "branch_head") throw new Error("Forbidden");
        setSession(sj);
        const res = await fetch("/api/branch_head_dashboard_data", { credentials: "include" });
        const json = await res.json();
        setData(json);
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
      <h3>Branch Head Dashboard</h3>
      <div>Branch: {session.branch || "-"}</div>
      <pre style={{ background: "#f6f6f6", padding: 8 }}>{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
}


