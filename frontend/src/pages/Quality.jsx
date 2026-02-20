import { useState, useEffect } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { fetchStats } from "../lib/api";

const CATEGORY_COLORS = {
  positive: "#D4A843",
  negative: "#C45C4A",
  medical: "#4A7CB6",
  unknown: "#A09482",
};

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: "var(--bg-void)",
        border: "1px solid var(--border)",
        borderRadius: "6px",
        padding: "8px 12px",
        fontSize: "12px",
      }}
    >
      <div style={{ color: "var(--cream)", marginBottom: 2 }}>{label}</div>
      {payload.map((p) => (
        <div key={p.name} style={{ color: p.color || "var(--gold)" }}>
          {p.name}: {typeof p.value === "number" ? p.value.toLocaleString() : p.value}
        </div>
      ))}
    </div>
  );
};

export default function Quality() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats()
      .then(setStats)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="page" style={{ maxWidth: 1000, margin: "0 auto", padding: "80px 24px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 16, marginBottom: 32 }}>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="skeleton" style={{ height: 100, borderRadius: 8 }} />
          ))}
        </div>
        <div className="skeleton" style={{ height: 300, marginBottom: 24 }} />
        <div className="skeleton" style={{ height: 300 }} />
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="page flex items-center justify-center">
        <p style={{ color: "var(--cream-faint)" }}>Failed to load statistics</p>
      </div>
    );
  }

  const statCards = [
    { label: "Total Strains", value: stats.total_strains },
    { label: "ML-Ready", value: stats.ml_ready_strains },
    { label: "Molecules", value: stats.molecules },
    { label: "Effects", value: stats.effects },
    { label: "Receptors", value: stats.receptors },
  ];

  const sourceData = (stats.sources || []).map((s) => ({
    name: s.source,
    count: s.count,
  }));

  const modelData = (stats.model_performance || [])
    .sort((a, b) => b.auc - a.auc)
    .slice(0, 20);

  const effectCounts = (stats.effect_counts || [])
    .sort((a, b) => b.total_reports - a.total_reports)
    .slice(0, 25);

  return (
    <div className="page" style={{ maxWidth: 1000, margin: "0 auto", padding: "80px 24px 48px" }}>
      <h1
        className="font-display"
        style={{ fontSize: "2rem", color: "var(--gold)", marginBottom: 32, letterSpacing: "0.05em" }}
      >
        Data Quality
      </h1>

      {/* Stat cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
          gap: 16,
          marginBottom: 40,
        }}
      >
        {statCards.map((s) => (
          <div key={s.label} className="card" style={{ padding: "20px 16px", textAlign: "center" }}>
            <div
              className="font-data"
              style={{ fontSize: "1.8rem", color: "var(--gold)", fontWeight: 600 }}
            >
              {(s.value || 0).toLocaleString()}
            </div>
            <div style={{ fontSize: "12px", color: "var(--cream-dim)", marginTop: 4 }}>
              {s.label}
            </div>
          </div>
        ))}
      </div>

      {/* Model Performance */}
      {modelData.length > 0 && (
        <section className="card" style={{ padding: 24, marginBottom: 24 }}>
          <h2 className="font-display" style={{ fontSize: "1.1rem", color: "var(--cream)", marginBottom: 16 }}>
            Model Performance (ROC AUC)
          </h2>
          <ResponsiveContainer width="100%" height={Math.max(modelData.length * 28, 200)}>
            <BarChart data={modelData} layout="vertical" margin={{ left: 100, right: 20 }}>
              <XAxis type="number" domain={[0, 1]} tick={{ fill: "#A09482", fontSize: 11 }} />
              <YAxis
                dataKey="name"
                type="category"
                tick={{ fill: "#E8DCC8", fontSize: 11, fontFamily: "var(--font-body)" }}
                width={100}
              />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="auc" radius={[0, 3, 3, 0]}>
                {modelData.map((entry) => (
                  <Cell
                    key={entry.name}
                    fill={CATEGORY_COLORS[entry.category] || CATEGORY_COLORS.unknown}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </section>
      )}

      {/* Effect Report Counts */}
      {effectCounts.length > 0 && (
        <section className="card" style={{ padding: 24, marginBottom: 24 }}>
          <h2 className="font-display" style={{ fontSize: "1.1rem", color: "var(--cream)", marginBottom: 16 }}>
            Effect Report Distribution
          </h2>
          <ResponsiveContainer width="100%" height={Math.max(effectCounts.length * 28, 200)}>
            <BarChart data={effectCounts} layout="vertical" margin={{ left: 100, right: 20 }}>
              <XAxis type="number" tick={{ fill: "#A09482", fontSize: 11 }} />
              <YAxis
                dataKey="name"
                type="category"
                tick={{ fill: "#E8DCC8", fontSize: 11, fontFamily: "var(--font-body)" }}
                width={100}
              />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="total_reports" name="Reports" radius={[0, 3, 3, 0]}>
                {effectCounts.map((entry) => (
                  <Cell
                    key={entry.name}
                    fill={CATEGORY_COLORS[entry.category] || CATEGORY_COLORS.unknown}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </section>
      )}

      {/* Source Breakdown */}
      {sourceData.length > 0 && (
        <section className="card" style={{ padding: 24 }}>
          <h2 className="font-display" style={{ fontSize: "1.1rem", color: "var(--cream)", marginBottom: 16 }}>
            Data Sources
          </h2>
          <ResponsiveContainer width="100%" height={Math.max(sourceData.length * 40, 150)}>
            <BarChart data={sourceData} layout="vertical" margin={{ left: 80, right: 20 }}>
              <XAxis type="number" tick={{ fill: "#A09482", fontSize: 11 }} />
              <YAxis
                dataKey="name"
                type="category"
                tick={{ fill: "#E8DCC8", fontSize: 11 }}
                width={80}
              />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="count" fill="#5C8A4D" radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </section>
      )}
    </div>
  );
}
