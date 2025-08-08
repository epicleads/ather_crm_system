"use client";
import { useEffect, useState } from "react";

type SessionInfo = { authenticated: boolean; user_type: string };
type Duplicate = { uid: string; customer_name?: string; customer_mobile_number?: string };

export default function DuplicatesPage() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rows, setRows] = useState<Duplicate[]>([]);

  useEffect(() => {
    const run = async () => {
      try {
        const s = await fetch("/api/session", { credentials: "include" });
        if (!s.ok) throw new Error("Not authenticated");
        const sj: SessionInfo = await s.json();
        if (sj.user_type !== "admin") throw new Error("Forbidden");
        setSession(sj);
        const res = await fetch("/api/hot_duplicate_leads", { credentials: "include" });
        const json = await res.json();
        if (!json.success) throw new Error(json.message || "Error");
        setRows(json.hot_leads || []);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Error");
      }
    };
    run();
  }, []);

  async function deleteDuplicate(uid: string) {
    try {
      const res = await fetch("/delete_duplicate_lead", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ uid }),
      });
      const json = await res.json();
      if (!json.success) throw new Error(json.message || "Failed");
      setRows((r) => r.filter((x) => x.uid !== uid));
    } catch (e) {
      alert(e instanceof Error ? e.message : "Error");
    }
  }

  if (error) return <div>{error}</div>;
  if (!session) return <div>Loading...</div>;
  return (
    <div>
      <h3>Duplicate Leads</h3>
      <ul>
        {rows.map((d) => (
          <li key={d.uid}>
            {d.customer_name || d.customer_mobile_number || d.uid}
            <button style={{ marginLeft: 8 }} onClick={() => deleteDuplicate(d.uid)}>Delete</button>
          </li>
        ))}
      </ul>
    </div>
  );
}


