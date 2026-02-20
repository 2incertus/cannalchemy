import { useRef, useEffect } from "react";
import * as d3 from "d3";

const TERPENE_EFFECTS = {
  myrcene: "Sedating, pain relief",
  limonene: "Mood elevation, stress relief",
  caryophyllene: "Anti-inflammatory, pain",
  pinene: "Alertness, memory retention",
  linalool: "Calming, anti-anxiety",
  terpinolene: "Uplifting, energizing",
  humulene: "Appetite suppressant",
  ocimene: "Anti-inflammatory, antiviral",
  bisabolol: "Soothing, anti-irritation",
  terpineol: "Relaxing, sedative",
  camphene: "Antioxidant, cooling",
  fenchol: "Antibacterial",
  borneol: "Analgesic, anti-inflammatory",
  nerolidol: "Sedating, antifungal",
  farnesene: "Calming, anti-inflammatory",
  valencene: "Anti-inflammatory, insect repellent",
  geraniol: "Neuroprotective, antioxidant",
  guaiol: "Anti-inflammatory, antimicrobial",
  phellandrene: "Antifungal, energizing",
  carene: "Anti-inflammatory, bone healing",
  eucalyptol: "Decongestant, anti-inflammatory",
};

/**
 * TerpeneRadar — D3 radar/spider chart for terpene profiles.
 *
 * Props:
 *   data      — [{name, percentage}] sorted by % desc, non-zero only
 *   size      — number (80 mini, 320 full)
 *   showLabels — boolean
 *   showTooltips — boolean
 *   overlayData  — optional second [{name, percentage}] for comparison
 *   overlayColor — CSS variable string (default --green-bright)
 *   className — optional wrapper class
 */
