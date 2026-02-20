import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Menu, X } from "lucide-react";

const NAV_LINKS = [
  { to: "/explore", label: "Explore" },
  { to: "/compare", label: "Compare" },
  { to: "/graph", label: "Graph" },
  { to: "/quality", label: "Data" },
];

export default function Nav() {
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);

  return (
    <nav
      className="fixed top-0 left-0 right-0 z-50 h-16 flex items-center justify-between px-6"
      style={{
        background: "var(--bg-void)",
        borderBottom: "1px solid var(--border)",
      }}
    >
      {/* Logo */}
      <Link
        to="/"
        className="font-display text-lg tracking-[0.15em] no-underline"
        style={{ color: "var(--gold)", textDecoration: "none" }}
      >
        ⚗ CANNALCHEMY
      </Link>

      {/* Desktop links */}
      <div className="hidden md:flex items-center gap-8">
        {NAV_LINKS.map(({ to, label }) => (
          <Link
            key={to}
            to={to}
            className="text-sm tracking-wide no-underline transition-colors duration-200"
            style={{
              color: pathname === to ? "var(--gold)" : "var(--cream-dim)",
              borderBottom:
                pathname === to ? "2px solid var(--gold)" : "2px solid transparent",
              paddingBottom: "2px",
              fontFamily: "var(--font-body)",
              textDecoration: "none",
            }}
          >
            {label}
          </Link>
        ))}
      </div>

      {/* Mobile hamburger */}
      <button
        className="md:hidden p-2"
        onClick={() => setOpen(!open)}
        style={{ color: "var(--cream)", background: "none", border: "none", cursor: "pointer" }}
        aria-label="Toggle menu"
      >
        {open ? <X size={22} /> : <Menu size={22} />}
      </button>

      {/* Mobile overlay */}
      {open && (
        <div
          className="fixed inset-0 top-16 z-40 flex flex-col items-center pt-16 gap-8"
          style={{ background: "var(--bg-dark)" }}
        >
          {NAV_LINKS.map(({ to, label }) => (
            <Link
              key={to}
              to={to}
              onClick={() => setOpen(false)}
              className="font-display text-2xl tracking-wide no-underline"
              style={{
                color: pathname === to ? "var(--gold)" : "var(--cream-dim)",
                textDecoration: "none",
              }}
            >
              {label}
            </Link>
          ))}
        </div>
      )}
    </nav>
  );
}
