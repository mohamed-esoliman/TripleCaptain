import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limiting configuration for FPL API calls."""

    calls_per_minute: int = 30
    burst_limit: int = 5
    backoff_multiplier: float = 2.0
    max_retries: int = 3


class FPLClientError(Exception):
    """Base exception for FPL client errors."""

    pass


class RateLimitError(FPLClientError):
    """Raised when rate limit is exceeded."""

    pass


class APIUnavailableError(FPLClientError):
    """Raised when FPL API is unavailable."""

    pass


class FPLClient:
    """Async client for fetching data from the FPL API."""

    def __init__(self, rate_limit_config: Optional[RateLimitConfig] = None):
        self.base_url = settings.FPL_BASE_URL.rstrip("/")
        self.rate_limit = rate_limit_config or RateLimitConfig()
        self._last_request_time = 0.0
        self._request_count = 0
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self._create_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._close_session()

    async def _create_session(self):
        """Create aiohttp session with appropriate headers."""
        headers = {
            "User-Agent": "TripleCaptain-FPL-App/1.0",
            "Accept": "application/json",
        }

        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self._session = aiohttp.ClientSession(headers=headers, timeout=timeout)

    async def _close_session(self):
        """Close aiohttp session."""
        if self._session:
            await self._session.close()
            self._session = None

    async def _rate_limited_request(self, url: str) -> Dict[str, Any]:
        """Make rate-limited request with exponential backoff."""
        if not self._session:
            await self._create_session()

        for attempt in range(self.rate_limit.max_retries + 1):
            # Implement rate limiting
            current_time = asyncio.get_event_loop().time()
            time_since_last = current_time - self._last_request_time
            min_interval = 60.0 / self.rate_limit.calls_per_minute

            if time_since_last < min_interval:
                sleep_time = min_interval - time_since_last
                await asyncio.sleep(sleep_time)

            try:
                async with self._session.get(url) as response:
                    self._last_request_time = asyncio.get_event_loop().time()

                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:  # Too Many Requests
                        if attempt < self.rate_limit.max_retries:
                            sleep_time = (
                                self.rate_limit.backoff_multiplier**attempt
                            ) * 5
                            logger.warning(f"Rate limited, sleeping for {sleep_time}s")
                            await asyncio.sleep(sleep_time)
                            continue
                        else:
                            raise RateLimitError("Rate limit exceeded after retries")
                    elif response.status >= 500:
                        if attempt < self.rate_limit.max_retries:
                            sleep_time = self.rate_limit.backoff_multiplier**attempt
                            logger.warning(
                                f"Server error {response.status}, retrying in {sleep_time}s"
                            )
                            await asyncio.sleep(sleep_time)
                            continue
                        else:
                            raise APIUnavailableError(
                                f"FPL API unavailable: {response.status}"
                            )
                    else:
                        raise FPLClientError(
                            f"HTTP {response.status}: {await response.text()}"
                        )

            except aiohttp.ClientError as e:
                if attempt < self.rate_limit.max_retries:
                    sleep_time = self.rate_limit.backoff_multiplier**attempt
                    logger.warning(f"Request failed: {e}, retrying in {sleep_time}s")
                    await asyncio.sleep(sleep_time)
                    continue
                else:
                    raise FPLClientError(f"Request failed after retries: {e}")

        raise FPLClientError("Max retries exceeded")

    async def get_bootstrap_static(self) -> Dict[str, Any]:
        """Get bootstrap static data (players, teams, gameweeks)."""
        url = f"{self.base_url}/bootstrap-static/"
        logger.info("Fetching bootstrap static data")

        try:
            data = await self._rate_limited_request(url)
            logger.info(
                f"Retrieved {len(data.get('elements', []))} players, "
                f"{len(data.get('teams', []))} teams, "
                f"{len(data.get('events', []))} gameweeks"
            )
            return data
        except Exception as e:
            logger.error(f"Failed to fetch bootstrap data: {e}")
            raise

    async def get_player_summary(self, player_id: int) -> Dict[str, Any]:
        """Get detailed player summary including history and fixtures."""
        url = f"{self.base_url}/element-summary/{player_id}/"
        logger.debug(f"Fetching player summary for ID {player_id}")

        try:
            data = await self._rate_limited_request(url)
            logger.debug(
                f"Retrieved player {player_id} with "
                f"{len(data.get('history', []))} history records, "
                f"{len(data.get('fixtures', []))} fixtures"
            )
            return data
        except Exception as e:
            logger.error(f"Failed to fetch player {player_id} summary: {e}")
            raise

    async def get_fixtures(
        self, gameweek: Optional[int] = None, future_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Get fixture data with optional filtering."""
        url = f"{self.base_url}/fixtures/"
        params = []

        if gameweek:
            params.append(f"event={gameweek}")
        if future_only:
            params.append("future=1")

        if params:
            url += "?" + "&".join(params)

        logger.info(f"Fetching fixtures with params: {params}")

        try:
            data = await self._rate_limited_request(url)
            logger.info(f"Retrieved {len(data)} fixtures")
            return data
        except Exception as e:
            logger.error(f"Failed to fetch fixtures: {e}")
            raise

    async def get_gameweek_live(self, gameweek: int) -> Dict[str, Any]:
        """Get live gameweek performance data."""
        url = f"{self.base_url}/event/{gameweek}/live/"
        logger.info(f"Fetching live data for gameweek {gameweek}")

        try:
            data = await self._rate_limited_request(url)
            elements = data.get("elements", [])
            logger.info(
                f"Retrieved live data for {len(elements)} players in GW{gameweek}"
            )
            return data
        except Exception as e:
            logger.error(f"Failed to fetch live data for GW{gameweek}: {e}")
            raise

    async def get_entry_picks(self, entry_id: int, gameweek: int) -> Dict[str, Any]:
        """Get manager's team selection for a specific gameweek."""
        url = f"{self.base_url}/entry/{entry_id}/event/{gameweek}/picks/"
        logger.debug(f"Fetching picks for entry {entry_id}, GW{gameweek}")

        try:
            data = await self._rate_limited_request(url)
            picks = data.get("picks", [])
            logger.debug(f"Retrieved {len(picks)} picks for entry {entry_id}")
            return data
        except Exception as e:
            logger.error(f"Failed to fetch picks for entry {entry_id}: {e}")
            raise

    async def get_entry_history(self, entry_id: int) -> Dict[str, Any]:
        """Get manager's historical performance."""
        url = f"{self.base_url}/entry/{entry_id}/history/"
        logger.debug(f"Fetching history for entry {entry_id}")

        try:
            data = await self._rate_limited_request(url)
            current = data.get("current", [])
            logger.debug(
                f"Retrieved history for entry {entry_id}: {len(current)} gameweeks"
            )
            return data
        except Exception as e:
            logger.error(f"Failed to fetch history for entry {entry_id}: {e}")
            raise

    async def batch_get_player_summaries(
        self, player_ids: List[int], max_concurrent: int = 5
    ) -> List[Dict[str, Any]]:
        """Fetch multiple player summaries concurrently with rate limiting."""
        logger.info(f"Batch fetching {len(player_ids)} player summaries")

        semaphore = asyncio.Semaphore(max_concurrent)

        async def fetch_one(player_id: int) -> Optional[Dict[str, Any]]:
            async with semaphore:
                try:
                    return await self.get_player_summary(player_id)
                except Exception as e:
                    logger.error(f"Failed to fetch player {player_id}: {e}")
                    return None

        tasks = [fetch_one(player_id) for player_id in player_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out failed requests
        successful_results = [
            result
            for result in results
            if result is not None and not isinstance(result, Exception)
        ]

        logger.info(
            f"Successfully fetched {len(successful_results)}/{len(player_ids)} player summaries"
        )
        return successful_results


# Utility functions for data processing
def get_current_gameweek(events: List[Dict[str, Any]]) -> Optional[int]:
    """Get current gameweek from events data."""
    # Use timezone-aware UTC for comparison with ISO strings that include offset
    current_time = datetime.now(timezone.utc)

    for event in events:
        deadline = event.get("deadline_time")
        if deadline:
            deadline_dt = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
            if deadline_dt > current_time and not event.get("finished", False):
                return event["id"]

    return None


def get_next_gameweek(events: List[Dict[str, Any]]) -> Optional[int]:
    """Get next gameweek from events data."""
    current_gw = get_current_gameweek(events)
    if current_gw and current_gw < len(events):
        return current_gw + 1
    return None


def is_gameweek_finished(events: List[Dict[str, Any]], gameweek: int) -> bool:
    """Check if a gameweek is finished."""
    for event in events:
        if event["id"] == gameweek:
            return event.get("finished", False)
    return False


def get_season_string() -> str:
    """Get current season string (e.g., '2024-25')."""
    current_year = datetime.now().year
    current_month = datetime.now().month

    # FPL season starts in August
    if current_month >= 8:
        return f"{current_year}-{str(current_year + 1)[-2:]}"
    else:
        return f"{current_year - 1}-{str(current_year)[-2:]}"
