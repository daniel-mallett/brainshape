import logging
from pathlib import Path
from typing import Any

from surrealdb import Surreal
from surrealdb.data.types.record_id import RecordID

from brain.config import settings

logger = logging.getLogger(__name__)


def _convert_record_ids(obj: Any) -> Any:
    """Recursively convert RecordID objects to strings."""
    if isinstance(obj, RecordID):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _convert_record_ids(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_record_ids(item) for item in obj]
    return obj


# Tables that are internal implementation details, not user-visible
_INTERNAL_EDGE_TABLES = frozenset({"from_document"})
_CORE_NODE_TABLES = frozenset({"note", "tag", "memory", "chunk"})


class GraphDB:
    def __init__(self):
        db_path = Path(settings.surrealdb_path).expanduser()
        db_path.mkdir(parents=True, exist_ok=True)
        try:
            self._conn = Surreal(f"surrealkv://{db_path}")
            self._conn.connect()
            self._conn.use("brain", "main")
        except Exception as e:
            logger.error("Failed to open SurrealDB at %s: %s", db_path, e)
            raise ConnectionError(f"Cannot open SurrealDB: {e}") from e

    def close(self):
        self._conn.close()

    def query(self, sql: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Run a SurrealQL query and return results as list of dicts."""
        result = self._conn.query(sql, parameters or {})
        return _convert_record_ids(result)

    def bootstrap_schema(self):
        """Create tables, indexes, and analyzers if they don't exist."""
        statements = [
            # Tables
            "DEFINE TABLE IF NOT EXISTS note SCHEMALESS",
            "DEFINE TABLE IF NOT EXISTS tag SCHEMALESS",
            "DEFINE TABLE IF NOT EXISTS chunk SCHEMALESS",
            "DEFINE TABLE IF NOT EXISTS memory SCHEMALESS",
            # Edge tables
            "DEFINE TABLE IF NOT EXISTS tagged_with TYPE RELATION IN note OUT tag",
            "DEFINE TABLE IF NOT EXISTS links_to TYPE RELATION IN note OUT note",
            "DEFINE TABLE IF NOT EXISTS from_document TYPE RELATION IN chunk OUT note",
            # Unique indexes
            "DEFINE INDEX IF NOT EXISTS note_path ON TABLE note FIELDS path UNIQUE",
            "DEFINE INDEX IF NOT EXISTS tag_name ON TABLE tag FIELDS name UNIQUE",
            "DEFINE INDEX IF NOT EXISTS memory_mid ON TABLE memory FIELDS mid UNIQUE",
            # Property indexes
            "DEFINE INDEX IF NOT EXISTS note_title ON TABLE note FIELDS title",
            "DEFINE INDEX IF NOT EXISTS note_hash ON TABLE note FIELDS content_hash",
            # Fulltext search
            "DEFINE ANALYZER IF NOT EXISTS note_analyzer TOKENIZERS class FILTERS lowercase, ascii",
            "DEFINE INDEX IF NOT EXISTS note_content_ft ON TABLE note "
            "FIELDS content SEARCH ANALYZER note_analyzer BM25",
            "DEFINE INDEX IF NOT EXISTS note_title_ft ON TABLE note "
            "FIELDS title SEARCH ANALYZER note_analyzer BM25",
        ]
        for stmt in statements:
            self.query(stmt)

    def _table_info(self) -> dict[str, str]:
        """Return {table_name: definition_string} from INFO FOR DB."""
        result = self.query("INFO FOR DB")
        if not result:
            return {}
        info = result if isinstance(result, dict) else result[0]
        return info.get("tables", {}) if isinstance(info, dict) else {}

    def get_relation_tables(self, *, exclude_internal: bool = True) -> list[str]:
        """Discover all relation (edge) tables in the database."""
        tables = []
        for name, defn in self._table_info().items():
            if "TYPE RELATION" in str(defn):
                if exclude_internal and name in _INTERNAL_EDGE_TABLES:
                    continue
                tables.append(name)
        return sorted(tables)

    def get_custom_node_tables(self) -> list[str]:
        """Discover non-core, non-relation tables (e.g. person, project)."""
        tables = []
        for name, defn in self._table_info().items():
            if "TYPE RELATION" in str(defn):
                continue
            if name in _CORE_NODE_TABLES:
                continue
            tables.append(name)
        return sorted(tables)
