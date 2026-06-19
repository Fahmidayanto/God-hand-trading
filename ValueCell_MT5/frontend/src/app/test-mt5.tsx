import { useEffect, useState } from "react";

export default function TestMT5Dashboard() {
  const [health, setHealth] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Test health check
    fetch("http://localhost:8000/api/v1/health")
      .then((r) => r.json())
      .then((data) => {
        console.log("Health:", data);
        setHealth(data);
      })
      .catch((err) => {
        console.error("Health error:", err);
        setError(err.message);
      });

    // Test dashboard stats
    fetch("http://localhost:8000/api/v1/dashboard/stats")
      .then((r) => r.json())
      .then((data) => {
        console.log("Stats:", data);
        setStats(data);
      })
      .catch((err) => {
        console.error("Stats error:", err);
        setError(err.message);
      });
  }, []);

  return (
    <div style={{ padding: "20px", fontFamily: "Arial" }}>
      <h1>🧪 Test MT5 Dashboard</h1>

      {error && (
        <div style={{ padding: "10px", background: "#ffebee", color: "#c62828", marginBottom: "20px" }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      <div style={{ marginBottom: "20px" }}>
        <h2>🔍 Backend Health Check</h2>
        {health ? (
          <pre style={{ background: "#f5f5f5", padding: "10px", borderRadius: "4px" }}>
            {JSON.stringify(health, null, 2)}
          </pre>
        ) : (
          <p>Loading...</p>
        )}
      </div>

      <div style={{ marginBottom: "20px" }}>
        <h2>📊 Dashboard Stats</h2>
        {stats ? (
          <div>
            <pre style={{ background: "#f5f5f5", padding: "10px", borderRadius: "4px" }}>
              {JSON.stringify(stats, null, 2)}
            </pre>
            <div style={{ marginTop: "20px" }}>
              <h3>Formatted Stats:</h3>
              <ul>
                <li>💰 <strong>Balance:</strong> ${stats.balance?.toFixed(2) || "N/A"}</li>
                <li>💵 <strong>Equity:</strong> ${stats.equity?.toFixed(2) || "N/A"}</li>
                <li>📈 <strong>Profit:</strong> ${stats.profit?.toFixed(2) || "N/A"}</li>
                <li>📍 <strong>Open Positions:</strong> {stats.open_positions || 0}</li>
              </ul>
            </div>
          </div>
        ) : (
          <p>Loading...</p>
        )}
      </div>

      <div style={{ marginTop: "40px", padding: "10px", background: "#e3f2fd", borderRadius: "4px" }}>
        <p><strong>✅ If you see data above, the integration is working!</strong></p>
        <p>Next step: Visit <a href="/mt5">/mt5</a> for the full dashboard</p>
      </div>
    </div>
  );
}
