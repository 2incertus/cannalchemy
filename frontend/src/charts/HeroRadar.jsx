import { useRef, useEffect } from "react";
import * as d3 from "d3";

const TERPENES = [
  { name: "myrcene", value: 0.42 },
  { name: "limonene", value: 0.31 },
  { name: "caryophyllene", value: 0.28 },
  { name: "pinene", value: 0.19 },
  { name: "linalool", value: 0.15 },
  { name: "terpinolene", value: 0.11 },
  { name: "humulene", value: 0.09 },
  { name: "ocimene", value: 0.07 },
];

export default function HeroRadar({ size = 500, opacity = 0.08 }) {
  const svgRef = useRef(null);

  useEffect(() => {
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const cx = size / 2;
    const cy = size / 2;
    const radius = size * 0.42;
    const n = TERPENES.length;

    const g = svg
      .append("g")
      .attr("transform", `translate(${cx},${cy})`);

    const rScale = d3.scaleLinear().domain([0, 0.5]).range([0, radius]);

    // Concentric rings
    [0.33, 0.66, 1].forEach((pct) => {
      const r = radius * pct;
      const pts = Array.from({ length: n }, (_, i) => {
        const angle = (2 * Math.PI * i) / n - Math.PI / 2;
        return [r * Math.cos(angle), r * Math.sin(angle)];
      });
      g.append("polygon")
        .attr("points", pts.map((p) => p.join(",")).join(" "))
        .attr("fill", "none")
        .attr("stroke", "var(--gold)")
        .attr("stroke-width", 0.5)
        .attr("opacity", 0.3);
    });

    // Spokes
    TERPENES.forEach((_, i) => {
      const angle = (2 * Math.PI * i) / n - Math.PI / 2;
      g.append("line")
        .attr("x1", 0)
        .attr("y1", 0)
        .attr("x2", radius * Math.cos(angle))
        .attr("y2", radius * Math.sin(angle))
        .attr("stroke", "var(--gold)")
        .attr("stroke-width", 0.5)
        .attr("opacity", 0.2);
    });

    // Data polygon
    const points = TERPENES.map((d, i) => {
      const angle = (2 * Math.PI * i) / n - Math.PI / 2;
      const r = rScale(d.value);
      return [r * Math.cos(angle), r * Math.sin(angle)];
    });

    g.append("polygon")
      .attr("points", points.map((p) => p.join(",")).join(" "))
      .attr("fill", "var(--gold)")
      .attr("fill-opacity", 0.12)
      .attr("stroke", "var(--gold)")
      .attr("stroke-width", 1.5);

    // Dots at vertices
    points.forEach(([x, y]) => {
      g.append("circle")
        .attr("cx", x)
        .attr("cy", y)
        .attr("r", 3)
        .attr("fill", "var(--gold)")
        .attr("opacity", 0.6);
    });

    // Slow rotation
    function rotate() {
      g.transition()
        .duration(60000)
        .ease(d3.easeLinear)
        .attrTween("transform", () => {
          const interp = d3.interpolate(0, 360);
          return (t) => `translate(${cx},${cy}) rotate(${interp(t)})`;
        })
        .on("end", rotate);
    }
    rotate();

    return () => {
      svg.selectAll("*").interrupt();
    };
  }, [size]);

  return (
    <svg
      ref={svgRef}
      width={size}
      height={size}
      style={{ opacity, position: "absolute" }}
      aria-hidden="true"
    />
  );
}
