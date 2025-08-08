"use client";
import { useState } from "react";

export default function Home() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [userType, setUserType] = useState("admin");
  const [message, setMessage] = useState<string | null>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage(null);
    try {
      const res = await fetch(
        "/unified_login_json",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ username, password, user_type: userType }),
        }
      );
      if (!res.ok) throw new Error(`Login failed (${res.status})`);
      const data = (await res.json()) as { success?: boolean; redirect?: string };
      if (data?.redirect) {
        const mapping: Record<string, string> = {
          '/admin_dashboard': '/admin',
          '/cre_dashboard': '/cre',
          '/ps_dashboard': '/ps',
          '/add_walkin_lead': '/walkin/add',
          '/rec_dashboard': '/rec',
          '/branch_head_dashboard': '/branch-head',
        };
        const nextPath = mapping[data.redirect] || '/';
        window.location.href = nextPath;
        return;
      }
      setMessage("Logged in successfully. Session cookie stored.");
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Login failed";
      setMessage(errorMessage);
    }
  };

  return (
    <div style={{ maxWidth: 400, margin: "80px auto", fontFamily: "system-ui, sans-serif" }}>
      <h2 style={{ marginBottom: 16 }}>Ather CRM Login</h2>
      <form onSubmit={handleLogin} style={{ display: "grid", gap: 12 }}>
        <label>
          <div>Username</div>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            style={{ width: "100%", padding: 8, border: "1px solid #ccc", borderRadius: 6 }}
          />
        </label>
        <label>
          <div>Password</div>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            style={{ width: "100%", padding: 8, border: "1px solid #ccc", borderRadius: 6 }}
          />
        </label>
        <label>
          <div>Role</div>
          <select
            value={userType}
            onChange={(e) => setUserType(e.target.value)}
            style={{ width: "100%", padding: 8, border: "1px solid #ccc", borderRadius: 6 }}
          >
            <option value="admin">Admin</option>
            <option value="cre">CRE</option>
            <option value="ps">PS</option>
            <option value="branch_head">Branch Head</option>
            <option value="rec">Receptionist</option>
          </select>
        </label>
        <button
          type="submit"
          style={{ padding: 10, borderRadius: 6, background: "#111", color: "#fff", border: 0 }}
        >
          Login
        </button>
        {message && (
          <div style={{ color: "#444", background: "#f6f6f6", padding: 8, borderRadius: 6 }}>{message}</div>
        )}
      </form>
    </div>
  );
}
