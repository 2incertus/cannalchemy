import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchStrain, fetchStrains, fetchExplanation } from "../lib/api";
import TerpeneRadar from "../charts/TerpeneRadar";
import EffectBars from "../charts/EffectBars";
import PathwayDiagram from "../charts/PathwayDiagram";
import TypeBadge from "../components/TypeBadge";
import StrainCard from "../components/StrainCard";

export default function StrainDetail() {
  const { name } = useParams();
  const [strain, setStrain] = useState(null);
  const [similar, setSimilar] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [explanation, setExplanation] = useState(null);
  const [explanationLoading, setExplanationLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchStrain(name)
      .then((data) => {
        setStrain(data);
        // Fetch explanation async (non-blocking)
        setExplanationLoading(true);
        fetchExplanation(name)
          .then((expData) => setExplanation(expData))
          .catch(() => setExplanation(null))
          .finally(() => setExplanationLoading(false));
        // Fetch similar strains of same type
        return fetchStrains("", data.strain_type, 6);
      })
      .then((data) => {
        // Filter out the current strain
        setSimilar(
          (data.strains || [])
            .filter((s) => s.name !== name)
            .slice(0, 5)
            .map((s) => ({ ...s, score: null, top_effects: [] }))
        );
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [name]);

  if (loading) {
    return (
      <div className="page" style={{ maxWidth: 1000, margin: "0 auto", padding: "80px 24px" }}>
        <div className="skeleton" style={{ height: 40, width: 300, marginBottom: 24 }} />
        <div className="detail-grid">
          <div className="skeleton" style={{ height: 350 }} />
          <div className="skeleton" style={{ height: 350 }} />
        </div>
        <div className="skeleton" style={{ height: 400, marginTop: 24 }} />
      </div>
    );
  }

  if (error || !strain) {
    return (
      <div className="page" style={{ maxWidth: 1000, margin: "0 auto", padding: "80px 24px", textAlign: "center" }}>
        <h2 className="font-display" style={{ color: "var(--red)", marginBottom: 16 }}>
          Strain Not Found
        </h2>
        <p style={{ color: "var(--cream-dim)", marginBottom: 24 }}>
          {error || `Could not find strain "${name}".`}
        </p>
        <Link to="/explore" className="btn-gold" style={{ textDecoration: "none" }}>
          ← Back to Explorer
        </Link>
      </div>
    );
  }

  // Terpene data for radar
  const terpenes = (strain.compositions || [])
    .filter((c) => c.type === "terpene" && c.percentage > 0)
    .sort((a, b) => b.percentage - a.percentage)
    .map((c) => ({ name: c.molecule, percentage: c.percentage }));

  // Cannabinoid data
  const cannabinoids = (strain.compositions || [])
    .filter((c) => c.type === "cannabinoid" && c.percentage > 0)
    .sort((a, b) => b.percentage - a.percentage);

  // Effects for bars
  const effectsList = (strain.predicted_effects || []).map((e) => ({
    ...e,
    predicted: e.probability >= 0.5,
  }));

  // Pathways
  const pathways = strain.pathways || [];
  const predictedEffectNames = effectsList
    .filter((e) => e.predicted)
    .map((e) => e.name);

  return (
    <div className="page" style={{ maxWidth: 1000, margin: "0 auto", padding: "80px 24px 48px" }}>
      {/* Back link */}
      <Link
        to="/explore"
        style={{ color: "var(--cream-faint)", fontSize: "13px", textDecoration: "none", marginBottom: 16, display: "inline-block" }}
      >
        ← Back to Explorer
      </Link>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 32, flexWrap: "wrap" }}>
        <h1
          className="font-display"
          style={{ fontSize: "2.2rem", color: "var(--cream)", letterSpacing: "0.03em" }}
        >
          {strain.name}
        </h1>
        <TypeBadge type={strain.strain_type} />
      </div>

      {/* Two-column grid: Radar + Cannabinoids | Effects */}
      <div className="detail-grid">
        {/* Left: Terpene Radar + Cannabinoid bars */}
        <div className="card" style={{ padding: 24 }}>
          <h2
            className="font-display"
            style={{ fontSize: "1.1rem", color: "var(--cream)", marginBottom: 16 }}
          >
            Terpene Profile
          </h2>
          <div style={{ display: "flex", justifyContent: "center" }}>
            <TerpeneRadar data={terpenes} size={300} />
          </div>

          {/* Cannabinoid bars */}
          {cannabinoids.length > 0 && (
            <div style={{ marginTop: 24 }}>
              <h3
                style={{
                  fontSize: "12px",
                  color: "var(--cream-dim)",
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                  marginBottom: 12,
                }}
              >
                Cannabinoids
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {cannabinoids.map((c) => (
                  <div key={c.molecule} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                      style={{
                        width: 50,
                        fontSize: "12px",
                        color: "var(--cream)",
                        fontFamily: "var(--font-data)",
                        textTransform: "uppercase",
                      }}
                    >
                      {c.molecule}
                    </span>
                    <div
                      style={{
                        flex: 1,
                        height: 8,
                        background: "var(--bg-elevated)",
                        borderRadius: "4px",
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          height: "100%",
                          width: `${Math.min(c.percentage / 30 * 100, 100)}%`,
                          background: "linear-gradient(90deg, var(--green), var(--green-bright))",
                          borderRadius: "4px",
                        }}
                      />
                    </div>
                    <span
                      className="font-data"
                      style={{ width: 48, textAlign: "right", fontSize: "12px", color: "var(--cream-dim)" }}
                    >
                      {c.percentage.toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: Effect predictions */}
        <div className="card" style={{ padding: 24 }}>
          <h2
            className="font-display"
            style={{ fontSize: "1.1rem", color: "var(--cream)", marginBottom: 16 }}
          >
            Predicted Effects
          </h2>
          <EffectBars effects={effectsList} />
        </div>
      </div>

      {/* Pathway diagram (full width) */}
      <div className="card" style={{ padding: 24, marginBottom: 32 }}>
        <h2
          className="font-display"
          style={{ fontSize: "1.1rem", color: "var(--cream)", marginBottom: 16 }}
        >
          Molecular Pathways
        </h2>
        <p style={{ color: "var(--cream-dim)", fontSize: "13px", marginBottom: 16 }}>
          How this strain&apos;s molecules interact with receptors to produce effects. Drag nodes to rearrange. Scroll to zoom.
        </p>
        <PathwayDiagram pathways={pathways} effects={predictedEffectNames} height={400} />
      </div>

      {/* AI Analysis */}
      {(explanationLoading || (explanation && explanation.explanation)) && (
        <div className="card animate-fade-in-up" style={{ padding: 24, marginBottom: 32 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
            <h2
              className="font-display"
              style={{ fontSize: "1.1rem", color: "var(--cream)", margin: 0 }}
            >
              AI Analysis
            </h2>
            {explanation?.provider && (
              <span
                className="font-data"
                style={{
                  fontSize: "10px",
                  color: "var(--cream-faint)",
                  border: "1px solid var(--border)",
                  borderRadius: 4,
                  padding: "2px 6px",
                }}
              >
                {explanation.provider.toUpperCase()}
              </span>
            )}
          </div>
          {explanationLoading ? (
            <div className="skeleton" style={{ height: 60, borderRadius: 4 }} />
          ) : (
            <p style={{ color: "var(--cream-dim)", fontSize: "14px", lineHeight: 1.7, margin: 0 }}>
              {explanation.explanation}
            </p>
          )}
        </div>
      )}

      {/* Similar strains */}
      {similar.length > 0 && (
        <section>
          <h2
            className="font-display"
            style={{ fontSize: "1.1rem", color: "var(--cream)", marginBottom: 16 }}
          >
            Similar {strain.strain_type} Strains
          </h2>
          <div
            style={{
              display: "flex",
              gap: 16,
              overflowX: "auto",
              paddingBottom: 8,
            }}
          >
            {similar.map((s, i) => (
              <div key={s.name} style={{ minWidth: 340, flexShrink: 0 }}>
                <StrainCard strain={s} animationDelay={`${i * 80}ms`} />
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
