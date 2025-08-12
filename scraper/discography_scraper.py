from __future__ import annotations

import logging
import re
from typing import Iterable, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .crawler import HttpCrawler

WIKI_BASE = "https://pt.wikipedia.org"
CATEGORY_ALBUMS = \
    "https://pt.wikipedia.org/wiki/Categoria:%C3%81lbuns_de_Engenheiros_do_Hawaii"


class WikipediaDiscographyScraper:
    """Coleta URLs de álbuns e extrai tracklists das páginas individuais na Wikipédia PT."""

    def __init__(self, crawler: HttpCrawler) -> None:
        self.crawler = crawler
        self.logger = logging.getLogger(self.__class__.__name__)

    def iter_album_urls(self) -> Iterable[str]:
        """Itera sobre todas as páginas de álbuns da categoria principal (com paginação)."""
        next_url = CATEGORY_ALBUMS
        visited: set[str] = set()
        while next_url and next_url not in visited:
            visited.add(next_url)
            soup, _ = self.crawler.fetch(next_url)
            if not soup:
                break
            for link in soup.select("div#mw-pages div.mw-category a"):
                href = link.get("href")
                if href and href.startswith("/wiki/") and not href.startswith("/wiki/Categoria:"):
                    yield urljoin(WIKI_BASE, href)
            # paginação: procurar link "página seguinte"
            pager = soup.select_one("div#mw-pages a[title='Categoria:Álbuns de Engenheiros do Hawaii'] + a ~ a")
            # fallback robusto
            next_link = None
            for a in soup.select("div#mw-pages a"):
                if a.text.strip().lower() in {"página seguinte", "página seguinte »", "página seguinte»", "próxima página"}:
                    next_link = a
                    break
            if next_link and next_link.get("href"):
                next_url = urljoin(WIKI_BASE, next_link.get("href"))
            else:
                next_url = None

    def parse_album_page(self, album_url: str) -> Optional[dict]:
        soup, _ = self.crawler.fetch(album_url)
        if not soup:
            return None
        title_el = soup.select_one("h1#firstHeading")
        album_title = title_el.text.strip() if title_el else album_url

        tracks = self._extract_tracks(soup)
        if not tracks:
            self.logger.warning("Nenhuma faixa encontrada em %s", album_url)

        year = self._extract_year(soup)

        return {
            "album_title": album_title,
            "album_url": album_url,
            "release_year": year,
            "tracks": tracks,
        }

    def _extract_year(self, soup: BeautifulSoup) -> Optional[int]:
        # tentar infobox
        infobox = soup.select_one("table.infobox, table.infobox_v2")
        if infobox:
            text = infobox.get_text(" ", strip=True)
            match = re.search(r"(19|20)\d{2}", text)
            if match:
                try:
                    return int(match.group(0))
                except ValueError:
                    pass
        # fallback: primeira data no conteúdo
        content = soup.select_one("div.mw-parser-output")
        if content:
            match = re.search(r"(19|20)\d{2}", content.get_text(" ", strip=True))
            if match:
                try:
                    return int(match.group(0))
                except ValueError:
                    pass
        return None

    def _extract_tracks(self, soup: BeautifulSoup) -> List[dict]:
        extractors = [
            self._extract_tracks_from_wikitable,
            self._extract_tracks_from_ordered_list,
        ]
        for extractor in extractors:
            tracks = extractor(soup)
            if tracks:
                # normalizar numeração sequencial caso ausente
                for idx, trk in enumerate(tracks, start=1):
                    if not trk.get("track_number"):
                        trk["track_number"] = idx
                return tracks
        return []

    def _extract_tracks_from_wikitable(self, soup: BeautifulSoup) -> List[dict]:
        tracks: List[dict] = []
        for table in soup.select("table.wikitable"):
            headers = [th.get_text(" ", strip=True).lower() for th in table.select("thead th")] or [
                th.get_text(" ", strip=True).lower() for th in table.select("tr th")
            ]
            if not headers:
                continue
            if not any(h in headers for h in ["faixa", "n.º", "nº", "n.", "#", "no.", "número"]):
                continue
            if not any("título" in h or "faixa" in h or "canção" in h for h in headers):
                continue

            for row in table.select("tr"):
                cells = row.find_all(["td", "th"])  # algumas tabelas usam th para número
                if len(cells) < 2:
                    continue
                number = _parse_track_number(cells[0].get_text(" ", strip=True))
                # encontrar célula com o título (heurística)
                title_cell = None
                if len(cells) >= 2:
                    title_cell = cells[1]
                # às vezes há uma coluna de duração entre número e título
                if title_cell and _looks_like_duration(title_cell.get_text(" ", strip=True)) and len(cells) >= 3:
                    title_cell = cells[2]
                title = _clean_track_title(title_cell.get_text(" ", strip=True)) if title_cell else None
                if title and _is_valid_track_title(title):
                    tracks.append({"track_number": number, "title": title})
        return tracks

    def _extract_tracks_from_ordered_list(self, soup: BeautifulSoup) -> List[dict]:
        tracks: List[dict] = []
        # procurar seções com título "Lista de faixas" ou "Faixas"
        sections = []
        for headline in soup.select("span.mw-headline"):
            text = headline.get_text(" ", strip=True).lower()
            if any(key in text for key in ["lista de faixas", "faixas", "lista de músicas", "tracklist"]):
                sections.append(headline)
        candidates: List[BeautifulSoup] = []
        for sec in sections:
            # procurar a primeira lista ordenada após o título
            current = sec.parent
            while current and current.name not in {"ol", "table"}:
                current = current.find_next_sibling()
            if current and current.name == "ol":
                candidates.append(current)
        if not candidates:
            # fallback: qualquer ol grande no conteúdo
            candidates = soup.select("div.mw-parser-output ol")
        for ol in candidates:
            items = ol.find_all("li", recursive=False) or ol.find_all("li")
            for li in items:
                raw = li.get_text(" ", strip=True)
                title = _clean_track_title(_split_number_and_title(raw)[1])
                if title and _is_valid_track_title(title):
                    tracks.append({"track_number": None, "title": title})
            if tracks:
                break
        return tracks


