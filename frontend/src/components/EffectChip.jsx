const STYLES = {
  positive: {
    selected: { bg: "rgba(212,168,67,0.15)", border: "var(--gold)", color: "var(--gold)" },
    idle: {},
  },
  negative: {
    selected: { bg: "rgba(196,92,74,0.15)", border: "var(--red)", color: "var(--red)" },
    idle: {},
  },
  medical: {
    selected: { bg: "rgba(74,124,182,0.15)", border: "var(--blue)", color: "var(--blue)" },
    idle: {},
  },
};

/**
 * Selectable pill button for choosing desired effects.
 *
 * Props:
 *   name      — effect name
 *   category  — "positive" | "negative" | "medical"
 *   selected  — boolean
 *   onToggle  — () => void
 */
export default function EffectChip({ name, category = "positive", selected, onToggle }) {
  const catStyle = STYLES[category] || STYLES.positive;
  const active = selected ? catStyle.selected : catStyle.idle;

  return (
    <button
      onClick={onToggle}
      type="button"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "6px 14px",
        borderRadius: "20px",
        border: `1px solid ${active.border || "var(--border)"}`,
        background: active.bg || "var(--bg-card)",
        color: active.color || "var(--cream-dim)",
        fontFamily: "var(--font-body)",
        fontSize: "13px",
        cursor: "pointer",
        transition: "all 200ms ease-out",
        transform: selected ? "scale(1.03)" : "scale(1)",
        textTransform: "capitalize",
        whiteSpace: "nowrap",
      }}
      onMouseEnter={(e) => {
        if (!selected) {
          e.currentTarget.style.background = "var(--bg-elevated)";
          e.currentTarget.style.borderColor = "var(--gold-dim)";
        }
      }}
      onMouseLeave={(e) => {
        if (!selected) {
          e.currentTarget.style.background = active.bg || "var(--bg-card)";
          e.currentTarget.style.borderColor = active.border || "var(--border)";
        }
      }}
    >
      {name}
    </button>
  );
}
