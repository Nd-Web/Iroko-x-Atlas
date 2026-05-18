"""
Azure Blob Storage — raw-documents container.
Uploads ingested files so the original source is preserved alongside the index.
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER", "raw-documents")

_service_client = None


def _get_service_client():
    global _service_client
    if _service_client is not None:
        return _service_client

    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        logger.warning("AZURE_STORAGE_CONNECTION_STRING not set — blob uploads disabled.")
        return None

    try:
        from azure.storage.blob import BlobServiceClient
        _service_client = BlobServiceClient.from_connection_string(conn_str)
        logger.info("Azure Blob Storage client initialised.")
        return _service_client
    except Exception as e:
        logger.error(f"Failed to create Blob Storage client: {e}")
        return None


async def upload_document(
    file_path: str,
    document_id: str,
    filename: str,
    content_type: str = "application/octet-stream",
) -> Optional[str]:
    """
    Upload a file to the raw-documents container.
    Blob name: <document_id>/<original_filename>  (keeps originals organised by doc ID)
    Returns the blob URL on success, None on failure.
    """
    service = _get_service_client()
    if service is None:
        return None

    blob_name = f"{document_id}/{filename}"
    try:
        from azure.storage.blob import ContentSettings
        blob_client = service.get_blob_client(container=CONTAINER_NAME, blob=blob_name)
        with open(file_path, "rb") as f:
            blob_client.upload_blob(
                f,
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type),
            )
        url = blob_client.url
        logger.info(f"Blob uploaded: {blob_name} → {url}")
        return url
    except Exception as e:
        logger.error(f"Blob upload failed for '{blob_name}': {e}")
        return None


async def download_document(document_id: str, filename: str, dest_path: str) -> bool:
    """Download a blob to a local file. Returns True on success."""
    service = _get_service_client()
    if service is None:
        return False
    try:
        blob_name = f"{document_id}/{filename}"
        blob_client = service.get_blob_client(container=CONTAINER_NAME, blob=blob_name)
        with open(dest_path, "wb") as f:
            stream = blob_client.download_blob()
            stream.readinto(f)
        return True
    except Exception as e:
        logger.error(f"Blob download failed for '{document_id}/{filename}': {e}")
        return False


async def delete_document(document_id: str, filename: str) -> bool:
    """Delete a blob when a document is removed from the system."""
    service = _get_service_client()
    if service is None:
        return False
    try:
        blob_name = f"{document_id}/{filename}"
        blob_client = service.get_blob_client(container=CONTAINER_NAME, blob=blob_name)
        blob_client.delete_blob()
        logger.info(f"Blob deleted: {blob_name}")
        return True
    except Exception as e:
        logger.error(f"Blob delete failed: {e}")
        return False
