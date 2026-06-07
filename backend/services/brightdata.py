"""
services/brightdata.py — Bright Data foundation layer for Iroko AI.
====================================================================
Provides an async client for all five Bright Data product surfaces used in the
Iroko AI enterprise web-intelligence pipeline:

  - **Web Unlocker** (fetch_url)  : Renders any public page through Bright Data's
    residential proxy network, bypassing bot protection and Cloudflare challenges.

  - **SERP API** (serp_search)    : Structured Google/Bing SERP results without
    browser overhead; ideal for rapid competitive-intelligence sweeps.

  - **Web Scraper API** (scrape_structured) : Schema-driven extraction via the
    Bright Data Datasets v3 trigger endpoint; falls back to fetch_url + raw HTML
    when the Datasets API is unreachable.

  - **Scraping Browser** (scraping_browser_interact) : Full Playwright browser
    automation over CDP for JS-heavy interactive pages (CBN.gov.ng / SEC.gov.ng
    regulatory document pages that require clicks, scrolls, and dynamic pagination).
    Falls back to Web Unlocker when the Scraping Browser zone is unavailable.

  - **MCP Server** (call_mcp_tool) : Model Context Protocol integration allowing
    AI agents to invoke Bright Data tools (search_serp, fetch_url) directly
    mid-reasoning via standard HTTP /tools/call. Falls back to native REST
    client methods when the MCP server is unconfigured.

  - **Health Check** (health_check) : Pings Bright Data's test endpoint to verify
    proxy connectivity and measure round-trip latency.

Mock mode:
    When BRIGHTDATA_API_KEY is absent (local dev / CI), fetch_url falls back to
    a plain httpx GET so the rest of the pipeline stays functional.

Usage::

    from services.brightdata import bright_data_client

    page    = await bright_data_client.fetch_url("https://example.com")
    results = await bright_data_client.serp_search("CBN Nigeria fintech regulation 2025")
    data    = await bright_data_client.scrape_structured(url, schema)
    dynamic = await bright_data_client.scraping_browser_interact(url, actions)
    mcp_res = await bright_data_client.call_mcp_tool("search_serp", {"query": "..."})
    health  = await bright_data_client.health_check()
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from pydantic import Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_USER_AGENT = "IrokoAI/2.0 (Enterprise Intelligence Platform)"
_TIMEOUT_SECONDS = 30
_MAX_RETRIES = 3
_BACKOFF_BASE = 1.5  # seconds; delay = _BACKOFF_BASE ** attempt


# ── Custom Exception ──────────────────────────────────────────────────────────


class BrightDataError(Exception):
    """
    Raised on unrecoverable failures from any Bright Data API surface.

    Attributes
    ----------
    message : str
        Human-readable description of what went wrong.
    status_code : int | None
        HTTP status code from the upstream response, if available.
    """

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


# ── Configuration ─────────────────────────────────────────────────────────────


class BrightDataConfig(BaseSettings):
    """
    Pydantic-settings model for Bright Data credentials and endpoints.
    All variables are read from the environment (or .env file).
    BRIGHTDATA_API_KEY is optional so the app can start in mock mode without it.
    """

    BRIGHTDATA_API_KEY: Optional[str] = Field(
        default=None,
        description="Bright Data account API key. Warn if missing; mock mode activates.",
    )
    BRIGHTDATA_CUSTOMER_ID: Optional[str] = Field(
        default=None,
        description="Bright Data account/customer ID (found in dashboard under Account Settings). Separate from API key."
    )
    BRIGHTDATA_WEB_UNLOCKER_ENDPOINT: str = Field(
        default="https://brd.superproxy.io:22225",
        description="Bright Data Web Unlocker proxy host:port.",
    )
    BRIGHTDATA_SERP_API_ENDPOINT: str = Field(
        default="https://api.brightdata.com/serp",
        description="Bright Data SERP API base URL.",
    )
    BRIGHTDATA_MCP_SERVER_URL: Optional[str] = Field(
        default=None,
        description="Optional Bright Data MCP (Model Context Protocol) server URL.",
    )
    BRIGHTDATA_ZONE: str = Field(
        default="residential",
        description="Bright Data proxy zone name (e.g. 'residential', 'datacenter').",
    )
    BRIGHTDATA_PROXY_PASSWORD: Optional[str] = Field(
        default=None,
        description="Bright Data proxy/zone password (specifically for Web Unlocker proxy auth). If not set, falls back to BRIGHTDATA_API_KEY.",
    )
    BRIGHTDATA_SERP_ZONE: str = Field(
        default="serp_api1",
        description="Bright Data SERP API zone name (e.g. 'serp_api1').",
    )
    BRIGHTDATA_SCRAPING_BROWSER_ZONE: str = Field(
        default="scraping_browser1",
        description="Bright Data Scraping Browser zone name (e.g. 'scraping_browser1').",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


# ── Async Client ──────────────────────────────────────────────────────────────


class BrightDataClient:
    """
    Async client for the Bright Data Web Intelligence suite.

    Instantiated once at module level as ``bright_data_client``.
    All network calls are made with a shared ``httpx.AsyncClient`` that is
    lazily created and reused across requests.
    """

    def __init__(self) -> None:
        self._config: Optional[BrightDataConfig] = None
        self._http: Optional[httpx.AsyncClient] = None

    # ── Internal helpers ──────────────────────────────────────────────────────

    @property
    def config(self) -> BrightDataConfig:
        """Lazily load and cache config (reads env vars on first access)."""
        if self._config is None:
            self._config = BrightDataConfig()
            if not self._config.BRIGHTDATA_API_KEY:
                logger.warning(
                    "[BrightData] BRIGHTDATA_API_KEY is not set. "
                    "Running in mock mode — fetch_url will use plain httpx GET. "
                    "SERP and Scraper APIs will be unavailable."
                )
            elif not self._config.BRIGHTDATA_CUSTOMER_ID:
                logger.warning(
                    "[BrightData] BRIGHTDATA_CUSTOMER_ID not set. Cannot build proxy auth. Mock mode active."
                )
        return self._config

    @property
    def mock_mode(self) -> bool:
        """Return True when no API key or customer ID is configured (local dev fallback)."""
        return not self.config.BRIGHTDATA_API_KEY or not self.config.BRIGHTDATA_CUSTOMER_ID

    def _get_http(self) -> httpx.AsyncClient:
        """Return the shared async HTTP client, creating it on first call."""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=httpx.Timeout(_TIMEOUT_SECONDS),
                headers={"User-Agent": _USER_AGENT},
                follow_redirects=True,
            )
        return self._http

    def _proxy_auth(self) -> tuple[str, str]:
        """
        Build the (username, password) tuple for Bright Data proxy authentication.
        Zone is embedded in the username per Bright Data's proxy format:
          brd-customer-<account>-zone-<zone>
        When no API key, returns empty strings (won't be used in mock mode).
        """
        username = f"brd-customer-{self.config.BRIGHTDATA_CUSTOMER_ID}-zone-{self.config.BRIGHTDATA_ZONE}"
        password = self.config.BRIGHTDATA_PROXY_PASSWORD or self.config.BRIGHTDATA_API_KEY or ""
        return username, password

    @staticmethod
    def _now_iso() -> str:
        """Return current UTC time as an ISO-8601 string."""
        return datetime.now(tz=timezone.utc).isoformat()

    async def _close(self) -> None:
        """Cleanly close the shared HTTP client."""
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    # ── Public API ────────────────────────────────────────────────────────────

    async def fetch_url(self, url: str, render_js: bool = True) -> dict[str, Any]:
        """
        Fetch a URL through the **Bright Data Web Unlocker** proxy.

        The Web Unlocker automatically handles bot-detection bypass, rotating
        IPs, CAPTCHA solving, and JavaScript rendering when ``render_js=True``.

        Parameters
        ----------
        url : str
            The target URL to fetch.
        render_js : bool
            Pass ``True`` (default) to request full JS rendering via headless
            Chrome on Bright Data's side. Set ``False`` for lightweight HTML-only
            fetches (faster, lower cost).

        Returns
        -------
        dict
            ``{"url": str, "content": str, "status": int, "fetched_at": str}``

        Raises
        ------
        BrightDataError
            If all retry attempts fail (excluding mock-mode fallback).
        """
        logger.info(f"[BrightData] Fetching {url}")

        # ── Mock mode: plain GET (no proxy) ──────────────────────────────────
        if self.mock_mode:
            logger.debug("[BrightData] Mock mode — skipping proxy for %s", url)
            try:
                http = self._get_http()
                response = await http.get(url)
                return {
                    "url": url,
                    "content": response.text,
                    "status": response.status_code,
                    "fetched_at": self._now_iso(),
                }
            except httpx.HTTPError as exc:
                raise BrightDataError(f"Mock fetch failed for {url}: {exc}") from exc

        # ── Real mode: proxy through Web Unlocker ─────────────────────────────
        proxy_endpoint = self.config.BRIGHTDATA_WEB_UNLOCKER_ENDPOINT
        proxy_username, proxy_password = self._proxy_auth()

        # Bright Data Web Unlocker is accessed as an HTTPS proxy.
        # httpx proxy format: "http://user:pass@host:port"
        proxy_url = (
            f"https://{proxy_username}:{proxy_password}@"
            + proxy_endpoint.replace("https://", "").replace("http://", "")
        )

        headers: dict[str, str] = {
            "User-Agent": _USER_AGENT,
        }
        if render_js:
            headers["X-Brd-Render"] = "true"

        last_exc: Optional[Exception] = None

        for attempt in range(_MAX_RETRIES):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(_TIMEOUT_SECONDS),
                    proxy=proxy_url,
                    follow_redirects=True,
                    verify=False,  # Bright Data uses its own SSL cert on the proxy tunnel
                ) as client:
                    response = await client.get(url, headers=headers)

                if response.status_code == 407:
                    raise BrightDataError(
                        "Proxy authentication failed (407). Check BRIGHTDATA_API_KEY and zone.",
                        status_code=407,
                    )

                logger.info(
                    "[BrightData] %s → HTTP %d (%d bytes)",
                    url,
                    response.status_code,
                    len(response.content),
                )
                return {
                    "url": url,
                    "content": response.text,
                    "status": response.status_code,
                    "fetched_at": self._now_iso(),
                }

            except BrightDataError:
                raise  # 407 is non-retryable
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
                last_exc = exc
                delay = _BACKOFF_BASE ** attempt
                logger.warning(
                    "[BrightData] fetch_url attempt %d/%d failed for %s: %s. "
                    "Retrying in %.1fs…",
                    attempt + 1,
                    _MAX_RETRIES,
                    url,
                    exc,
                    delay,
                )
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(delay)
            except Exception as exc:
                last_exc = exc
                delay = _BACKOFF_BASE ** attempt
                logger.warning(
                    "[BrightData] fetch_url unexpected error attempt %d/%d: %s",
                    attempt + 1,
                    _MAX_RETRIES,
                    exc,
                )
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(delay)

        raise BrightDataError(
            f"fetch_url exhausted {_MAX_RETRIES} retries for {url}: {last_exc}"
        ) from last_exc

    # ─────────────────────────────────────────────────────────────────────────

    async def serp_search(
        self,
        query: str,
        country: str = "ng",
        num_results: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Run a Google SERP query through the **Bright Data SERP API**.

        The SERP API returns structured, parsed search-engine result pages
        without requiring a browser. Results include organic listings,
        knowledge panels, and featured snippets flattened into a clean list.

        Parameters
        ----------
        query : str
            Search query string (e.g. "CBN Nigeria fintech enforcement 2025").
        country : str
            ISO 3166-1 alpha-2 country code for localising results (default: ``"ng"``
            for Nigeria — the primary Iroko AI market).
        num_results : int
            Maximum number of organic results to return (1–100).

        Returns
        -------
        list[dict]
            Each item: ``{"title": str, "url": str, "snippet": str, "position": int}``

        Raises
        ------
        BrightDataError
            On non-retryable API errors or if API key is absent.
        """
        if self.mock_mode:
            logger.warning("[BrightData] SERP API unavailable in mock mode. Returning mock data.")
            return [
                {
                    "title": f"Mock SERP Result: {query}",
                    "url": f"https://mock-news.ng/article/{query.replace(' ', '-')}",
                    "snippet": f"This is a simulated Bright Data SERP result for '{query}'. Used for local testing.",
                    "position": 1
                },
                {
                    "title": f"Mock Regulatory Update: {query}",
                    "url": f"https://mock-regulator.gov.ng/{query.replace(' ', '-')}",
                    "snippet": f"Simulated regulatory warning or competitor announcement regarding '{query}'.",
                    "position": 2
                }
            ]

        endpoint = "https://api.brightdata.com/request"
        api_key = self.config.BRIGHTDATA_API_KEY
        zone = self.config.BRIGHTDATA_SERP_ZONE

        import urllib.parse
        search_query = urllib.parse.quote_plus(query)
        target_url = f"https://www.google.com/search?q={search_query}&gl={country}&num={num_results}"

        payload = {
            "zone": zone,
            "url": target_url,
            "format": "json"
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        }

        last_exc: Optional[Exception] = None
        http = self._get_http()

        for attempt in range(_MAX_RETRIES):
            try:
                response = await http.post(endpoint, json=payload, headers=headers)

                if response.status_code == 429:
                    delay = _BACKOFF_BASE ** (attempt + 2)  # heavier back-off for rate limits
                    logger.warning(
                        "[BrightData] SERP rate-limited (429). Retry %d/%d in %.1fs…",
                        attempt + 1,
                        _MAX_RETRIES,
                        delay,
                    )
                    if attempt < _MAX_RETRIES - 1:
                        await asyncio.sleep(delay)
                        continue
                    raise BrightDataError("SERP API rate limit exceeded after retries.", status_code=429)

                if response.status_code not in (200, 201):
                    raise BrightDataError(
                        f"SERP API returned HTTP {response.status_code}: {response.text[:200]}",
                        status_code=response.status_code,
                    )

                data = response.json()

                # Check if response is wrapped in {"status_code": 200, "headers": ..., "body": ...}
                body_data = data
                if isinstance(data, dict) and "body" in data:
                    body_val = data["body"]
                    if isinstance(body_val, str):
                        try:
                            import json
                            body_data = json.loads(body_val)
                        except Exception as pe:
                            logger.error(f"[BrightData] Failed to parse nested JSON body: {pe}")
                            body_data = {}
                    elif isinstance(body_val, dict):
                        body_data = body_val

                organic: list[dict] = []
                if isinstance(body_data, dict):
                    organic = body_data.get("organic", [])

                results: list[dict[str, Any]] = []
                for i, item in enumerate(organic[:num_results]):
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("link", item.get("url", "")),
                        "snippet": item.get("snippet", item.get("description", "")),
                        "position": item.get("rank", item.get("position", i + 1)),
                    })

                logger.info(
                    "[BrightData] SERP search '%s' → %d results (country=%s)",
                    query[:60],
                    len(results),
                    country,
                )
                return results

            except BrightDataError:
                raise
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exc = exc
                delay = _BACKOFF_BASE ** attempt
                logger.warning(
                    "[BrightData] serp_search attempt %d/%d failed: %s. Retrying in %.1fs…",
                    attempt + 1,
                    _MAX_RETRIES,
                    exc,
                    delay,
                )
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(delay)
            except Exception as exc:
                last_exc = exc
                logger.warning("[BrightData] serp_search unexpected error: %s", exc)
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(_BACKOFF_BASE ** attempt)

        raise BrightDataError(
            f"serp_search exhausted {_MAX_RETRIES} retries for '{query}': {last_exc}"
        ) from last_exc

    # ─────────────────────────────────────────────────────────────────────────

    async def scrape_structured(self, url: str, schema: dict[str, Any]) -> dict[str, Any]:
        """
        Extract structured data from a URL using the **Bright Data Web Scraper
        Datasets v3 API** (POST /datasets/v3/trigger).

        The caller provides a ``schema`` dict describing the fields to extract
        (field name → extraction hint/XPath/description). Bright Data's managed
        scrapers handle pagination, JS rendering, and anti-bot challenges.

        Falls back transparently to ``fetch_url`` if the Datasets API returns
        a non-200 status or is unreachable.

        Parameters
        ----------
        url : str
            The target page to scrape.
        schema : dict
            Field extraction schema, e.g.::

                {
                    "company_name": "Name of the fintech company",
                    "revenue_usd": "Annual revenue in USD",
                    "customers_m": "Total customers in millions",
                }

        Returns
        -------
        dict
            Extracted fields matching ``schema`` keys, plus a ``_meta`` key
            containing ``{"url": str, "scraped_at": str, "source": str}``.

        Raises
        ------
        BrightDataError
            On non-retryable Datasets API failures (after fallback also fails).
        """
        if self.mock_mode:
            logger.warning(
                "[BrightData] Scraper API unavailable in mock mode. Returning mock structured data."
            )
            result = {
                "_meta": {"url": url, "scraped_at": self._now_iso(), "source": "mock_scrape"},
                "raw_html": "<html><body><h1>Mock Extracted Data</h1></body></html>",
            }
            # Fill schema keys with dummy data
            for key in schema.keys():
                result[key] = f"Mock extracted {key}"
            return result

        datasets_endpoint = "https://api.brightdata.com/datasets/v3/trigger"
        api_key = self.config.BRIGHTDATA_API_KEY

        payload: dict[str, Any] = {
            "url": url,
            "schema": schema,
            "format": "json",
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        }

        http = self._get_http()

        try:
            response = await http.post(datasets_endpoint, json=payload, headers=headers)

            if response.status_code not in (200, 201, 202):
                logger.warning(
                    "[BrightData] Datasets API returned HTTP %d for %s. Falling back to fetch_url.",
                    response.status_code,
                    url,
                )
                page = await self.fetch_url(url, render_js=True)
                return {
                    "_meta": {
                        "url": url,
                        "scraped_at": self._now_iso(),
                        "source": "fetch_url_fallback",
                    },
                    "raw_html": page["content"][:10000],
                }

            data = response.json()

            # Datasets v3 may return a snapshot_id for async jobs; handle both
            if "snapshot_id" in data:
                snapshot_id = data["snapshot_id"]
                poll_url = f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}?format=json"
                poll_success = False
                poll_data = None

                for n in range(1, 4):
                    logger.info(f"[BrightData] Polling snapshot {snapshot_id}, attempt {n}/3...")
                    try:
                        poll_resp = await http.get(poll_url, headers=headers)
                        if poll_resp.status_code == 200:
                            poll_data = poll_resp.json()
                            poll_success = True
                            break
                    except Exception as poll_exc:
                        logger.warning(
                            f"[BrightData] Snapshot {snapshot_id} poll attempt {n}/3 failed: {poll_exc}"
                        )
                    if n < 3:
                        await asyncio.sleep(5)

                if poll_success and poll_data is not None:
                    result = {
                        "_meta": {
                            "url": url,
                            "scraped_at": self._now_iso(),
                            "source": "datasets_v3_async",
                            "snapshot_id": snapshot_id,
                        }
                    }
                    if isinstance(poll_data, list) and poll_data:
                        result.update(poll_data[0])
                    elif isinstance(poll_data, dict):
                        result.update(poll_data)
                    logger.info("[BrightData] scrape_structured async complete for %s", url)
                    return result
                else:
                    logger.info(
                        f"[BrightData] Snapshot {snapshot_id} not ready after 3 polls. Falling back to fetch_url."
                    )
                    page = await self.fetch_url(url, render_js=True)
                    return {
                        "_meta": {
                            "url": url,
                            "scraped_at": self._now_iso(),
                            "source": "fetch_url_fallback",
                            "snapshot_id": snapshot_id,
                        },
                        "raw_html": page["content"][:10000],
                    }

            # Synchronous result
            result: dict[str, Any] = {
                "_meta": {"url": url, "scraped_at": self._now_iso(), "source": "datasets_v3"}
            }
            # Merge schema fields from response
            if isinstance(data, list) and data:
                result.update(data[0])
            elif isinstance(data, dict):
                result.update(data)

            logger.info("[BrightData] scrape_structured complete for %s (%d fields)", url, len(schema))
            return result

        except BrightDataError:
            raise
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logger.warning(
                "[BrightData] Datasets API unreachable (%s). Falling back to fetch_url.", exc
            )
            try:
                page = await self.fetch_url(url, render_js=True)
                return {
                    "_meta": {
                        "url": url,
                        "scraped_at": self._now_iso(),
                        "source": "fetch_url_fallback",
                    },
                    "raw_html": page["content"][:10000],
                }
            except BrightDataError as inner_exc:
                raise BrightDataError(
                    f"scrape_structured failed and fallback also failed for {url}: {inner_exc}"
                ) from inner_exc
        except Exception as exc:
            raise BrightDataError(
                f"scrape_structured unexpected error for {url}: {exc}"
            ) from exc

    # ─────────────────────────────────────────────────────────────────────────

    async def health_check(self) -> dict[str, Any]:
        """
        Verify Bright Data proxy connectivity via the **Web Unlocker** test endpoint.

        Pings ``https://geo.brdtest.com/welcome.txt`` through the proxy and measures
        round-trip latency. The response body contains the egress IP assigned by
        Bright Data's proxy network.

        Returns
        -------
        dict
            ``{"status": "ok"|"error", "latency_ms": float, "proxy_ip": str}``
            On error: ``{"status": "error", "latency_ms": float, "error": str}``

        Raises
        ------
        BrightDataError
            Not raised — errors are surfaced as ``{"status": "error", ...}`` to
            avoid crashing startup checks.
        """
        test_url = "https://geo.brdtest.com/welcome.txt"
        start = asyncio.get_event_loop().time()

        try:
            result = await self.fetch_url(test_url, render_js=False)
            latency_ms = round((asyncio.get_event_loop().time() - start) * 1000, 2)

            # The welcome.txt body typically contains the proxied IP
            content = result.get("content", "").strip()
            proxy_ip = content.split("\n")[0] if content else "unknown"

            logger.info(
                "[BrightData] Health check OK — latency=%.0fms proxy_ip=%s",
                latency_ms,
                proxy_ip,
            )
            return {
                "status": "ok",
                "latency_ms": latency_ms,
                "proxy_ip": proxy_ip,
            }

        except Exception as exc:
            latency_ms = round((asyncio.get_event_loop().time() - start) * 1000, 2)
            logger.error("[BrightData] Health check failed: %s", exc)
            return {
                "status": "error",
                "latency_ms": latency_ms,
                "proxy_ip": "unavailable",
                "error": str(exc),
            }

    # ─────────────────────────────────────────────────────────────────────────

    async def scraping_browser_interact(self, url: str, actions: list[dict] = None) -> dict[str, Any]:
        """
        Use Bright Data Scraping Browser for JS-heavy interactive pages.
        Falls back to fetch_url if scraping browser unavailable or mock mode is active.
        Used for CBN.gov.ng / SEC.gov.ng dynamic regulatory document pages.
        """
        logger.info(f"[BrightData] Connecting to Scraping Browser for {url}")
        if self.mock_mode:
            logger.warning("[BrightData] Mock mode active — Scraping Browser simulates fetching url.")
            try:
                res = await self.fetch_url(url, render_js=True)
                res["source"] = "scraping_browser_mock"
                return res
            except Exception as e:
                raise BrightDataError(f"Mock Scraping Browser failed: {e}") from e

        customer_id = self.config.BRIGHTDATA_CUSTOMER_ID
        scraping_browser_zone = getattr(self.config, "BRIGHTDATA_SCRAPING_BROWSER_ZONE", "scraping_browser1")
        password = self.config.BRIGHTDATA_PROXY_PASSWORD or self.config.BRIGHTDATA_API_KEY or ""
        
        ws_endpoint = f"wss://brd-customer-{customer_id}-zone-{scraping_browser_zone}:{password}@brd.superproxy.io:9222"
        
        from playwright.async_api import async_playwright
        try:
            async with async_playwright() as p:
                logger.info("[BrightData] CDP connecting to superproxy...")
                browser = await p.chromium.connect_over_cdp(ws_endpoint)
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded")
                
                if actions:
                    for action in actions:
                        atype = action.get("type")
                        selector = action.get("selector")
                        if atype == "click" and selector:
                            logger.info(f"[BrightData] Scraping Browser click: {selector}")
                            await page.click(selector)
                        elif atype == "fill" and selector:
                            val = action.get("value", "")
                            logger.info(f"[BrightData] Scraping Browser fill: {selector} = {val}")
                            await page.fill(selector, val)
                        elif atype == "scroll":
                            logger.info("[BrightData] Scraping Browser scrollDown")
                            await page.evaluate("window.scrollBy(0, window.innerHeight)")
                        elif atype == "wait":
                            timeout = action.get("timeout", 1000)
                            await page.wait_for_timeout(timeout)
                
                content = await page.content()
                await browser.close()
                return {
                    "url": url,
                    "content": content,
                    "status": 200,
                    "fetched_at": self._now_iso(),
                    "source": "scraping_browser",
                }
        except Exception as exc:
            logger.warning("[BrightData] Scraping Browser failed: %s. Falling back to Web Unlocker.", exc)
            return await self.fetch_url(url, render_js=True)

    # ─────────────────────────────────────────────────────────────────────────

    async def call_mcp_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Invoke a tool on the Bright Data MCP Server (Model Context Protocol).
        Used by the Strategist agent to dynamically fetch real-time market signals.
        Falls back to local REST client APIs if the MCP server is unreachable or unconfigured.
        """
        mcp_url = self.config.BRIGHTDATA_MCP_SERVER_URL
        if not mcp_url or self.mock_mode:
            logger.warning("[BrightData] MCP Server URL is not configured or in mock mode. Falling back to local REST client APIs.")
            if "serp" in tool_name or "search" in tool_name:
                query = arguments.get("query", arguments.get("q", ""))
                return await self.serp_search(query)
            else:
                url = arguments.get("url", "")
                return await self.fetch_url(url)

        headers = {
            "Authorization": f"Bearer {self.config.BRIGHTDATA_API_KEY}",
            "Content-Type": "application/json",
        }
        
        body = {
            "name": tool_name,
            "arguments": arguments,
        }
        
        endpoint = f"{mcp_url.rstrip('/')}/tools/call"
        logger.info(f"[BrightData] Invoking MCP Tool {tool_name} on {endpoint}")
        
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(_TIMEOUT_SECONDS)) as client:
                response = await client.post(endpoint, json=body, headers=headers)
                
            if response.status_code == 200:
                logger.info(f"[BrightData] MCP Tool {tool_name} executed successfully.")
                return response.json()
            else:
                logger.warning(f"[BrightData] MCP Server returned HTTP {response.status_code}. Falling back.")
        except Exception as e:
            logger.warning(f"[BrightData] Failed to connect to MCP Server: {e}. Falling back.")

        if "serp" in tool_name or "search" in tool_name:
            return await self.serp_search(arguments.get("query", ""))
        else:
            return await self.fetch_url(arguments.get("url", ""))


# ── Module-level singleton ────────────────────────────────────────────────────

bright_data_client: BrightDataClient = BrightDataClient()
"""
Shared singleton ``BrightDataClient`` instance.
Import and use this directly in agents and routes::

    from services.brightdata import bright_data_client

    results = await bright_data_client.serp_search("Airtel Nigeria 2025 coverage")
"""
