"use client";
import { useEffect, useState } from "react";

type SessionInfo = { authenticated: boolean; user_type: string };
type AnalyticsSummary = {
  success: boolean;
  total_leads: number;
  won_leads: number;
  conversion_rate: number;
  // optional richer fields when available
  source_labels?: string[];
  source_data?: number[];
  trend_labels?: string[];
  trend_data?: number[];
};

export default function AnalyticsPage() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const run = async () => {
      try {
        const s = await fetch("/api/session", { credentials: "include" });
        if (!s.ok) throw new Error("Not authenticated");
        const sj: SessionInfo = await s.json();
        if (sj.user_type !== "admin") throw new Error("Forbidden");
        setSession(sj);
        const res = await fetch("/api/analytics?period=30", { credentials: "include" });
        const json = (await res.json()) as AnalyticsSummary;
        if (!json.success) throw new Error("Analytics error");
        setSummary(json);
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
      <h3>Analytics</h3>
      {summary ? (
        <div>
          <div>Total Leads: {summary.total_leads}</div>
          <div>Won Leads: {summary.won_leads}</div>
          <div>Conversion Rate: {summary.conversion_rate}%</div>
          {summary.source_labels && summary.source_data && (
            <div style={{ marginTop: 16 }}>
              <strong>Source Distribution</strong>
              <ul>
                {summary.source_labels.map((l, i) => (
                  <li key={l}>{l}: {summary.source_data?.[i]}</li>
                ))}
              </ul>
            </div>
          )}
          {summary.trend_labels && summary.trend_data && (
            <div style={{ marginTop: 16 }}>
              <strong>Last 30 Days</strong>
              <ul>
                {summary.trend_labels.map((l, i) => (
                  <li key={l}>{l}: {summary.trend_data?.[i]}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : (
        <div>Loading analytics...</div>
      )}
    </div>
  );
}



