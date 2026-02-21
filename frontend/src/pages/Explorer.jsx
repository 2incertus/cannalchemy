import { useState, useEffect, useCallback } from "react";
import { fetchEffects, fetchStrains, matchEffects } from "../lib/api";
import EffectChip from "../components/EffectChip";
import StrainCard from "../components/StrainCard";
import { useNavigate } from "react-router-dom";

const TYPE_OPTIONS = ["all", "indica", "sativa", "hybrid"];

export default function Explorer() {
  const navigate = useNavigate();
  const [effects, setEffects] = useState([]);
  const [selectedEffects, setSelectedEffects] = useState([]);
  const [selectedType, setSelectedType] = useState("all");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showNegative, setShowNegative] = useState(false);
  const [showSummaries, setShowSummaries] = useState(false);

  // Load available effects
  useEffect(() => {
    fetchEffects()
      .then((data) => setEffects(data.effects || []))
      .catch(() => {});
  }, []);

  // Fetch results when selection changes
  const search = useCallback(async () => {
    setLoading(true);
    try {
      const typeFilter = selectedType === "all" ? "" : selectedType;
      if (selectedEffects.length > 0) {
        const data = await matchEffects(selectedEffects, typeFilter, 24, showSummaries);
        setResults(data.strains || []);
      } else {
        const data = await fetchStrains("", typeFilter, 12);
        // Wrap plain strains to match card format
        setResults(
          (data.strains || []).map((s) => ({
            ...s,
            score: null,
            top_effects: [],
          }))
        );
      }
    } catch {
      setResults([]);
    }
    setLoading(false);
  }, [selectedEffects, selectedType, showSummaries]);

  useEffect(() => {
    search();
  }, [search]);

  const toggleEffect = (name) => {
    setSelectedEffects((prev) =>
      prev.includes(name) ? prev.filter((e) => e !== name) : [...prev, name]
    );
  };

  const handleCompare = (strainName) => {
    navigate(`/compare?strain=${encodeURIComponent(strainName)}`);
  };

  // Group effects by category
  const positive = effects.filter((e) => e.category === "positive" && e.name !== "aroused");
  const medical = effects.filter((e) => e.category === "medical");
  const negative = effects.filter((e) => e.category === "negative");

  return (
    <div className="page" style={{ maxWidth: 1100, margin: "0 auto", padding: "80px 24px 48px" }}>
      {/* Header */}
      <h1
        className="font-display"
        style={{
          fontSize: "2rem",
          color: "var(--gold)",
          marginBottom: 8,
          letterSpacing: "0.05em",
        }}
      >
        What do you want to feel?
      </h1>
      <p style={{ color: "var(--cream-dim)", marginBottom: 32, fontSize: "15px" }}>
        Select effects to find matching strains. Our ML model predicts the best matches.
      </p>

      {/* Effect Picker */}
      <section style={{ marginBottom: 32 }}>
        {/* Positive */}
        <div style={{ marginBottom: 16 }}>
          <h3 style={{ color: "var(--cream-dim)", fontSize: "12px", marginBottom: 8, letterSpacing: "0.1em", textTransform: "uppercase" }}>
            Positive
          </h3>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {positive.map((e) => (
              <EffectChip
                key={e.name}
                name={e.name}
                category="positive"
                selected={selectedEffects.includes(e.name)}
                onToggle={() => toggleEffect(e.name)}
              />
            ))}
          </div>
        </div>

        {/* Medical */}
        <div style={{ marginBottom: 16 }}>
          <h3 style={{ color: "var(--cream-dim)", fontSize: "12px", marginBottom: 8, letterSpacing: "0.1em", textTransform: "uppercase" }}>
            Medical
          </h3>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {medical.map((e) => (
              <EffectChip
                key={e.name}
                name={e.name}
                category="medical"
                selected={selectedEffects.includes(e.name)}
                onToggle={() => toggleEffect(e.name)}
              />
            ))}
          </div>
        </div>

        {/* Negative (collapsed by default) */}
        <div>
          <button
            type="button"
            onClick={() => setShowNegative(!showNegative)}
            style={{
              color: "var(--cream-faint)",
              fontSize: "12px",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: 0,
              marginBottom: 8,
              fontFamily: "var(--font-body)",
            }}
          >
            {showNegative ? "▾" : "▸"} Negative / Side Effects
          </button>
          {showNegative && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {negative.map((e) => (
                <EffectChip
                  key={e.name}
                  name={e.name}
                  category="negative"
                  selected={selectedEffects.includes(e.name)}
                  onToggle={() => toggleEffect(e.name)}
                />
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Filters row */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          marginBottom: 24,
          flexWrap: "wrap",
        }}
      >
        {/* Type filter pills */}
        <div style={{ display: "flex", gap: 4 }}>
          {TYPE_OPTIONS.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setSelectedType(t)}
              style={{
                padding: "6px 16px",
                borderRadius: "20px",
                border: `1px solid ${
                  selectedType === t ? "var(--gold)" : "var(--border)"
                }`,
                background: selectedType === t ? "rgba(212,168,67,0.12)" : "transparent",
                color: selectedType === t ? "var(--gold)" : "var(--cream-dim)",
                fontSize: "13px",
                fontFamily: "var(--font-body)",
                cursor: "pointer",
                textTransform: "capitalize",
                transition: "all 150ms",
              }}
            >
              {t}
            </button>
          ))}
        </div>

        {/* AI Summaries toggle */}
        {selectedEffects.length > 0 && (
          <button
            type="button"
            onClick={() => setShowSummaries(!showSummaries)}
            style={{
              padding: "6px 12px",
              borderRadius: "20px",
              border: `1px solid ${showSummaries ? "var(--gold-dim)" : "var(--border)"}`,
              background: showSummaries ? "rgba(212,168,67,0.08)" : "transparent",
              color: showSummaries ? "var(--gold)" : "var(--cream-faint)",
              fontSize: "12px",
              fontFamily: "var(--font-body)",
              cursor: "pointer",
              transition: "all 150ms",
            }}
          >
            {showSummaries ? "\u2726 " : ""}AI Summaries
          </button>
        )}

        {/* Selection summary */}
        {selectedEffects.length > 0 && (
          <span
            className="font-data"
            style={{ fontSize: "12px", color: "var(--cream-faint)" }}
          >
            {selectedEffects.length} effect{selectedEffects.length > 1 ? "s" : ""} selected
          </span>
        )}

        {selectedEffects.length > 0 && (
          <button
            type="button"
            onClick={() => setSelectedEffects([])}
            style={{
              fontSize: "12px",
              color: "var(--cream-faint)",
              background: "none",
              border: "none",
              cursor: "pointer",
              textDecoration: "underline",
              fontFamily: "var(--font-body)",
            }}
          >
            Clear all
          </button>
        )}
      </div>

      {/* Results */}
      <section>
        {loading ? (
          <div className="strain-grid">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="skeleton" style={{ height: 120, borderRadius: 8 }} />
            ))}
          </div>
        ) : results.length > 0 ? (
          <div className="strain-grid">
            {results.map((strain, i) => (
              <StrainCard
                key={strain.name}
                strain={strain}
                score={strain.score}
                onCompare={handleCompare}
                animationDelay={`${i * 50}ms`}
              />
            ))}
          </div>
        ) : (
          <div
            style={{
              textAlign: "center",
              padding: "48px 0",
              color: "var(--cream-faint)",
              fontSize: "14px",
            }}
          >
            No strains found matching your criteria.
          </div>
        )}
      </section>
    </div>
  );
}
