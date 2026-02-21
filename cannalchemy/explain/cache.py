"""SQLite cache for LLM-generated strain explanations."""
import logging
import sqlite3

logger = logging.getLogger(__name__)


class ExplanationCache:
    """Read/write cache for strain explanations, keyed by (strain_id, type, model_version)."""

    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # Ensure table exists (idempotent)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS strain_explanations (
                strain_id INTEGER NOT NULL,
                explanation_type TEXT NOT NULL,
                content TEXT NOT NULL,
                model_version TEXT NOT NULL,
                llm_provider TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (strain_id, explanation_type, model_version)
            )
        """)
        self._conn.commit()

    def get(self, strain_id: int, explanation_type: str, model_version: str) -> dict | None:
        row = self._conn.execute(
            "SELECT content, llm_provider, created_at FROM strain_explanations "
            "WHERE strain_id = ? AND explanation_type = ? AND model_version = ?",
            (strain_id, explanation_type, model_version),
        ).fetchone()
        if not row:
            return None
        return {
            "content": row["content"],
            "llm_provider": row["llm_provider"],
            "created_at": row["created_at"],
            "cached": True,
        }

    def put(
        self,
        strain_id: int,
        explanation_type: str,
        model_version: str,
        content: str,
        llm_provider: str,
    ) -> None:
        try:
            self._conn.execute(
                "INSERT OR REPLACE INTO strain_explanations "
                "(strain_id, explanation_type, content, model_version, llm_provider) "
                "VALUES (?, ?, ?, ?, ?)",
                (strain_id, explanation_type, content, model_version, llm_provider),
            )
            self._conn.commit()
        except Exception as e:
            logger.warning("Cache write failed: %s", e)
