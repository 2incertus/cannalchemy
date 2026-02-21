"""Pluggable LLM client with provider fallback for strain explanations."""
import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

# Prompt templates
FULL_EXPLANATION_PROMPT = """You are a cannabis scientist explaining strain effects to an informed consumer.
Given this strain's chemistry and predicted effects, explain WHY these effects
occur at the molecular level. Be specific about which terpenes/cannabinoids
drive which effects and mention receptor interactions when available.

Strain: {name} ({strain_type})
Terpenes: {terpenes}
Cannabinoids: {cannabinoids}
Top predicted effects: {effects}
Receptor pathways: {pathways}

Write 2-4 sentences. Use an accessible but scientific tone — like a well-informed
budtender with a biochemistry background."""

SUMMARY_PROMPT = """Summarize this strain's key effect in one sentence (max 20 words).
Strain: {name}, dominant terpene: {dominant_terpene}, top effect: {top_effect} ({top_prob}%)"""


class LLMClient:
    """Pluggable LLM client. Tries primary (Z.AI/Anthropic-compatible), falls back to Ollama."""

    def __init__(
        self,
        primary_url: str,
        primary_model: str,
        primary_key: str,
        fallback_url: str | None = None,
        fallback_model: str | None = None,
        primary_timeout: float = 10.0,
        fallback_timeout: float = 15.0,
    ):
        self.primary_url = primary_url
        self.primary_model = primary_model
        self.primary_key = primary_key
        self.fallback_url = fallback_url
        self.fallback_model = fallback_model
        self.primary_timeout = primary_timeout
        self.fallback_timeout = fallback_timeout
        self._rate_limited_until: float = 0  # timestamp when rate limit expires

    @classmethod
    def from_env(cls) -> "LLMClient | None":
        """Create from environment variables. Returns None if primary not configured."""
        primary_url = os.environ.get("CANNALCHEMY_LLM_PRIMARY_URL")
        primary_key = os.environ.get("CANNALCHEMY_LLM_PRIMARY_KEY")
        if not primary_url or not primary_key:
            return None
        return cls(
            primary_url=primary_url,
            primary_model=os.environ.get("CANNALCHEMY_LLM_PRIMARY_MODEL", "glm-4.7"),
            primary_key=primary_key,
            fallback_url=os.environ.get("CANNALCHEMY_LLM_FALLBACK_URL"),
            fallback_model=os.environ.get("CANNALCHEMY_LLM_FALLBACK_MODEL", "llama3.2"),
        )

    def _format_strain_data(self, strain_data: dict) -> dict:
        """Extract formatted strings from strain_data for prompt interpolation."""
        compositions = strain_data.get("compositions", [])
        terpenes = [c for c in compositions if c.get("type") == "terpene"]
        cannabinoids = [c for c in compositions if c.get("type") == "cannabinoid"]
        effects = strain_data.get("predicted_effects", [])
        pathways = strain_data.get("pathways", [])

        return {
            "name": strain_data.get("name", "Unknown"),
            "strain_type": strain_data.get("strain_type", "hybrid"),
            "terpenes": ", ".join(
                f"{t['molecule']} ({t['percentage']:.2f}%)" for t in terpenes[:5]
            ) or "none reported",
            "cannabinoids": ", ".join(
                f"{c['molecule'].upper()} ({c['percentage']:.1f}%)" for c in cannabinoids
            ) or "none reported",
            "effects": ", ".join(
                f"{e['name']} ({e['probability']:.0%}, {e.get('confidence', 'medium')} confidence)"
                for e in effects[:5]
            ) or "none predicted",
            "pathways": ", ".join(
                f"{p['molecule']} → {p['receptor']}" + (f" (Ki={p['ki_nm']:.0f}nM)" if p.get("ki_nm") else "")
                for p in pathways[:5]
            ) or "no pathway data",
            "dominant_terpene": terpenes[0]["molecule"] if terpenes else "unknown",
            "top_effect": effects[0]["name"] if effects else "unknown",
            "top_prob": f"{effects[0]['probability'] * 100:.0f}" if effects else "0",
        }

    def _call_primary(self, prompt: str) -> str | None:
        """Call primary provider (Anthropic-compatible API)."""
        if time.time() < self._rate_limited_until:
            logger.debug("Primary rate-limited, skipping")
            return None
        try:
            resp = httpx.post(
                self.primary_url,
                headers={
                    "x-api-key": self.primary_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.primary_model,
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=self.primary_timeout,
            )
            if resp.status_code == 429:
                self._rate_limited_until = time.time() + 60
                logger.warning("Primary rate-limited for 60s")
                return None
            resp.raise_for_status()
            data = resp.json()
            text = data.get("content", [{}])[0].get("text", "").strip()
            return text if text and len(text) < 2000 else None
        except (httpx.TimeoutException, httpx.HTTPStatusError, Exception) as e:
            logger.warning("Primary LLM failed: %s", e)
            return None

    def _call_fallback(self, prompt: str) -> str | None:
        """Call fallback provider (Ollama API)."""
        if not self.fallback_url:
            return None
        try:
            resp = httpx.post(
                f"{self.fallback_url}/api/generate",
                json={
                    "model": self.fallback_model,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=self.fallback_timeout,
            )
            resp.raise_for_status()
            text = resp.json().get("response", "").strip()
            return text if text and len(text) < 2000 else None
        except (httpx.TimeoutException, httpx.HTTPStatusError, Exception) as e:
            logger.warning("Fallback LLM failed: %s", e)
            return None

    def _generate(self, prompt: str) -> tuple[str | None, str | None]:
        """Try primary, then fallback. Returns (text, provider_name)."""
        text = self._call_primary(prompt)
        if text:
            return text, "zai"
        text = self._call_fallback(prompt)
        if text:
            return text, "ollama"
        return None, None

    def explain_strain(self, strain_data: dict) -> tuple[str | None, str | None]:
        """Generate 2-4 sentence explanation. Returns (text, provider)."""
        fmt = self._format_strain_data(strain_data)
        prompt = FULL_EXPLANATION_PROMPT.format(**fmt)
        return self._generate(prompt)

    def summarize_strain(self, strain_data: dict) -> tuple[str | None, str | None]:
        """Generate 1-line summary. Returns (text, provider)."""
        fmt = self._format_strain_data(strain_data)
        prompt = SUMMARY_PROMPT.format(**fmt)
        return self._generate(prompt)