export default function TerpeneRadar({
  data = [],
  size = 320,
  showLabels = true,
  showTooltips = true,
  overlayData = null,
  overlayColor = "var(--green-bright)",
  className = "",
}) {
  const svgRef = useRef(null);
  const tooltipRef = useRef(null);

  useEffect(() => {
    if (!data.length) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const margin = showLabels ? 48 : 8;
    const cx = size / 2;
    const cy = size / 2;
    const radius = (size - margin * 2) / 2;
    const n = data.length;

    // Determine max for scale — use at least 0.1 to avoid degenerate charts
    const maxVal = Math.max(d3.max(data, (d) => d.percentage) || 0.1, 0.01);
    const overlayMax = overlayData
      ? Math.max(d3.max(overlayData, (d) => d.percentage) || 0, 0)
      : 0;
    const scaleMax = Math.max(maxVal, overlayMax) * 1.15;

    const rScale = d3.scaleLinear().domain([0, scaleMax]).range([0, radius]);
    const angleSlice = (2 * Math.PI) / n;

    const g = svg.append("g").attr("transform", `translate(${cx},${cy})`);

    // --- Grid rings ---
    const ringLevels = [0.33, 0.66, 1.0];
    ringLevels.forEach((pct, ri) => {
      const r = radius * pct;
      const pts = Array.from({ length: n }, (_, i) => {
        const a = angleSlice * i - Math.PI / 2;
        return [r * Math.cos(a), r * Math.sin(a)];
      });
      g.append("polygon")
        .attr("points", pts.map((p) => p.join(",")).join(" "))
        .attr("fill", "none")
        .attr("stroke", "var(--border)")
        .attr("stroke-width", 0.8);

      // Ring label on first axis only (full size)
      if (showLabels && ri < ringLevels.length) {
        const val = scaleMax * pct;
        g.append("text")
          .attr("x", 4)
          .attr("y", -r + 12)
          .text(val < 1 ? val.toFixed(2) + "%" : val.toFixed(1) + "%")
          .attr("fill", "var(--cream-faint)")
          .attr("font-family", "var(--font-data)")
          .attr("font-size", "9px");
      }
    });

    // --- Spokes ---
    const dominantIdx = data.reduce(
      (best, d, i) => (d.percentage > data[best].percentage ? i : best),
      0
    );

    data.forEach((_, i) => {
      const a = angleSlice * i - Math.PI / 2;
      g.append("line")
        .attr("x1", 0)
        .attr("y1", 0)
        .attr("x2", radius * Math.cos(a))
        .attr("y2", radius * Math.sin(a))
        .attr("stroke", i === dominantIdx ? "var(--gold-dim)" : "var(--border)")
        .attr("stroke-width", i === dominantIdx ? 1.5 : 0.6);
    });

    // --- Data polygon ---
    function drawPolygon(polyData, color, fillOpacity, strokeWidth, animate) {
      const points = polyData.map((d, i) => {
        const a = angleSlice * i - Math.PI / 2;
        const r = rScale(d.percentage);
        return [r * Math.cos(a), r * Math.sin(a)];
      });

      const zeroPoints = polyData.map(() => [0, 0]);

      const polygon = g
        .append("polygon")
        .attr("points", zeroPoints.map((p) => p.join(",")).join(" "))
        .attr("fill", color)
        .attr("fill-opacity", fillOpacity)
        .attr("stroke", color)
        .attr("stroke-width", strokeWidth);

      if (animate) {
        polygon
          .transition()
          .duration(500)
          .ease(d3.easeCubicOut)
          .attr("points", points.map((p) => p.join(",")).join(" "));
      } else {
        polygon.attr("points", points.map((p) => p.join(",")).join(" "));
      }

      // Data points
      points.forEach(([x, y], i) => {
        const dot = g
          .append("circle")
          .attr("cx", 0)
          .attr("cy", 0)
          .attr("r", size > 100 ? 4 : 2)
          .attr("fill", color)
          .attr("stroke", "var(--bg-dark)")
          .attr("stroke-width", 1)
          .style("filter", `drop-shadow(0 0 4px ${color})`);

        if (animate) {
          dot
            .transition()
            .delay(i * 50)
            .duration(400)
            .ease(d3.easeCubicOut)
            .attr("cx", x)
            .attr("cy", y);
        } else {
          dot.attr("cx", x).attr("cy", y);
        }

        // Tooltip hover area (invisible larger circle)
        if (showTooltips) {
          g.append("circle")
            .attr("cx", x)
            .attr("cy", y)
            .attr("r", 12)
            .attr("fill", "transparent")
            .style("cursor", "pointer")
            .on("mouseenter", (event) => {
              const tip = tooltipRef.current;
              if (!tip) return;
              const d = polyData[i];
              // Safely set tooltip content using textContent on child elements
              tip.querySelector("[data-name]").textContent = d.name;
              tip.querySelector("[data-pct]").textContent = d.percentage.toFixed(2) + "%";
              tip.querySelector("[data-effect]").textContent =
                TERPENE_EFFECTS[d.name] || "";
              tip.style.opacity = "1";
              const rect = svgRef.current.getBoundingClientRect();
              tip.style.left = `${event.clientX - rect.left}px`;
              tip.style.top = `${event.clientY - rect.top - 60}px`;
            })
            .on("mouseleave", () => {
              if (tooltipRef.current) tooltipRef.current.style.opacity = "0";
            });
        }
      });
    }

    // Primary data
    drawPolygon(data, "var(--gold)", 0.15, 2, true);

    // Overlay comparison
    if (overlayData && overlayData.length) {
      // Align overlay data to same axes as primary — match by name
      const aligned = data.map((d) => {
        const match = overlayData.find((o) => o.name === d.name);
        return { name: d.name, percentage: match ? match.percentage : 0 };
      });
      drawPolygon(aligned, overlayColor, 0.1, 1.5, true);
    }

    // --- Labels ---
    if (showLabels) {
      data.forEach((d, i) => {
        const a = angleSlice * i - Math.PI / 2;
        const labelR = radius + 16;
        const x = labelR * Math.cos(a);
        const y = labelR * Math.sin(a);

        const isDominant = i === dominantIdx;

        // Terpene name
        g.append("text")
          .attr("x", x)
          .attr("y", y - 6)
          .attr("text-anchor", "middle")
          .attr("dominant-baseline", "middle")
          .text(d.name)
          .attr("fill", isDominant ? "var(--cream)" : "var(--cream-dim)")
          .attr("font-family", "var(--font-body)")
          .attr("font-size", Math.max(size * 0.035, 11) + "px")
          .attr("font-weight", isDominant ? 600 : 400);

        // Percentage value
        g.append("text")
          .attr("x", x)
          .attr("y", y + 8)
          .attr("text-anchor", "middle")
          .attr("dominant-baseline", "middle")
          .text(d.percentage.toFixed(2) + "%")
          .attr("fill", isDominant ? "var(--gold)" : "var(--cream-faint)")
          .attr("font-family", "var(--font-data)")
          .attr("font-size", Math.max(size * 0.032, 10) + "px");
      });
    }

    return () => {
      svg.selectAll("*").interrupt();
    };
  }, [data, size, showLabels, showTooltips, overlayData, overlayColor]);

  if (!data.length) {
    return (
      <div
        className={className}
        style={{
          width: size,
          height: size,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--cream-faint)",
          fontSize: "12px",
          fontFamily: "var(--font-data)",
        }}
      >
        No terpene data
      </div>
    );
  }

  return (
    <div className={className} style={{ position: "relative", width: size, height: size }}>
      <svg ref={svgRef} width={size} height={size} />
      {showTooltips && (
        <div
          ref={tooltipRef}
          style={{
            position: "absolute",
            pointerEvents: "none",
            opacity: 0,
            transition: "opacity 150ms",
            background: "var(--bg-void)",
            border: "1px solid var(--border)",
            borderRadius: "6px",
            padding: "8px 12px",
            display: "flex",
            flexDirection: "column",
            gap: "2px",
            fontSize: "12px",
            zIndex: 10,
            whiteSpace: "nowrap",
          }}
        >
          <strong data-name style={{ color: "var(--gold)" }} />
          <span data-pct style={{ fontFamily: "var(--font-data)" }} />
          <span data-effect style={{ color: "var(--cream-dim)", fontSize: "11px" }} />
        </div>
      )}
    </div>
  );
}
