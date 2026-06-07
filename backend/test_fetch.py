import asyncio
from services.brightdata import bright_data_client

async def main():
    print("Testing Web Unlocker...")
    try:
        html = await bright_data_client.fetch_url("https://example.com")
        print(f"Success! Fetched {len(html.get('content', ''))} chars. Starts with: {html.get('content', '')[:100]}...")
    except Exception as e:
        print(f"Web Unlocker Failed: {e}")

    print("\nTesting SERP API...")
    try:
        results = await bright_data_client.serp_search("CBN fintech microfinance regulations 2026")
        print(f"Success! Got {len(results)} results.")
        if results:
            print(f"First result title: {results[0].get('title')}")
    except Exception as e:
        print(f"SERP API Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
