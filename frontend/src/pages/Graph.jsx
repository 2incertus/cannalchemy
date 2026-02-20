import { useState, useEffect, useRef, useCallback } from "react";
import { fetchGraph } from "../lib/api";
import * as d3 from "d3";
import { Search } from "lucide-react";

const NODE_COLORS = {
  molecule: "var(--gold)",
  receptor: "var(--green)",
  effect: "var(--cream)",
};

export default function Graph() {
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filters, setFilters] = useState({ molecule: true, receptor: true, effect: true });
  const svgRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    fetchGraph()
      .then(setGraphData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const drawGraph = useCallback(() => {
    if (!graphData || !svgRef.current || !containerRef.current) return;

    const width = containerRef.current.clientWidth;
    const height = Math.max(window.innerHeight - 64, 500);
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.attr("width", width).attr("height", height);

    // Filter nodes
    let nodes = graphData.nodes.filter((n) => filters[n.type]);
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      nodes = nodes.filter((n) => n.name.toLowerCase().includes(q));
    }
    const nodeIds = new Set(nodes.map((n) => n.id));
    const edges = graphData.edges.filter(
      (e) => nodeIds.has(e.source) && nodeIds.has(e.target)
    );

    // Clone for simulation
    const simNodes = nodes.map((n) => ({ ...n }));
    const simEdges = edges.map((e) => ({ ...e }));

    const simulation = d3
      .forceSimulation(simNodes)
      .force("link", d3.forceLink(simEdges).id((d) => d.id).distance(60))
      .force("charge", d3.forceManyBody().strength(-120))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide(22));

    const g = svg.append("g");
    svg.call(
      d3.zoom().scaleExtent([0.2, 5]).on("zoom", (event) => g.attr("transform", event.transform))
    );

    // Edges
    const link = g
      .selectAll("line")
      .data(simEdges)
      .join("line")
      .attr("stroke", "var(--border)")
      .attr("stroke-width", (d) => Math.max(1, d.affinity_score || 1))
      .attr("stroke-opacity", 0.4);

    // Nodes
    const node = g
      .selectAll("g.node")
      .data(simNodes)
      .join("g")
      .attr("class", "node")
      .style("cursor", "pointer")
      .call(
        d3.drag()
          .on("start", (event, d) => { if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
          .on("drag", (event, d) => { d.fx = event.x; d.fy = event.y; })
          .on("end", (event, d) => { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; })
      );

    node.each(function (d) {
      const el = d3.select(this);
      const color = NODE_COLORS[d.type] || "var(--cream-dim)";

      if (d.type === "molecule") {
        const r = 14;
        const hex = Array.from({ length: 6 }, (_, i) => {
          const a = (Math.PI / 3) * i - Math.PI / 6;
          return `${r * Math.cos(a)},${r * Math.sin(a)}`;
        }).join(" ");
        el.append("polygon").attr("points", hex).attr("fill", "var(--bg-card)").attr("stroke", color).attr("stroke-width", 1.5);
      } else if (d.type === "receptor") {
        el.append("circle").attr("r", 12).attr("fill", "var(--bg-card)").attr("stroke", color).attr("stroke-width", 1.5);
      } else {
        el.append("rect").attr("x", -22).attr("y", -10).attr("width", 44).attr("height", 20).attr("rx", 5).attr("fill", "var(--bg-card)").attr("stroke", color).attr("stroke-width", 1.5);
      }

      el.append("text").text(d.name).attr("y", d.type === "effect" ? 4 : (d.type === "molecule" ? 24 : 22)).attr("text-anchor", "middle").attr("fill", color).attr("font-family", "var(--font-data)").attr("font-size", "9px");
    });

    // Click & hover
    node
      .on("click", (event, d) => {
        event.stopPropagation();
        setSelectedNode(d);
        const connected = new Set();
        simEdges.forEach((e) => {
          const sid = typeof e.source === "object" ? e.source.id : e.source;
          const tid = typeof e.target === "object" ? e.target.id : e.target;
          if (sid === d.id) connected.add(tid);
          if (tid === d.id) connected.add(sid);
        });
        connected.add(d.id);
        node.style("opacity", (n) => (connected.has(n.id) ? 1 : 0.12));
        link.style("stroke-opacity", (l) => {
          const sid = typeof l.source === "object" ? l.source.id : l.source;
          const tid = typeof l.target === "object" ? l.target.id : l.target;
          return sid === d.id || tid === d.id ? 0.7 : 0.05;
        });
      })
      .on("dblclick", (event, d) => {
        // Zoom to node
        svg.transition().duration(500).call(
          d3.zoom().scaleExtent([0.2, 5]).on("zoom", (ev) => g.attr("transform", ev.transform)).transform,
          d3.zoomIdentity.translate(width / 2, height / 2).scale(2).translate(-d.x, -d.y)
        );
      });

    svg.on("click", () => {
      setSelectedNode(null);
      node.style("opacity", 1);
      link.style("stroke-opacity", 0.4);
    });

    simulation.on("tick", () => {
      link.attr("x1", (d) => d.source.x).attr("y1", (d) => d.source.y).attr("x2", (d) => d.target.x).attr("y2", (d) => d.target.y);
      node.attr("transform", (d) => `translate(${d.x},${d.y})`);
    });

    return () => simulation.stop();
  }, [graphData, searchQuery, filters]);

  useEffect(() => {
    const cleanup = drawGraph();
    return cleanup;
  }, [drawGraph]);

  const toggleFilter = (type) => setFilters((f) => ({ ...f, [type]: !f[type] }));

  return (
    <div className="page graph-layout">
      {/* Sidebar */}
      <div className="graph-sidebar">
        <h2 className="font-display" style={{ fontSize: "1.1rem", color: "var(--gold)" }}>
          Knowledge Graph
        </h2>

        {/* Search */}
        <div style={{ position: "relative" }}>
          <Search size={14} style={{ position: "absolute", left: 10, top: 10, color: "var(--cream-faint)" }} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter nodes..."
            style={{
              width: "100%",
              padding: "8px 8px 8px 30px",
              border: "1px solid var(--border)",
              borderRadius: "4px",
              background: "var(--bg-card)",
              color: "var(--cream)",
              fontSize: "13px",
              fontFamily: "var(--font-body)",
              outline: "none",
            }}
          />
        </div>

        {/* Type toggles */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {Object.entries({ molecule: "Molecules", receptor: "Receptors", effect: "Effects" }).map(
            ([type, label]) => (
              <label
                key={type}
                style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: "13px", color: "var(--cream)" }}
              >
                <input
                  type="checkbox"
                  checked={filters[type]}
                  onChange={() => toggleFilter(type)}
                  style={{ accentColor: NODE_COLORS[type] }}
                />
                <span style={{ width: 8, height: 8, borderRadius: type === "receptor" ? "50%" : "2px", background: NODE_COLORS[type] }} />
                {label}
              </label>
            )
          )}
        </div>

        {/* Selected node detail */}
        {selectedNode && (
          <div style={{ padding: 12, background: "var(--bg-card)", borderRadius: 6, border: "1px solid var(--border)" }}>
            <div style={{ fontFamily: "var(--font-display)", fontSize: "14px", color: NODE_COLORS[selectedNode.type], marginBottom: 4 }}>
              {selectedNode.name}
            </div>
            <div style={{ fontSize: "11px", color: "var(--cream-dim)", textTransform: "capitalize" }}>
              {selectedNode.type}
            </div>
          </div>
        )}

        {/* Legend */}
        <div style={{ fontSize: "11px", color: "var(--cream-faint)", lineHeight: 1.8 }}>
          <div>Click node to highlight connections</div>
          <div>Double-click to zoom in</div>
          <div>Drag nodes to rearrange</div>
          <div>Scroll to zoom, drag to pan</div>
        </div>

        {loading && <div style={{ color: "var(--cream-faint)", fontSize: "13px" }}>Loading graph...</div>}
        {graphData && (
          <div className="font-data" style={{ fontSize: "11px", color: "var(--cream-faint)" }}>
            {graphData.nodes.length} nodes · {graphData.edges.length} edges
          </div>
        )}
      </div>

      {/* Graph area */}
      <div ref={containerRef} style={{ flex: 1, overflow: "hidden" }}>
        <svg ref={svgRef} style={{ width: "100%", height: "100%" }} />
      </div>
    </div>
  );
}