def _split_number_and_title(text: str) -> tuple[Optional[int], str]:
    # remove prefixos tipo "1." "1)" "A1" etc.
    m = re.match(r"^([A-Za-z]?[0-9]{1,2})[\).\-\s]+(.+)$", text)
    if m:
        num = m.group(1)
        try:
            return int(re.sub(r"[^0-9]", "", num)), m.group(2)
        except ValueError:
            return None, m.group(2)
    return None, text


def _clean_track_title(title: str) -> str:
    # remover aspas, notas entre parênteses e créditos
    title = re.sub(r"\s*\([^\)]*\)", "", title)  # parênteses
    title = title.strip().strip('"""‟‟\'')
    # separar por – or - se houver créditos/duração
    parts = re.split(r"\s[–-]\s", title)
    if parts:
        title = parts[0].strip()
    # remover "Lançamento:" e datas
    title = re.sub(r"Lançamento:\s*\d{4}", "", title)
    return title.strip()


def _parse_track_number(text: str) -> Optional[int]:
    text = text.strip()
    try:
        return int(re.sub(r"[^0-9]", "", text)) if re.search(r"\d", text) else None
    except ValueError:
        return None


def _is_valid_track_title(title: str) -> bool:
    """Filtrar títulos que não são faixas reais."""
    if not title or len(title) < 2:
        return False
    
    # filtrar referências da Wikipedia
    if title.startswith("↑"):
        return False
    if "Mazocco & Remaso" in title or "Lucchese" in title:
        return False
    if "AllMusic" in title or "Spotify" in title:
        return False
    if "Consultado em" in title:
        return False
    if title.startswith("«") and title.endswith("»"):
        return False
    if "Lançamento:" in title and len(title) > 50:
        return False
    if title.lower().startswith("http"):
        return False
    
    return True


def _looks_like_duration(text: str) -> bool:
    return bool(re.match(r"^\d{1,2}:\d{2}$", text.strip())) 