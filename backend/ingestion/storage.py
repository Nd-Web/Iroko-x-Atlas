"""Private immutable originals using Iroko's existing blob container."""

import asyncio
from pathlib import Path

from services.blob_storage import CONTAINER_NAME, _get_service_client


def _put(path, document_id, filename):
    import mimetypes

    from azure.core.exceptions import ResourceExistsError
    from azure.storage.blob import ContentSettings

    service = _get_service_client()
    if service is None:
        raise RuntimeError("Azure Blob Storage must be configured before accepting documents")
    blob = service.get_blob_client(CONTAINER_NAME, f"{document_id}/{filename}")
    try:
        with Path(path).open("rb") as stream:
            blob.upload_blob(
                stream,
                overwrite=False,
                content_settings=ContentSettings(
                    content_type=mimetypes.guess_type(filename)[0] or "application/octet-stream"
                ),
            )
    except ResourceExistsError:
        # This ID was freshly allocated; treating an existing object as success
        # could accept different bytes under a reused identity.
        raise RuntimeError("Original blob identity already exists; retry the upload") from None
    return blob.url


async def preserve(path, document_id, filename):
    return await asyncio.to_thread(_put, path, document_id, filename)
