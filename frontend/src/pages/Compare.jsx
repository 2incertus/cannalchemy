import { useState, useEffect, useCallback, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { fetchStrain, fetchStrains } from "../lib/api";
import TerpeneRadar from "../charts/TerpeneRadar";
import EffectBars from "../charts/EffectBars";
import TypeBadge from "../components/TypeBadge";
import { X } from "lucide-react";

export default function Compare() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [strains, setStrains] = useState([]);
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef(null);

  // Load strains from URL on mount
  useEffect(() => {
    const names = searchParams.get("strains")?.split(",").filter(Boolean) || [];
    if (names.length > 0) {
      Promise.all(names.map((n) => fetchStrain(n).catch(() => null))).then(
        (results) => setStrains(results.filter(Boolean))
      );
    }
  }, []);

  // Update URL when strains change
  useEffect(() => {
    if (strains.length > 0) {
      setSearchParams({ strains: strains.map((s) => s.name).join(",") });
    } else {
      setSearchParams({});
    }
  }, [strains]);

  // Autocomplete search
  const onQueryChange = useCallback((val) => {
    setQuery(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (val.length < 2) {
      setSuggestions([]);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const data = await fetchStrains(val, "", 8);
        setSuggestions(data.strains || []);
      } catch {
        setSuggestions([]);
      }
    }, 300);
  }, []);

  const addStrain = async (name) => {
    if (strains.length >= 3 || strains.find((s) => s.name === name)) return;
    setLoading(true);
    setQuery("");
    setSuggestions([]);
    try {
      const data = await fetchStrain(name);
      setStrains((prev) => [...prev, data]);
    } catch { /* ignore */ }
    setLoading(false);
  };

  const removeStrain = (name) => {
    setStrains((prev) => prev.filter((s) => s.name !== name));
  };

  // Merge terpene data for overlaid radar
  const allTerpeneNames = new Set();
  strains.forEach((s) =>
    (s.compositions || [])
      .filter((c) => c.type === "terpene" && c.percentage > 0)
      .forEach((c) => allTerpeneNames.add(c.molecule))
  );

  const radarDataSets = strains.map((s) => {
    const comps = s.compositions || [];
    return [...allTerpeneNames].map((name) => {
      const found = comps.find((c) => c.molecule === name);
      return { name, percentage: found?.percentage || 0 };
    });
  });

  // Key differences
  const differences = [];
  if (strains.length >= 2) {
    const effects0 = strains[0].predicted_effects || [];
    const effects1 = strains[1].predicted_effects || [];
    const map0 = Object.fromEntries(effects0.map((e) => [e.name, e.probability]));
    const map1 = Object.fromEntries(effects1.map((e) => [e.name, e.probability]));
    const allEffects = new Set([...effects0.map((e) => e.name), ...effects1.map((e) => e.name)]);
    allEffects.forEach((eff) => {
      const diff = Math.abs((map0[eff] || 0) - (map1[eff] || 0));
      differences.push({ name: eff, diff, s0: map0[eff] || 0, s1: map1[eff] || 0 });
    });
    differences.sort((a, b) => b.diff - a.diff);
  }

  const COLORS = ["var(--gold)", "var(--green-bright)", "var(--blue)"];

  return (
    <div className="page" style={{ maxWidth: 1100, margin: "0 auto", padding: "80px 24px 48px" }}>
      <h1
        className="font-display"
        style={{ fontSize: "2rem", color: "var(--gold)", marginBottom: 8, letterSpacing: "0.05em" }}
      >
        Compare Strains
      </h1>
      <p style={{ color: "var(--cream-dim)", marginBottom: 24, fontSize: "15px" }}>
        Add up to 3 strains to compare their terpene profiles, predicted effects, and chemistry.
      </p>

      {/* Search + selected chips */}
      <div style={{ marginBottom: 32, position: "relative" }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
          {strains.map((s, i) => (
            <span
              key={s.name}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "4px 12px",
                borderRadius: "16px",
                border: `1px solid ${COLORS[i]}`,
                color: COLORS[i],
                fontSize: "13px",
                fontFamily: "var(--font-body)",
              }}
            >
              {s.name}
              <button
                type="button"
                onClick={() => removeStrain(s.name)}
                style={{ background: "none", border: "none", cursor: "pointer", color: "inherit", padding: 0, display: "flex" }}
              >
                <X size={14} />
              </button>
            </span>
          ))}
        </div>

        {strains.length < 3 && (
          <div style={{ position: "relative" }}>
            <input
              type="text"
              value={query}
              onChange={(e) => onQueryChange(e.target.value)}
              placeholder="Search strains to add..."
              style={{
                width: "100%",
                maxWidth: 400,
                padding: "10px 16px",
                border: "1px solid var(--border)",
                borderRadius: "6px",
                background: "var(--bg-card)",
                color: "var(--cream)",
                fontSize: "14px",
                fontFamily: "var(--font-body)",
                outline: "none",
              }}
            />
            {suggestions.length > 0 && (
              <div
                style={{
                  position: "absolute",
                  top: "100%",
                  left: 0,
                  width: 400,
                  maxHeight: 240,
                  overflowY: "auto",
                  background: "var(--bg-void)",
                  border: "1px solid var(--border)",
                  borderRadius: "6px",
                  zIndex: 20,
                  marginTop: 4,
                }}
              >
                {suggestions.map((s) => (
                  <button
                    key={s.name}
                    type="button"
                    onClick={() => addStrain(s.name)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      width: "100%",
                      padding: "10px 16px",
                      border: "none",
                      background: "transparent",
                      color: "var(--cream)",
                      fontSize: "13px",
                      cursor: "pointer",
                      textAlign: "left",
                      fontFamily: "var(--font-body)",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-elevated)")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    {s.name}
                    <TypeBadge type={s.strain_type} />
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {loading && <div className="skeleton" style={{ height: 200, marginBottom: 24 }} />}

      {strains.length === 0 && !loading && (
        <div style={{ textAlign: "center", padding: "64px 0", color: "var(--cream-faint)" }}>
          Add strains above to start comparing
        </div>
      )}

      {strains.length > 0 && (
        <>
          {/* Overlaid Radar */}
          <section className="card" style={{ padding: 24, marginBottom: 24 }}>
            <h2 className="font-display" style={{ fontSize: "1.1rem", color: "var(--cream)", marginBottom: 16 }}>
              Terpene Fingerprints
            </h2>
            <div style={{ display: "flex", justifyContent: "center" }}>
              <TerpeneRadar
                data={radarDataSets[0] || []}
                overlayData={radarDataSets[1] || null}
                overlayColor={COLORS[1]}
                size={360}
              />
            </div>
            {/* Legend */}
            <div style={{ display: "flex", justifyContent: "center", gap: 24, marginTop: 12 }}>
              {strains.map((s, i) => (
                <span key={s.name} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "12px", color: COLORS[i] }}>
                  <span style={{ width: 12, height: 3, background: COLORS[i], display: "inline-block", borderRadius: 2 }} />
                  {s.name}
                </span>
              ))}
            </div>
          </section>

          {/* Side-by-side effects */}
          <section style={{ display: "grid", gridTemplateColumns: `repeat(${strains.length}, 1fr)`, gap: 16, marginBottom: 24 }}>
            {strains.map((s, i) => (
              <div key={s.name} className="card" style={{ padding: 20 }}>
                <h3 className="font-display" style={{ color: COLORS[i], fontSize: "1rem", marginBottom: 12 }}>
                  {s.name}
                </h3>
                <EffectBars effects={(s.predicted_effects || []).map((e) => ({ ...e, predicted: e.probability >= 0.5 }))} />
              </div>
            ))}
          </section>

          {/* Key differences */}
          {differences.length > 0 && (
            <section className="card" style={{ padding: 24, marginBottom: 24 }}>
              <h2 className="font-display" style={{ fontSize: "1.1rem", color: "var(--cream)", marginBottom: 16 }}>
                Key Differences
              </h2>
              <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 8 }}>
                {differences.slice(0, 5).map((d) => (
                  <li key={d.name} style={{ display: "flex", alignItems: "center", gap: 12, fontSize: "13px" }}>
                    <span style={{ color: "var(--cream)", textTransform: "capitalize", width: 140 }}>{d.name}</span>
                    <span className="font-data" style={{ color: COLORS[0] }}>{Math.round(d.s0 * 100)}%</span>
                    <span style={{ color: "var(--cream-faint)" }}>vs</span>
                    <span className="font-data" style={{ color: COLORS[1] }}>{Math.round(d.s1 * 100)}%</span>
                    <span className="font-data" style={{ color: "var(--cream-dim)", fontSize: "11px" }}>
                      (Δ{Math.round(d.diff * 100)}%)
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Chemistry table */}
          <section className="card" style={{ padding: 24, overflow: "auto" }}>
            <h2 className="font-display" style={{ fontSize: "1.1rem", color: "var(--cream)", marginBottom: 16 }}>
              Chemical Composition
            </h2>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left", padding: "8px 12px", borderBottom: "1px solid var(--border)", color: "var(--cream-dim)", fontWeight: 400 }}>
                    Molecule
                  </th>
                  {strains.map((s, i) => (
                    <th key={s.name} style={{ textAlign: "right", padding: "8px 12px", borderBottom: "1px solid var(--border)", color: COLORS[i], fontWeight: 500 }}>
                      {s.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...allTerpeneNames].sort().map((mol) => (
                  <tr key={mol}>
                    <td style={{ padding: "6px 12px", borderBottom: "1px solid var(--bg-elevated)", color: "var(--cream)", fontFamily: "var(--font-body)" }}>
                      {mol}
                    </td>
                    {strains.map((s) => {
                      const comp = (s.compositions || []).find((c) => c.molecule === mol);
                      const pct = comp?.percentage || 0;
                      const brightness = Math.min(pct / 0.5, 1);
                      return (
                        <td
                          key={s.name}
                          className="font-data"
                          style={{
                            textAlign: "right",
                            padding: "6px 12px",
                            borderBottom: "1px solid var(--bg-elevated)",
                            color: pct > 0 ? `rgba(212,168,67,${0.4 + brightness * 0.6})` : "var(--cream-faint)",
                          }}
                        >
                          {pct > 0 ? pct.toFixed(3) + "%" : "—"}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
}
