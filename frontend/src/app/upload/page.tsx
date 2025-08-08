"use client";
import { useEffect, useState } from "react";

type SessionInfo = { authenticated: boolean; user_type: string };

export default function UploadDataPage() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

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

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    try {
      setSaving(true);
      const res = await fetch("/api/upload_data", {
        method: "POST",
        credentials: "include",
        body: fd,
      });
      const json = await res.json();
      if (!json.success) throw new Error(json.message || "Failed");
      alert(`Uploaded ${json.uploaded} leads`);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Error");
    } finally {
      setSaving(false);
    }
  }

  if (error) return <div>{error}</div>;
  if (!session) return <div>Loading...</div>;
  return (
    <form onSubmit={onSubmit} style={{ display: "grid", gap: 8, maxWidth: 500 }}>
      <h3>Upload Lead Data</h3>
      <select name="source" required>
        <option value="">Select source</option>
        <option value="CRM Upload">CRM Upload</option>
      </select>
      <input name="file" type="file" accept=".csv,.xlsx,.xls" required />
      <button disabled={saving} type="submit">{saving ? "Uploading..." : "Upload"}</button>
    </form>
  );
}



