"""
Azure OpenAI embeddings — text-embedding-3-large, 3072 dimensions.
Used by the indexing pipeline (batch) and search (single query).
"""
import os
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
EMBEDDING_DIMS = 3072
_BATCH_SIZE = 16  # Azure OpenAI limit for text-embedding-3-large


async def get_embedding(text: str) -> Optional[List[float]]:
    """Return a single 3072-dim embedding, or None if the service is unavailable."""
    results = await get_embeddings_batch([text])
    return results[0]


async def get_embeddings_batch(texts: List[str]) -> List[Optional[List[float]]]:
    """
    Return embeddings for a list of texts.
    Sends requests in batches of 16 to stay within Azure OpenAI limits.
    Any individual failure returns None for that slot rather than raising.
    """
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")

    if not endpoint or not api_key:
        logger.warning("Azure OpenAI not configured — embeddings unavailable.")
        return [None] * len(texts)

    try:
        from openai import AsyncAzureOpenAI
        client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
        )
    except Exception as e:
        logger.error(f"Failed to create OpenAI client: {e}")
        return [None] * len(texts)

    all_embeddings: List[Optional[List[float]]] = []

    for i in range(0, len(texts), _BATCH_SIZE):
        batch = [t[:8000] for t in texts[i : i + _BATCH_SIZE]]
        try:
            response = await client.embeddings.create(
                input=batch,
                model=EMBEDDING_DEPLOYMENT,
            )
            sorted_data = sorted(response.data, key=lambda x: x.index)
            all_embeddings.extend(item.embedding for item in sorted_data)
        except Exception as e:
            logger.error(f"Embedding batch {i//16} failed: {e}")
            all_embeddings.extend([None] * len(batch))

    return all_embeddings
