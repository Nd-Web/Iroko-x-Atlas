"""
Cosmos DB Gremlin knowledge graph service.
Writes document and entity vertices to iroko-knowledge-graph so the
GraphRAG layer has a queryable entity store.

Connection uses the primary key from Key Vault (cosmos-primary-key).
Endpoint format stored in vault: irokograph2026.gremlin.cosmos.azure.com
"""
import os
import logging
import concurrent.futures
from typing import Optional

logger = logging.getLogger(__name__)

# Gremlin calls block on their own internal event loop; running them from
# inside uvloop raises "Cannot run the event loop while another loop is
# running". A dedicated single-threaded executor keeps gremlin off the
# main event loop entirely.
_gremlin_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="gremlin"
)

DATABASE  = os.getenv("COSMOS_DATABASE", "iroko-graph-db")
GRAPH     = os.getenv("COSMOS_GRAPH",    "iroko-knowledge-graph")

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client

    raw_endpoint = os.getenv("COSMOS_GREMLIN_ENDPOINT", "")
    key          = os.getenv("COSMOS_PRIMARY_KEY", "")

    if not raw_endpoint or not key:
        logger.warning("Cosmos DB Gremlin not configured — graph writes disabled.")
        return None

    # Normalise endpoint: strip protocol/port if present, keep hostname only
    hostname = (
        raw_endpoint
        .replace("https://", "")
        .replace("wss://", "")
        .split(":")[0]
        .rstrip("/")
    )
    ws_url = f"wss://{hostname}:443/"

    try:
        from gremlin_python.driver import client as gremlin_module, serializer

        _client = gremlin_module.Client(
            ws_url,
            "g",
            username=f"/dbs/{DATABASE}/colls/{GRAPH}",
            password=key,
            message_serializer=serializer.GraphSONSerializersV2d0(),
        )
        logger.info(f"Cosmos DB Gremlin connected: {ws_url}")
        return _client
    except ImportError:
        logger.warning("gremlinpython not installed — graph writes disabled.")
        return None
    except Exception as e:
        logger.error(f"Failed to connect to Cosmos DB Gremlin: {e}")
        return None


