"use client";
import { useEffect, useState } from "react";

type SessionInfo = { authenticated: boolean; user_type: string };
type PsUser = { id?: number; name?: string; username?: string; branch?: string; is_active?: boolean };

export default function ManagePsPage() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [data, setData] = useState<PsUser[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const run = async () => {
      try {
        const s = await fetch("/api/session", { credentials: "include" });
        if (!s.ok) throw new Error("Not authenticated");
        const sj: SessionInfo = await s.json();
        if (sj.user_type !== "admin") throw new Error("Forbidden");
        setSession(sj);
        const res = await fetch("/api/ps_users", { credentials: "include" });
        const json = await res.json();
        if (!json.success) throw new Error(json.message || "Error");
        setData(json.ps_users || []);
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
      <h3>Manage PS</h3>
      <ul>
        {data.map((u) => (
          <li key={u.id}>
            {u.name} ({u.username}) — {u.branch} — {u.is_active ? "Active" : "Inactive"}
          </li>
        ))}
      </ul>
    </div>
  );
}



