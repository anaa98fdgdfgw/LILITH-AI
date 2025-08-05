"""MCP Memory/Knowledge Graph Server."""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from base_server import BaseMCPServer, create_argument_parser
from pathlib import Path
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional
import pickle
import base64


class MemoryServer(BaseMCPServer):
    """Persistent memory and knowledge graph server."""
    
    def __init__(self, port: int = 3005, db_path: str = None):
        super().__init__("memory", port)
        self.db_path = db_path or str(Path.home() / ".lilith" / "memory.db")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_database()
        
        # Register methods
        self.register_method("store", self.store)
        self.register_method("retrieve", self.retrieve)
        self.register_method("delete", self.delete)
        self.register_method("list_keys", self.list_keys)
        self.register_method("search", self.search)
        self.register_method("create_graph_node", self.create_graph_node)
        self.register_method("create_graph_edge", self.create_graph_edge)
        self.register_method("get_graph_node", self.get_graph_node)
        self.register_method("get_graph_neighbors", self.get_graph_neighbors)
        self.register_method("search_graph", self.search_graph)
        self.register_method("get_statistics", self.get_statistics)
        
    def init_database(self):
        """Initialize the database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Key-value store
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER DEFAULT 0,
                tags TEXT
            )
        """)
        
        # Knowledge graph nodes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS graph_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL,
                properties TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Knowledge graph edges
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS graph_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relationship TEXT NOT NULL,
                properties TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES graph_nodes(node_id),
                FOREIGN KEY (target_id) REFERENCES graph_nodes(node_id)
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_tags ON memory(tags)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_graph_edges_source ON graph_edges(source_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_graph_edges_target ON graph_edges(target_id)")
        
        conn.commit()
        conn.close()
        
    def _serialize_value(self, value: Any) -> tuple[str, str]:
        """Serialize a value for storage."""
        if isinstance(value, str):
            return value, "string"
        elif isinstance(value, (int, float)):
            return str(value), "number"
        elif isinstance(value, bool):
            return str(value), "boolean"
        elif isinstance(value, (list, dict)):
            return json.dumps(value), "json"
        else:
            # Pickle and base64 encode complex objects
            pickled = pickle.dumps(value)
            return base64.b64encode(pickled).decode(), "pickle"
            
    def _deserialize_value(self, value: str, value_type: str) -> Any:
        """Deserialize a stored value."""
        if value_type == "string":
            return value
        elif value_type == "number":
            return float(value) if "." in value else int(value)
        elif value_type == "boolean":
            return value.lower() == "true"
        elif value_type == "json":
            return json.loads(value)
        elif value_type == "pickle":
            return pickle.loads(base64.b64decode(value))
        else:
            return value
            
    async def store(self, key: str, value: Any, tags: List[str] = None) -> Dict[str, Any]:
        """Store a value in memory."""
        try:
            serialized_value, value_type = self._serialize_value(value)
            tags_str = json.dumps(tags) if tags else None
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO memory (key, value, type, tags, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (key, serialized_value, value_type, tags_str))
            
            conn.commit()
            conn.close()
            
            return {"success": True, "key": key, "type": value_type}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def retrieve(self, key: str) -> Dict[str, Any]:
        """Retrieve a value from memory."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT value, type FROM memory WHERE key = ?
            """, (key,))
            
            row = cursor.fetchone()
            if not row:
                conn.close()
                return {"error": "Key not found"}
                
            # Update access count
            cursor.execute("""
                UPDATE memory SET access_count = access_count + 1 WHERE key = ?
            """, (key,))
            
            conn.commit()
            conn.close()
            
            value = self._deserialize_value(row[0], row[1])
            return {"value": value, "type": row[1]}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def delete(self, key: str) -> Dict[str, Any]:
        """Delete a value from memory."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM memory WHERE key = ?", (key,))
            deleted = cursor.rowcount > 0
            
            conn.commit()
            conn.close()
            
            return {"success": deleted}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def list_keys(self, pattern: str = None, tags: List[str] = None) -> Dict[str, Any]:
        """List all keys in memory."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = "SELECT key, type, tags, created_at, updated_at, access_count FROM memory"
            params = []
            
            conditions = []
            if pattern:
                conditions.append("key LIKE ?")
                params.append(f"%{pattern}%")
                
            if tags:
                for tag in tags:
                    conditions.append("tags LIKE ?")
                    params.append(f'%"{tag}"%')
                    
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
                
            cursor.execute(query, params)
            
            keys = []
            for row in cursor.fetchall():
                key_tags = json.loads(row[2]) if row[2] else []
                keys.append({
                    "key": row[0],
                    "type": row[1],
                    "tags": key_tags,
                    "created_at": row[3],
                    "updated_at": row[4],
                    "access_count": row[5]
                })
                
            conn.close()
            return {"keys": keys, "count": len(keys)}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def search(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search memory by key or tags."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT key, value, type, tags FROM memory
                WHERE key LIKE ? OR tags LIKE ?
                ORDER BY access_count DESC, updated_at DESC
                LIMIT ?
            """, (f"%{query}%", f"%{query}%", limit))
            
            results = []
            for row in cursor.fetchall():
                value = self._deserialize_value(row[1], row[2])
                tags = json.loads(row[3]) if row[3] else []
                results.append({
                    "key": row[0],
                    "value": value,
                    "type": row[2],
                    "tags": tags
                })
                
            conn.close()
            return {"results": results, "count": len(results)}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def create_graph_node(self, node_id: str, node_type: str, properties: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a node in the knowledge graph."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            properties_json = json.dumps(properties or {})
            
            cursor.execute("""
                INSERT OR REPLACE INTO graph_nodes (node_id, type, properties, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (node_id, node_type, properties_json))
            
            conn.commit()
            conn.close()
            
            return {"success": True, "node_id": node_id}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def create_graph_edge(self, source_id: str, target_id: str, relationship: str, properties: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create an edge in the knowledge graph."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            properties_json = json.dumps(properties) if properties else None
            
            cursor.execute("""
                INSERT INTO graph_edges (source_id, target_id, relationship, properties)
                VALUES (?, ?, ?, ?)
            """, (source_id, target_id, relationship, properties_json))
            
            edge_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return {"success": True, "edge_id": edge_id}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def get_graph_node(self, node_id: str) -> Dict[str, Any]:
        """Get a node from the knowledge graph."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT type, properties, created_at, updated_at
                FROM graph_nodes WHERE node_id = ?
            """, (node_id,))
            
            row = cursor.fetchone()
            if not row:
                conn.close()
                return {"error": "Node not found"}
                
            properties = json.loads(row[1])
            
            # Get edges
            cursor.execute("""
                SELECT target_id, relationship, properties
                FROM graph_edges WHERE source_id = ?
            """, (node_id,))
            
            outgoing_edges = []
            for edge in cursor.fetchall():
                edge_props = json.loads(edge[2]) if edge[2] else {}
                outgoing_edges.append({
                    "target": edge[0],
                    "relationship": edge[1],
                    "properties": edge_props
                })
                
            cursor.execute("""
                SELECT source_id, relationship, properties
                FROM graph_edges WHERE target_id = ?
            """, (node_id,))
            
            incoming_edges = []
            for edge in cursor.fetchall():
                edge_props = json.loads(edge[2]) if edge[2] else {}
                incoming_edges.append({
                    "source": edge[0],
                    "relationship": edge[1],
                    "properties": edge_props
                })
                
            conn.close()
            
            return {
                "node_id": node_id,
                "type": row[0],
                "properties": properties,
                "created_at": row[2],
                "updated_at": row[3],
                "outgoing_edges": outgoing_edges,
                "incoming_edges": incoming_edges
            }
            
        except Exception as e:
            return {"error": str(e)}
            
    async def get_graph_neighbors(self, node_id: str, relationship: str = None, direction: str = "both") -> Dict[str, Any]:
        """Get neighbors of a node in the knowledge graph."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            neighbors = []
            
            if direction in ["out", "both"]:
                query = """
                    SELECT e.target_id, e.relationship, n.type, n.properties
                    FROM graph_edges e
                    JOIN graph_nodes n ON e.target_id = n.node_id
                    WHERE e.source_id = ?
                """
                params = [node_id]
                
                if relationship:
                    query += " AND e.relationship = ?"
                    params.append(relationship)
                    
                cursor.execute(query, params)
                
                for row in cursor.fetchall():
                    neighbors.append({
                        "node_id": row[0],
                        "relationship": row[1],
                        "type": row[2],
                        "properties": json.loads(row[3]),
                        "direction": "outgoing"
                    })
                    
            if direction in ["in", "both"]:
                query = """
                    SELECT e.source_id, e.relationship, n.type, n.properties
                    FROM graph_edges e
                    JOIN graph_nodes n ON e.source_id = n.node_id
                    WHERE e.target_id = ?
                """
                params = [node_id]
                
                if relationship:
                    query += " AND e.relationship = ?"
                    params.append(relationship)
                    
                cursor.execute(query, params)
                
                for row in cursor.fetchall():
                    neighbors.append({
                        "node_id": row[0],
                        "relationship": row[1],
                        "type": row[2],
                        "properties": json.loads(row[3]),
                        "direction": "incoming"
                    })
                    
            conn.close()
            return {"neighbors": neighbors, "count": len(neighbors)}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def search_graph(self, query: str, node_type: str = None, limit: int = 10) -> Dict[str, Any]:
        """Search the knowledge graph."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            base_query = """
                SELECT node_id, type, properties
                FROM graph_nodes
                WHERE (node_id LIKE ? OR properties LIKE ?)
            """
            params = [f"%{query}%", f"%{query}%"]
            
            if node_type:
                base_query += " AND type = ?"
                params.append(node_type)
                
            base_query += " LIMIT ?"
            params.append(limit)
            
            cursor.execute(base_query, params)
            
            nodes = []
            for row in cursor.fetchall():
                nodes.append({
                    "node_id": row[0],
                    "type": row[1],
                    "properties": json.loads(row[2])
                })
                
            conn.close()
            return {"nodes": nodes, "count": len(nodes)}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def get_statistics(self) -> Dict[str, Any]:
        """Get memory and graph statistics."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Memory stats
            cursor.execute("SELECT COUNT(*) FROM memory")
            memory_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(access_count) FROM memory")
            total_accesses = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT key, access_count FROM memory ORDER BY access_count DESC LIMIT 5")
            most_accessed = [{"key": row[0], "count": row[1]} for row in cursor.fetchall()]
            
            # Graph stats
            cursor.execute("SELECT COUNT(*) FROM graph_nodes")
            node_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM graph_edges")
            edge_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT type, COUNT(*) as count FROM graph_nodes GROUP BY type")
            node_types = {row[0]: row[1] for row in cursor.fetchall()}
            
            cursor.execute("SELECT relationship, COUNT(*) as count FROM graph_edges GROUP BY relationship")
            relationship_types = {row[0]: row[1] for row in cursor.fetchall()}
            
            conn.close()
            
            return {
                "memory": {
                    "total_keys": memory_count,
                    "total_accesses": total_accesses,
                    "most_accessed": most_accessed
                },
                "graph": {
                    "total_nodes": node_count,
                    "total_edges": edge_count,
                    "node_types": node_types,
                    "relationship_types": relationship_types
                }
            }
            
        except Exception as e:
            return {"error": str(e)}


if __name__ == "__main__":
    parser = create_argument_parser("MCP Memory Server")
    parser.add_argument('--db-path', help='Path to database file')
    args = parser.parse_args()
    
    server = MemoryServer(port=args.port, db_path=args.db_path)
    server.run()