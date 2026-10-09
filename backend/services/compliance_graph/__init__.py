"""
The compliance knowledge graph.

Requirements found in regulations, how instruments relate, and each
workspace's controls, evidence and decisions, connected so Iroko can answer
"what does this change affect?", "what is not yet evidenced in our records?"
and "who owns this?".

Modules must stay importable in the ingestion worker image, which has no
fastapi: permission problems are plain exceptions (permissions.py) mapped to
HTTP responses only in routes/compliance_graph.py.
"""
