"""Resource-bounded parser subprocess. Never receives cloud credentials as input."""

import json
import os
import sys


def main():
    if sys.platform != "win32":
        import resource

        limit = int(os.getenv("EXTRACTION_MEMORY_MB", "768")) * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
        resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))
    from ingestion.extraction import native_pages
    from ingestion.validation import validate_file

    validate_file(sys.argv[1], "original." + sys.argv[2])
    pages = native_pages(sys.argv[1], sys.argv[2])
    content = json.dumps(pages, ensure_ascii=True)
    if len(content) > 32 * 1024 * 1024:
        raise ValueError("Extracted content exceeds output limit")
    print(content)


if __name__ == "__main__":
    main()