def _submit(fn):
    """Run fn in the gremlin thread pool when called from an async context."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return _gremlin_executor.submit(fn).result(timeout=30)
    except RuntimeError:
        pass
    return fn()


def _run(query: str) -> bool:
    client = _get_client()
    if client is None:
        return False

    def _exec():
        try:
            result_set = client.submitAsync(query).result()
            # gremlinpython does not raise on server-side errors — check the
            # raw result for Cosmos DB error status codes.
            for item in result_set:
                if isinstance(item, dict) and item.get("status", {}).get("code", 200) >= 400:
                    logger.error(f"Gremlin server error: {item}\nQuery: {query[:200]}")
                    return False
            return True
        except Exception as e:
            logger.error(f"Gremlin query failed: {e}\nQuery: {query[:200]}")
            return False

    return _submit(_exec)


def _esc(s: str) -> str:
    return s.replace("'", "\\'").replace('"', '\\"')


# ── Public API ────────────────────────────────────────────────────────────────

def upsert_document_node(
    document_id: str,
    title: str,
    doc_type: str,
    department: str,
    blob_url: str = "",
) -> bool:
    """
    Add or update a document vertex in the knowledge graph.
    Uses Cosmos DB's upsert pattern (fold/coalesce) to be idempotent.
    """
    q = (
        f"g.V().has('document','docId','{document_id}')"
        f".fold()"
        f".coalesce("
        f"unfold(),"
        f"addV('document')"
        f".property('pk','{document_id}')"
        f".property('docId','{document_id}')"
        f")"
        f".property('title','{_esc(title)}')"
        f".property('docType','{_esc(doc_type)}')"
        f".property('department','{_esc(department)}')"
        f".property('blobUrl','{_esc(blob_url)}')"
    )
    ok = _run(q)
    if ok:
        logger.info(f"Graph: upserted document node '{document_id}'")
    return ok


def upsert_entity_node(
    entity_id: str,
    label: str,
    name: str,
    entity_type: str = "",
) -> bool:
    """Add or update a named-entity vertex (contract, organisation, regulation, etc.)."""
    q = (
        f"g.V().has('{_esc(label)}','entityId','{entity_id}')"
        f".fold()"
        f".coalesce("
        f"unfold(),"
        f"addV('{_esc(label)}')"
        f".property('pk','{entity_id}')"
        f".property('entityId','{entity_id}')"
        f")"
        f".property('name','{_esc(name)}')"
        f".property('entityType','{_esc(entity_type)}')"
    )
    return _run(q)


def upsert_edge(from_id: str, to_id: str, relationship: str) -> bool:
    """Add a directed edge between two vertices (idempotent check by outE label)."""
    q = (
        f"g.V().has('id','{from_id}').as('a')"
        f".V().has('id','{to_id}').as('b')"
        f".coalesce("
        f"select('a').outE('{_esc(relationship)}').where(inV().as('b')),"
        f"addE('{_esc(relationship)}').from('a').to('b')"
        f")"
    )
    return _run(q)


# ── Read API ─────────────────────────────────────────────────────────────────

def query_related_documents(document_id: str, max_depth: int = 2) -> list:
    """Find documents related to a given document through entity connections."""
    client = _get_client()
    if client is None:
        return []

    def _exec():
        try:
            q = (
                f"g.V().has('document','docId','{_esc(document_id)}')"
                f".repeat(both().simplePath()).times({max_depth})"
                f".hasLabel('document')"
                f".dedup()"
                f".valueMap('docId','title','department','docType')"
                f".limit(10)"
            )
            result = client.submitAsync(q).result()
            docs = []
            for item in result:
                def _first(val):
                    return val[0] if isinstance(val, list) else val
                docs.append({
                    "document_id": _first(item.get("docId", "")),
                    "title": _first(item.get("title", "")),
                    "department": _first(item.get("department", "")),
                    "doc_type": _first(item.get("docType", "")),
                })
            return docs
        except Exception as e:
            logger.error(f"Graph query failed for document '{document_id}': {e}")
            return []

    return _submit(_exec)


def query_entity_documents(entity_name: str) -> list:
    """Find all documents connected to a named entity."""
    client = _get_client()
    if client is None:
        return []

    def _exec():
        try:
            q = (
                f"g.V().has('name','{_esc(entity_name)}')"
                f".both()"
                f".hasLabel('document')"
                f".dedup()"
                f".valueMap('docId','title','department')"
                f".limit(10)"
            )
            result = client.submitAsync(q).result()
            docs = []
            for item in result:
                def _first(val):
                    return val[0] if isinstance(val, list) else val
                docs.append({
                    "document_id": _first(item.get("docId", "")),
                    "title": _first(item.get("title", "")),
                })
            return docs
        except Exception as e:
            logger.error(f"Graph query failed for entity '{entity_name}': {e}")
            return []

    return _submit(_exec)


def query_entities_for_document(document_id: str) -> list:
    """Find all entities connected to a document."""
    client = _get_client()
    if client is None:
        return []

    def _exec():
        try:
            q = (
                f"g.V().has('document','docId','{_esc(document_id)}')"
                f".both()"
                f".not_(hasLabel('document'))"
                f".dedup()"
                f".valueMap('name','entityType','entityId')"
                f".limit(20)"
            )
            result = client.submitAsync(q).result()
            entities = []
            for item in result:
                def _first(val):
                    return val[0] if isinstance(val, list) else val
                entities.append({
                    "entity_id": _first(item.get("entityId", "")),
                    "name": _first(item.get("name", "")),
                    "type": _first(item.get("entityType", "")),
                })
            return entities
        except Exception as e:
            logger.error(f"Graph query failed for document '{document_id}': {e}")
            return []

    return _submit(_exec)
