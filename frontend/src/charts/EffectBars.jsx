import { useState } from "react";

const CATEGORY_COLORS = {
  positive: "var(--gold)",
  negative: "var(--red)",
  medical: "var(--blue)",
  unknown: "var(--cream-dim)",
};

const CATEGORY_ORDER = { positive: 0, medical: 1, negative: 2, unknown: 3 };

const CONFIDENCE_STYLES = {
  high: { label: "H", color: "var(--green, #6b9e6b)", title: "High confidence (AUC ≥ 0.85)" },
  medium: { label: "M", color: "var(--gold-dim)", title: "Medium confidence (AUC 0.75–0.85)" },
  low: { label: "L", color: "var(--cream-faint)", title: "Low confidence (AUC < 0.75)" },
};

/**
 * EffectBars — horizontal bar chart for predicted effect probabilities.
 *
 * Props:
 *   effects  — [{name, category, probability, predicted}]
 *   compact  — boolean (top 5 only, no hover expand)
 *   showThreshold — boolean (50% dashed line)
 */
export default function EffectBars({
  effects = [],
  compact = false,
  showThreshold = true,
}) {
  const [expanded, setExpanded] = useState(null);

  // Sort: by category group, then by probability desc within group
  const sorted = [...effects].sort((a, b) => {
    const catDiff =
      (CATEGORY_ORDER[a.category] ?? 3) - (CATEGORY_ORDER[b.category] ?? 3);
    if (catDiff !== 0) return catDiff;
    return b.probability - a.probability;
  });

  const displayed = compact ? sorted.filter((e) => e.probability >= 0.2).slice(0, 5) : sorted;

  if (!displayed.length) {
    return (
      <div
        style={{
          color: "var(--cream-faint)",
          fontSize: "12px",
          fontFamily: "var(--font-data)",
          padding: "16px 0",
        }}
      >
        No effect predictions
      </div>
    );
  }

  return (
    <div style={{ position: "relative" }}>
      {/* Threshold line */}
      {showThreshold && !compact && (
        <div
          style={{
            position: "absolute",
            left: "50%",
            top: 0,
            bottom: 0,
            width: "1px",
            borderLeft: "1px dashed var(--cream-faint)",
            zIndex: 1,
            pointerEvents: "none",
            marginLeft: "calc(40% * 0.5)", // offset for label column
          }}
        />
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: compact ? 4 : 6 }}>
        {displayed.map((effect) => {
          const color = CATEGORY_COLORS[effect.category] || CATEGORY_COLORS.unknown;
          const pct = Math.round(effect.probability * 100);
          const isExpanded = expanded === effect.name && !compact;

          return (
            <div
              key={effect.name}
              role={compact ? undefined : "button"}
              tabIndex={compact ? undefined : 0}
              onClick={() => !compact && setExpanded(isExpanded ? null : effect.name)}
              onKeyDown={(e) => {
                if (!compact && (e.key === "Enter" || e.key === " ")) {
                  e.preventDefault();
                  setExpanded(isExpanded ? null : effect.name);
                }
              }}
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 2,
                cursor: compact ? "default" : "pointer",
                padding: compact ? "2px 0" : "4px 0",
                borderRadius: "4px",
                transition: "background-color 150ms",
              }}
            >
              {/* Main row */}
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                {/* Category dot */}
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: color,
                    flexShrink: 0,
                  }}
                />

                {/* Effect name */}
                <span
                  style={{
                    width: compact ? 80 : 120,
                    flexShrink: 0,
                    fontSize: compact ? "11px" : "13px",
                    color: "var(--cream)",
                    fontFamily: "var(--font-body)",
                    textTransform: "capitalize",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {effect.name}
                </span>

                {/* Bar */}
                <div
                  style={{
                    flex: 1,
                    height: compact ? 6 : 10,
                    background: "var(--bg-elevated)",
                    borderRadius: "3px",
                    overflow: "hidden",
                    position: "relative",
                  }}
                >
                  <div
                    style={{
                      height: "100%",
                      width: `${pct}%`,
                      background: `linear-gradient(90deg, ${
                        effect.category === "negative"
                          ? "var(--red)"
                          : effect.category === "medical"
                          ? "var(--blue)"
                          : "var(--gold-dim)"
                      }, ${color})`,
                      borderRadius: "3px",
                      transition: "width 400ms ease-out",
                    }}
                  />
                </div>

                {/* Percentage */}
                <span
                  style={{
                    width: 36,
                    textAlign: "right",
                    flexShrink: 0,
                    fontSize: compact ? "10px" : "12px",
                    fontFamily: "var(--font-data)",
                    color: pct >= 50 ? color : "var(--cream-dim)",
                  }}
                >
                  {pct}%
                </span>

                {/* Confidence badge */}
                {!compact && effect.confidence && (() => {
                  const conf = CONFIDENCE_STYLES[effect.confidence] || CONFIDENCE_STYLES.medium;
                  return (
                    <span
                      title={conf.title}
                      style={{
                        width: 16,
                        height: 16,
                        borderRadius: "50%",
                        border: `1px solid ${conf.color}`,
                        display: "inline-flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: "8px",
                        fontFamily: "var(--font-data)",
                        color: conf.color,
                        flexShrink: 0,
                      }}
                    >
                      {conf.label}
                    </span>
                  );
                })()}
              </div>

              {/* Expanded detail (non-compact only) */}
              {isExpanded && (
                <div
                  style={{
                    marginLeft: 14,
                    padding: "6px 12px",
                    fontSize: "11px",
                    color: "var(--cream-dim)",
                    fontFamily: "var(--font-body)",
                    borderLeft: `2px solid ${color}`,
                    lineHeight: 1.5,
                  }}
                >
                  <span style={{ textTransform: "capitalize", fontWeight: 500 }}>
                    {effect.category}
                  </span>{" "}
                  effect
                  {effect.predicted && (
                    <span style={{ color, marginLeft: 8 }}>
                      ● Predicted
                    </span>
                  )}
                  {effect.confidence && (
                    <span style={{
                      marginLeft: 8,
                      color: (CONFIDENCE_STYLES[effect.confidence] || CONFIDENCE_STYLES.medium).color,
                    }}>
                      ● {effect.confidence === "high" ? "High" : effect.confidence === "medium" ? "Medium" : "Low"} model confidence
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
