const TYPE_COLORS = {
  indica: "var(--green)",
  sativa: "var(--gold)",
  hybrid: "var(--cream-dim)",
};

/**
 * Small pill showing strain type (indica / sativa / hybrid).
 */
export default function TypeBadge({ type }) {
  const color = TYPE_COLORS[type] || TYPE_COLORS.hybrid;

  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 10px",
        borderRadius: "12px",
        border: `1px solid ${color}`,
        color,
        fontFamily: "var(--font-data)",
        fontSize: "11px",
        textTransform: "capitalize",
        letterSpacing: "0.03em",
        lineHeight: "1.4",
      }}
    >
      {type || "unknown"}
    </span>
  );
}
