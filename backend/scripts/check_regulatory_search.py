"""Read-only live check: one fixed public query, optionally fetch its official sources.

Run from backend: python scripts/check_regulatory_search.py [--fetch]
No model calls, database writes, ingestion or email sends. Uses local .env.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.brightdata import bright_data_client
from services.regulatory_discovery import discover


async def run(fetch):
    try:
        result = await discover("NDPC", "NDPC data protection requirements")
        print(json.dumps(result, indent=2))
        if result["check"]["status"] != "checked" or not result["candidates"]:
            return 1
        if fetch:
            from services.regulatory_research import research
            report = await research("What are the latest NDPC data protection requirements?")
            evidence_urls = {s["provenance"]["source_url"] for s in report["sources"]}
            discovered_sources_read = evidence_urls & {c["url"] for c in result["candidates"]}
            print(json.dumps({
                "source_count": len(report["sources"]), "checks": report["checks"],
                "discovery_checks": report.get("discovery_checks", []),
                "evidence_urls": sorted(evidence_urls),
                "discovered_sources_read": sorted(discovered_sources_read),
            }, indent=2))
            if not discovered_sources_read:
                return 1
        return 0
    finally:
        await bright_data_client._close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true")
    sys.exit(asyncio.run(run(parser.parse_args().fetch)))
