import { useEffect, useState, useRef } from "react";
import { Link } from "react-router-dom";
import { Beaker, Search, GitBranch, BarChart3 } from "lucide-react";
import HeroRadar from "../charts/HeroRadar";
import { fetchStats } from "../lib/api";

const FEATURES = [
  {
    icon: Search,
    title: "Predict",
    desc: "Enter chemistry, see effects. XGBoost models trained on thousands of strain profiles predict how a chemical fingerprint translates to experience.",
  },
  {
    icon: GitBranch,
    title: "Trace",
    desc: "Follow molecules through receptors to effects. Interactive knowledge graphs reveal the pharmacological pathways behind every strain.",
  },
  {
    icon: BarChart3,
    title: "Compare",
    desc: "Side-by-side terpene fingerprints, effect predictions, and molecular pathway overlays. See exactly what makes two strains different.",
  },
];

export default function Landing() {
  const [stats, setStats] = useState(null);
  const featuresRef = useRef(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    fetchStats().then(setStats).catch(() => {});
  }, []);

  useEffect(() => {
    const el = featuresRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          obs.disconnect();
        }
      },
      { threshold: 0.15 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  return (
    <div className="page">
      {/* Hero */}
      <section
        className="relative flex flex-col items-center justify-center text-center overflow-hidden"
        style={{ minHeight: "100vh" }}
      >
        <HeroRadar size={520} opacity={0.07} />

        <div className="relative z-10 flex flex-col items-center gap-6 px-4">
          {/* Alchemist icon */}
          <div
            className="text-5xl"
            style={{
              filter: "drop-shadow(0 0 24px rgba(212,168,67,0.3))",
              animation: "glow-pulse 4s ease-in-out infinite",
            }}
          >
            <Beaker size={56} style={{ color: "var(--gold)" }} strokeWidth={1.5} />
          </div>

          {/* Title */}
          <h1
            className="font-display text-4xl md:text-5xl lg:text-6xl font-light"
            style={{
              color: "var(--gold)",
              letterSpacing: "0.2em",
            }}
          >
            CANNALCHEMY
          </h1>

          {/* Subtitle */}
          <p
            className="text-lg md:text-xl italic max-w-md"
            style={{ color: "var(--cream-dim)", fontFamily: "var(--font-body)" }}
          >
            The science behind how you feel
          </p>

          {/* CTA */}
          <Link to="/explore" className="btn-gold mt-4" style={{ textDecoration: "none" }}>
            Explore Effects →
          </Link>

          {/* Stats */}
          <p
            className="font-data text-sm mt-8"
            style={{ color: "var(--cream-faint)", letterSpacing: "0.05em" }}
          >
            {stats
              ? `${stats.total_strains?.toLocaleString()} strains · ${stats.molecules} molecules · ${stats.effects} effects`
              : "5,000+ strains · 27 molecules · 51 effects"}
          </p>
        </div>

        {/* Scroll hint */}
        <div
          className="absolute bottom-8 left-1/2 -translate-x-1/2"
          style={{
            color: "var(--cream-faint)",
            animation: "bounce-subtle 2.5s ease-in-out infinite",
          }}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M7 10l5 5 5-5" />
          </svg>
        </div>
      </section>

      {/* Feature cards */}
      <section
        ref={featuresRef}
        className="max-w-5xl mx-auto px-6 py-24 grid grid-cols-1 md:grid-cols-3 gap-8"
      >
        {FEATURES.map((f, i) => (
          <div
            key={f.title}
            className={`card p-8 flex flex-col gap-4 ${visible ? "animate-fade-in-up" : ""}`}
            style={{ animationDelay: visible ? `${i * 120}ms` : undefined }}
          >
            <f.icon size={28} style={{ color: "var(--gold)" }} strokeWidth={1.5} />
            <h3
              className="font-display text-xl"
              style={{ color: "var(--cream)" }}
            >
              {f.title}
            </h3>
            <p className="text-sm leading-relaxed" style={{ color: "var(--cream-dim)" }}>
              {f.desc}
            </p>
          </div>
        ))}
      </section>

      {/* Glow pulse + bounce animations */}
      <style>{`
        @keyframes glow-pulse {
          0%, 100% { filter: drop-shadow(0 0 16px rgba(212,168,67,0.2)); }
          50% { filter: drop-shadow(0 0 32px rgba(212,168,67,0.4)); }
        }
        @keyframes bounce-subtle {
          0%, 100% { transform: translateX(-50%) translateY(0); }
          50% { transform: translateX(-50%) translateY(6px); }
        }
      `}</style>
    </div>
  );
}
