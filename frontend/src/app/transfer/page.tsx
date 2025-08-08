"use client";
import { useEffect, useState } from "react";

type SessionInfo = { authenticated: boolean; user_type: string };
type CreOption = { name: string; username: string };

export default function TransferPage() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creOptions, setCreOptions] = useState<CreOption[]>([]);
  const [leadUid, setLeadUid] = useState("");
  const [toCre, setToCre] = useState("");

  useEffect(() => {
    const run = async () => {
      try {
        const s = await fetch("/api/session", { credentials: "include" });
        if (!s.ok) throw new Error("Not authenticated");
        const sj: SessionInfo = await s.json();
        if (sj.user_type !== "admin") throw new Error("Forbidden");
        setSession(sj);
        const optsRes = await fetch("/api/transfer_options", { credentials: "include" });
        const opts = await optsRes.json();
        setCreOptions(opts.cre_options || []);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Error");
      }
    };
    run();
  }, []);

  async function transfer() {
    try {
      const res = await fetch("/api/transfer_cre_lead", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ lead_uid: leadUid, new_cre_name: toCre }),
      });
      const json = await res.json();
      if (!json.success) throw new Error(json.message || "Failed");
      alert("Transferred");
    } catch (e) {
      alert(e instanceof Error ? e.message : "Error");
    }
  }

  if (error) return <div>{error}</div>;
  if (!session) return <div>Loading...</div>;
  return (
    <div style={{ display: "grid", gap: 8, maxWidth: 500 }}>
      <h3>Transfer Lead (CRE)</h3>
      <input placeholder="Lead UID" value={leadUid} onChange={(e) => setLeadUid(e.target.value)} />
      <select value={toCre} onChange={(e) => setToCre(e.target.value)}>
        <option value="">Select target CRE (username)</option>
        {creOptions.map((c) => (
          <option key={c.username} value={c.username}>
            {c.name} ({c.username})
          </option>
        ))}
      </select>
      <button onClick={transfer} disabled={!leadUid || !toCre}>Transfer</button>
    </div>
  );
}


