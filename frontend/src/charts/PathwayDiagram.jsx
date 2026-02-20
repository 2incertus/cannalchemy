import { useRef, useEffect } from "react";
import * as d3 from "d3";

const NODE_STYLES = {
  molecule: { shape: "hexagon", stroke: "var(--gold)", r: 20 },
  receptor: { shape: "circle", stroke: "var(--green)", r: 16 },
  effect: { shape: "rect", stroke: "var(--cream)", r: 14 },
};

/**
 * PathwayDiagram — D3 force-directed graph showing molecule→receptor→effect paths.
 *
 * Props:
 *   pathways  — [{molecule, receptor, ki_nm, affinity_score, action_type}]
 *   effects   — [string] predicted effect names
 *   width     — number (default 100%)
 *   height    — number (default 400)
 */
export default function PathwayDiagram({
  pathways = [],
  effects = [],
  height = 400,
}) {
  const containerRef = useRef(null);
  const svgRef = useRef(null);

  useEffect(() => {
    if (!pathways.length) return;

    const container = containerRef.current;
    const width = container?.clientWidth || 700;
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("width", width).attr("height", height);

    // Build nodes and links from pathways
    const nodeMap = new Map();
    const links = [];

    pathways.forEach((p) => {
      const molId = `mol:${p.molecule}`;
      const recId = `rec:${p.receptor}`;

      if (!nodeMap.has(molId)) {
        nodeMap.set(molId, { id: molId, label: p.molecule, type: "molecule" });
      }
      if (!nodeMap.has(recId)) {
        nodeMap.set(recId, { id: recId, label: p.receptor, type: "receptor" });
      }

      links.push({
        source: molId,
        target: recId,
        affinity: p.affinity_score || 2,
        action: p.action_type || "",
      });
    });

    // Add effect nodes linked to receptors they're predicted from
    const effectSet = new Set(effects);
    effectSet.forEach((eff) => {
      const effId = `eff:${eff}`;
      nodeMap.set(effId, { id: effId, label: eff, type: "effect" });
      // Connect each effect to all receptors (simplified — real pathways are complex)
      nodeMap.forEach((node) => {
        if (node.type === "receptor") {
          links.push({
            source: node.id,
            target: effId,
            affinity: 1,
            action: "modulates",
          });
        }
      });
    });

    const nodes = Array.from(nodeMap.values());

    // If too many effect→receptor links, limit to keep graph readable
    const maxEffectLinks = 3;
    const receptorIds = nodes.filter((n) => n.type === "receptor").map((n) => n.id);
    const effectLinks = links.filter(
      (l) =>
        typeof l.target === "string"
          ? l.target.startsWith("eff:")
          : l.target.id?.startsWith("eff:")
    );

    // Keep only first N receptor links per effect
    const keptEffectLinks = new Set();
    const effLinkCounts = {};
    effectLinks.forEach((l) => {
      const tgt = typeof l.target === "string" ? l.target : l.target.id;
      effLinkCounts[tgt] = (effLinkCounts[tgt] || 0) + 1;
      if (effLinkCounts[tgt] <= maxEffectLinks) {
        keptEffectLinks.add(l);
      }
    });

    const filteredLinks = links.filter(
      (l) => !effectLinks.includes(l) || keptEffectLinks.has(l)
    );

    // Force simulation
    const simulation = d3
      .forceSimulation(nodes)
      .force(
        "link",
        d3
          .forceLink(filteredLinks)
          .id((d) => d.id)
          .distance(80)
      )
      .force("charge", d3.forceManyBody().strength(-200))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide(30));

    // Zoom
    const g = svg.append("g");
    svg.call(
      d3
        .zoom()
        .scaleExtent([0.3, 3])
        .on("zoom", (event) => g.attr("transform", event.transform))
    );

    // Links
    const link = g
      .selectAll("line")
      .data(filteredLinks)
      .join("line")
      .attr("stroke", "var(--border)")
      .attr("stroke-width", (d) => Math.max(1, d.affinity))
      .attr("stroke-opacity", 0.5);

    // Node groups
    const node = g
      .selectAll("g.node")
      .data(nodes)
      .join("g")
      .attr("class", "node")
      .style("cursor", "pointer")
      .call(
        d3
          .drag()
          .on("start", (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      );

    // Draw shapes per type
    node.each(function (d) {
      const el = d3.select(this);
      const style = NODE_STYLES[d.type] || NODE_STYLES.effect;

      if (d.type === "molecule") {
        // Hexagon
        const r = style.r;
        const hex = Array.from({ length: 6 }, (_, i) => {
          const a = (Math.PI / 3) * i - Math.PI / 6;
          return `${r * Math.cos(a)},${r * Math.sin(a)}`;
        }).join(" ");
        el.append("polygon")
          .attr("points", hex)
          .attr("fill", "var(--bg-card)")
          .attr("stroke", style.stroke)
          .attr("stroke-width", 1.5);
      } else if (d.type === "receptor") {
        el.append("circle")
          .attr("r", style.r)
          .attr("fill", "var(--bg-card)")
          .attr("stroke", style.stroke)
          .attr("stroke-width", 1.5);
      } else {
        // Rounded rect for effect
        el.append("rect")
          .attr("x", -28)
          .attr("y", -12)
          .attr("width", 56)
          .attr("height", 24)
          .attr("rx", 6)
          .attr("fill", "var(--bg-card)")
          .attr("stroke", style.stroke)
          .attr("stroke-width", 1.5);
      }

      // Label
      el.append("text")
        .text(d.label)
        .attr("y", d.type === "effect" ? 4 : style.r + 14)
        .attr("text-anchor", "middle")
        .attr("fill", "var(--cream-dim)")
        .attr("font-family", "var(--font-data)")
        .attr("font-size", "10px");
    });

    // Hover: highlight connected
    node
      .on("mouseenter", (event, d) => {
        const connected = new Set();
        filteredLinks.forEach((l) => {
          const sid = typeof l.source === "string" ? l.source : l.source.id;
          const tid = typeof l.target === "string" ? l.target : l.target.id;
          if (sid === d.id) connected.add(tid);
          if (tid === d.id) connected.add(sid);
        });
        connected.add(d.id);

        node.style("opacity", (n) => (connected.has(n.id) ? 1 : 0.2));
        link.style("stroke", (l) => {
          const sid = typeof l.source === "string" ? l.source : l.source.id;
          const tid = typeof l.target === "string" ? l.target : l.target.id;
          return sid === d.id || tid === d.id ? "var(--gold)" : "var(--border)";
        }).style("stroke-opacity", (l) => {
          const sid = typeof l.source === "string" ? l.source : l.source.id;
          const tid = typeof l.target === "string" ? l.target : l.target.id;
          return sid === d.id || tid === d.id ? 0.8 : 0.15;
        });
      })
      .on("mouseleave", () => {
        node.style("opacity", 1);
        link
          .style("stroke", "var(--border)")
          .style("stroke-opacity", 0.5);
      });

    // Tick
    simulation.on("tick", () => {
      link
        .attr("x1", (d) => d.source.x)
        .attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x)
        .attr("y2", (d) => d.target.y);
      node.attr("transform", (d) => `translate(${d.x},${d.y})`);
    });

    return () => {
      simulation.stop();
    };
  }, [pathways, effects, height]);

  if (!pathways.length) {
    return (
      <div
        style={{
          height,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--cream-faint)",
          fontSize: "13px",
        }}
      >
        No pathway data available
      </div>
    );
  }

  return (
    <div ref={containerRef} style={{ width: "100%", position: "relative" }}>
      <svg ref={svgRef} style={{ width: "100%", height }} />
      {/* Legend */}
      <div
        style={{
          display: "flex",
          gap: 24,
          justifyContent: "center",
          padding: "8px 0",
          fontSize: "11px",
          color: "var(--cream-dim)",
          fontFamily: "var(--font-data)",
        }}
      >
        <span>
          <span style={{ color: "var(--gold)" }}>⬡</span> Molecule
        </span>
        <span>
          <span style={{ color: "var(--green)" }}>●</span> Receptor
        </span>
        <span>
          <span style={{ color: "var(--cream)" }}>▢</span> Effect
        </span>
      </div>
    </div>
  );
}
