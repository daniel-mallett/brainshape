from typing import Any

from neo4j import GraphDatabase

from brain.config import settings


class GraphDB:
    def __init__(self):
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def close(self):
        self._driver.close()

    def query(self, cypher: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Run a Cypher query and return results as list of dicts."""
        with self._driver.session() as session:
            result = session.run(cypher, parameters or {})  # type: ignore[arg-type]
            return [record.data() for record in result]

    def bootstrap_schema(self):
        """Create constraints and indexes if they don't exist."""
        statements = [
            "CREATE CONSTRAINT note_path IF NOT EXISTS FOR (n:Note) REQUIRE n.path IS UNIQUE",
            "CREATE CONSTRAINT tag_name IF NOT EXISTS FOR (t:Tag) REQUIRE t.name IS UNIQUE",
            "CREATE CONSTRAINT memory_id IF NOT EXISTS FOR (m:Memory) REQUIRE m.id IS UNIQUE",
            "CREATE INDEX note_title IF NOT EXISTS FOR (n:Note) ON (n.title)",
            "CREATE FULLTEXT INDEX note_content IF NOT EXISTS"
            " FOR (n:Note) ON EACH [n.content, n.title]",
        ]
        for stmt in statements:
            self.query(stmt)
