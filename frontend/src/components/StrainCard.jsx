import { Link } from "react-router-dom";
import TerpeneRadar from "../charts/TerpeneRadar";
import EffectBars from "../charts/EffectBars";
import TypeBadge from "./TypeBadge";

/**
 * Card component for strain search results.
 *
 * Props:
 *   strain        — {name, strain_type, compositions, top_effects}
 *   score         — number 0-1 (match score, optional)
 *   onCompare     — (strainName) => void (optional)
 *   style         — optional inline styles
 *   animationDelay — CSS delay string for stagger
 */
export default function StrainCard({
  strain,
  score,
  onCompare,
  style,
  animationDelay,
}) {
  // Extract terpene data for mini radar
  const terpenes = (strain.compositions || [])
    .filter((c) => c.type === "terpene" && c.percentage > 0)
    .sort((a, b) => b.percentage - a.percentage)
    .map((c) => ({ name: c.molecule, percentage: c.percentage }));

  return (
    <div
      className="card animate-fade-in-up"
      style={{
        display: "flex",
        gap: 16,
        padding: 16,
        animationDelay: animationDelay || "0ms",
        ...style,
      }}
    >
      {/* Left: Mini radar */}
      <div style={{ flexShrink: 0 }}>
        <TerpeneRadar
          data={terpenes}
          size={80}
          showLabels={false}
          showTooltips={false}
        />
      </div>

      {/* Right: Info */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8, minWidth: 0 }}>
        {/* Header row */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <Link
            to={`/strain/${encodeURIComponent(strain.name)}`}
            className="font-display"
            style={{
              color: "var(--cream)",
              fontSize: "16px",
              textDecoration: "none",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {strain.name}
          </Link>
          <TypeBadge type={strain.strain_type} />

          {score != null && (
            <span
              className="font-data"
              style={{
                marginLeft: "auto",
                color: "var(--gold)",
                fontSize: "18px",
                fontWeight: 600,
              }}
            >
              {Math.round(score * 100)}%
            </span>
          )}
        </div>

        {/* Effect bars (compact) */}
        {strain.top_effects && strain.top_effects.length > 0 && (
          <EffectBars effects={strain.top_effects} compact showThreshold={false} />
        )}

        {/* Actions */}
        <div style={{ display: "flex", gap: 8, marginTop: "auto" }}>
          {onCompare && (
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                onCompare(strain.name);
              }}
              style={{
                padding: "4px 12px",
                border: "1px solid var(--border)",
                borderRadius: "4px",
                background: "transparent",
                color: "var(--cream-dim)",
                fontSize: "12px",
                fontFamily: "var(--font-body)",
                cursor: "pointer",
                transition: "all 150ms",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "var(--gold-dim)";
                e.currentTarget.style.color = "var(--cream)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "var(--border)";
                e.currentTarget.style.color = "var(--cream-dim)";
              }}
            >
              Compare
            </button>
          )}
          <Link
            to={`/strain/${encodeURIComponent(strain.name)}`}
            style={{
              padding: "4px 12px",
              border: "1px solid var(--gold-dim)",
              borderRadius: "4px",
              color: "var(--gold)",
              fontSize: "12px",
              fontFamily: "var(--font-body)",
              textDecoration: "none",
              transition: "all 150ms",
            }}
          >
            Details →
          </Link>
        </div>
      </div>
    </div>
  );
}
