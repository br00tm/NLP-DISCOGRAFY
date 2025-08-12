import time
import random
import logging
from typing import Optional, Tuple
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup


class HttpCrawler:
    """HTTP crawler com respeito a robots.txt, retries, backoff e user-agent configurável."""

    def __init__(
        self,
        user_agent: str = "Mozilla/5.0 (compatible; DiscographyCrawler/1.0; +https://example.com)",
        max_retries: int = 3,
        backoff_factor_seconds: float = 1.5,
        min_delay_seconds: float = 1.0,
        max_delay_seconds: float = 2.5,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self.max_retries = max_retries
        self.backoff_factor_seconds = backoff_factor_seconds
        self.min_delay_seconds = min_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self.timeout_seconds = timeout_seconds
        self._robots_cache: dict[str, RobotFileParser] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def _respectful_delay(self) -> None:
        delay = random.uniform(self.min_delay_seconds, self.max_delay_seconds)
        time.sleep(delay)

    def _get_robots(self, base_url: str) -> RobotFileParser:
        if base_url in self._robots_cache:
            return self._robots_cache[base_url]
        rp = RobotFileParser()
        robots_url = base_url.rstrip("/") + "/robots.txt"
        try:
            rp.set_url(robots_url)
            rp.read()
        except Exception:
            # Se falhar, assume permitido por padrão (com cautela)
            pass
        self._robots_cache[base_url] = rp
        return rp

    def _allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        rp = self._get_robots(base)
        try:
            return rp.can_fetch(self.session.headers.get("User-Agent", "*"), url)
        except Exception:
            return True

    def fetch(self, url: str) -> Tuple[Optional[BeautifulSoup], Optional[requests.Response]]:
        """Faz GET com retries e retorna (soup, response). Respeita robots e insere delays."""
        if not self._allowed(url):
            self.logger.warning("Bloqueado por robots.txt: %s", url)
            return None, None

        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                self._respectful_delay()
                response = self.session.get(url, timeout=self.timeout_seconds)
                if response.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {response.status_code}")
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                return soup, response
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                wait = (self.backoff_factor_seconds ** attempt) if attempt > 0 else 0
                if wait:
                    time.sleep(wait)
                self.logger.debug("Erro ao buscar %s (tentativa %d/%d): %s", url, attempt + 1, self.max_retries + 1, exc)
        self.logger.error("Falha ao buscar %s: %s", url, last_exc)
        return None, None 