from __future__ import annotations

import logging
import time
import re
from typing import List, Optional
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup


class GeniusDiscographyProvider:
    """Cliente completo para buscar discografia via API do Genius e extrair letras das páginas."""

    API_BASE = "https://api.genius.com"
    SITE_BASE = "https://genius.com"
    DEFAULT_ACCESS_TOKEN = "8pWmFQWeV6i_SpOgNY4-VOwgjusxxYlYS3x7a7QIrPAGNQZNoE-j2UBHROhWVA1K"

    def __init__(self, access_token: Optional[str], max_retries: int = 2, backoff_seconds: float = 1.5) -> None:
        self.access_token = (access_token or self.DEFAULT_ACCESS_TOKEN).strip()
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.logger = logging.getLogger(self.__class__.__name__)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "DiscographyCrawler/1.0 (+https://example.com)",
        })

    def is_enabled(self) -> bool:
        return bool(self.access_token)

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}

    def get_artist_songs(self, artist_name: str, max_songs: int = 500) -> List[dict]:
        """Busca todas as músicas do artista via API do Genius."""
        if not self.access_token:
            return []
        
        # Primeiro, buscar o ID do artista
        artist_id = self._get_artist_id(artist_name)
        if not artist_id:
            return []
        
        # Buscar todas as músicas do artista
        songs = []
        page = 1
        while len(songs) < max_songs:
            page_songs = self._get_artist_songs_page(artist_id, page)
            if not page_songs:
                break
            songs.extend(page_songs)
            page += 1
            if len(page_songs) < 20:  # página não completa = última página
                break
        
        return songs[:max_songs]

    def search_albums(self, artist_name: str) -> List[dict]:
        """Busca álbuns específicos do artista no Genius."""
        if not self.access_token:
            return []
        
        albums = []
        # Lista conhecida de álbuns dos Engenheiros do Hawaii
        known_albums = [
            "Longe Demais das Capitais", "A Revolta dos Dândis", "Ouça o Que Eu Digo: Não Ouça Ninguém",
            "O Papa É Pop", "Alívio Imediato", "Várias Variáveis", "Gessinger, Licks & Maltz",
            "Surfando Karmas & DNA", "Minuano", "Simples de Coração", "Tchau Radar!",
            "10.000 Destinos", "Novos Horizontes", "Acústico MTV", "Filmes de Guerra, Canções de Amor",
            "Dançando no Campo Minado", "Pra Entender"
        ]
        
        # Para cada álbum conhecido, buscar suas músicas
        for album_name in known_albums:
            self.logger.info("Buscando álbum: %s", album_name)
            album_songs = self._search_album_songs(artist_name, album_name)
            if album_songs:
                albums.append({
                    "album_title": album_name,
                    "album_url": "",
                    "release_year": None,
                    "tracks": album_songs
                })
        
        return albums
    
    def _search_album_songs(self, artist_name: str, album_name: str) -> List[dict]:
        """Busca músicas de um álbum específico."""
        query = f"{artist_name} {album_name}"
        url = f"{self.API_BASE}/search?q={query}"
        
        songs = []
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.get(url, headers=self._auth_headers(), timeout=20)
                resp.raise_for_status()
                data = resp.json()
                hits = (data.get("response") or {}).get("hits") or []
                
                for hit in hits:
                    result = hit.get("result") or {}
                    primary_artist = result.get("primary_artist") or {}
                    
                    # Verificar se é do artista correto
                    if primary_artist.get("name", "").lower() != artist_name.lower():
                        continue
                    
                    # Verificar se menciona o álbum no título ou tem informação de álbum
                    song_album = result.get("album") or {}
                    song_album_name = song_album.get("name", "")
                    full_title = result.get("full_title", "")
                    
                    # Se tem informação de álbum e bate com o que procuramos
                    if (album_name.lower() in song_album_name.lower() or 
                        album_name.lower() in full_title.lower()):
                        
                        # Buscar letra da música
                        lyrics = self.get_lyrics_from_song(result)
                        
                        songs.append({
                            "track_number": None,
                            "title": result.get("title", ""),
                            "lyrics": lyrics
                        })
                
                break
                
            except Exception as exc:
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * (attempt + 1))
                else:
                    self.logger.error("Erro ao buscar álbum %s: %s", album_name, exc)
        
        return songs

    def _get_artist_id(self, artist_name: str) -> Optional[int]:
        url = f"{self.API_BASE}/search?q={artist_name}"
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.get(url, headers=self._auth_headers(), timeout=20)
                resp.raise_for_status()
                data = resp.json()
                hits = (data.get("response") or {}).get("hits") or []
                for hit in hits:
                    result = hit.get("result") or {}
                    primary_artist = result.get("primary_artist") or {}
                    if primary_artist.get("name", "").lower() == artist_name.lower():
                        return primary_artist.get("id")
                return None
            except Exception as exc:
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * (attempt + 1))
                else:
                    self.logger.error("Erro ao buscar ID do artista: %s", exc)
        return None

    def _get_artist_songs_page(self, artist_id: int, page: int) -> List[dict]:
        url = f"{self.API_BASE}/artists/{artist_id}/songs?page={page}&per_page=50&sort=title"
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.get(url, headers=self._auth_headers(), timeout=20)
                resp.raise_for_status()
                data = resp.json()
                songs = (data.get("response") or {}).get("songs") or []
                return songs
            except Exception as exc:
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * (attempt + 1))
                else:
                    self.logger.error("Erro ao buscar página %d: %s", page, exc)
        return []

    def organize_by_albums(self, songs: List[dict]) -> List[dict]:
        """Organiza as músicas por álbum."""
        albums_dict = {}
        
        for song in songs:
            album_info = song.get("album") or {}
            album_name = album_info.get("name") or "Singles/Avulsas"
            album_url = album_info.get("url") or ""
            release_date = album_info.get("release_date_for_display")
            
            # Extrair ano da data de lançamento
            year = None
            if release_date:
                year_match = re.search(r"\b(19|20)\d{2}\b", str(release_date))
                if year_match:
                    try:
                        year = int(year_match.group(0))
                    except ValueError:
                        pass
            
            if album_name not in albums_dict:
                albums_dict[album_name] = {
                    "album_title": album_name,
                    "album_url": album_url,
                    "release_year": year,
                    "tracks": []
                }
            
            # Buscar letra da música
            lyrics = self.get_lyrics_from_song(song)
            
            albums_dict[album_name]["tracks"].append({
                "track_number": None,  # Genius não fornece número da faixa consistentemente
                "title": song.get("title", ""),
                "lyrics": lyrics
            })
        
        # Converter para lista e ordenar por ano
        albums_list = list(albums_dict.values())
        albums_list.sort(key=lambda a: (9999 if a.get("release_year") is None else a.get("release_year"), a.get("album_title", "")))
        
        return albums_list

    def get_lyrics_from_song(self, song: dict) -> Optional[str]:
        """Extrai letra de uma música específica do Genius."""
        path = song.get("path")
        if not path:
            return None
        
        url = f"{self.SITE_BASE}{path}"
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.get(url, timeout=25)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                
                # Genius: blocos com data-lyrics-container="true"
                containers = soup.select('[data-lyrics-container="true"]')
                if not containers:
                    # fallback antigo
                    legacy = soup.select_one(".lyrics")
                    if legacy:
                        for br in legacy.find_all("br"):
                            br.replace_with("\n")
                        text = legacy.get_text("\n", strip=True)
                        return _normalize_text(text)
                    return None
                
                parts: list[str] = []
                for block in containers:
                    for br in block.find_all("br"):
                        br.replace_with("\n")
                    # remover notas de rodapé/ads
                    for ann in block.select(".Referent, .annotation, .song_body-lyrics p a, script, style"):
                        ann.decompose()
                    raw = block.get_text("\n", strip=True)
                    if raw:
                        parts.append(raw)
                
                text = "\n".join(parts)
                text = _normalize_text(text)
                return text if text else None
                
            except Exception as exc:
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * (attempt + 1))
                else:
                    self.logger.debug("Falha ao obter letra em %s: %s", url, exc)
        return None


class GeniusLyricsProvider:
    """Cliente para buscar músicas no Genius via API e extrair letras da página pública.

    Requer token de acesso (Bearer) em `GENIUS_ACCESS_TOKEN`.
    - Busca: GET https://api.genius.com/search?q={query}
    - Página da música: https://genius.com{path}
    - Extração: elementos com data-lyrics-container="true"
    """

    API_BASE = "https://api.genius.com"
    SITE_BASE = "https://genius.com"
    DEFAULT_ACCESS_TOKEN = "8pWmFQWeV6i_SpOgNY4-VOwgjusxxYlYS3x7a7QIrPAGNQZNoE-j2UBHROhWVA1K"

    def __init__(self, access_token: Optional[str], max_retries: int = 2, backoff_seconds: float = 1.5) -> None:
        # usa token padrão embutido se não for fornecido
        self.access_token = (access_token or self.DEFAULT_ACCESS_TOKEN).strip()
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.logger = logging.getLogger(self.__class__.__name__)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "DiscographyCrawler/1.0 (+https://example.com)",
        })

    def is_enabled(self) -> bool:
        return bool(self.access_token)

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}

    def _search_song_path(self, artist: str, title: str) -> Optional[str]:
        """Usa a API de busca do Genius para obter o path da música mais relevante."""
        if not self.access_token:
            return None
        query = f"{artist} {title}"
        url = f"{self.API_BASE}/search?{urlencode({'q': query})}"
        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.get(url, headers=self._auth_headers(), timeout=20)
                if resp.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {resp.status_code}")
                resp.raise_for_status()
                data = resp.json()
                hits = (data.get("response") or {}).get("hits") or []
                for hit in hits:
                    result = hit.get("result") or {}
                    # Heurística: garantir que o artista principal combine com o desejado
                    primary = (result.get("primary_artist") or {}).get("name", "").lower()
                    full_title = (result.get("full_title") or "").lower()
                    if artist.lower().split(" ")[0] in primary or artist.lower() in full_title:
                        path = result.get("path")
                        if path:
                            return path
                # fallback: primeiro hit
                if hits:
                    result = hits[0].get("result") or {}
                    path = result.get("path")
                    if path:
                        return path
                return None
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * (attempt + 1))
        self.logger.debug("Falha na busca Genius para '%s' - '%s': %s", artist, title, last_exc)
        return None

    def get_lyrics(self, artist: str, title: str) -> Optional[str]:
        if not self.is_enabled():
            return None
        path = self._search_song_path(artist, title)
        if not path:
            return None
        url = f"{self.SITE_BASE}{path}"
        # baixar e extrair letra
        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.get(url, timeout=25)
                if resp.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {resp.status_code}")
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                # Genius: blocos com data-lyrics-container="true"
                containers = soup.select('[data-lyrics-container="true"]')
                if not containers:
                    # fallback antigo
                    legacy = soup.select_one(".lyrics")
                    if legacy:
                        for br in legacy.find_all("br"):
                            br.replace_with("\n")
                        text = legacy.get_text("\n", strip=True)
                        return _normalize_text(text)
                    return None
                parts: list[str] = []
                for block in containers:
                    for br in block.find_all("br"):
                        br.replace_with("\n")
                    # remover notas de rodapé/ads
                    for ann in block.select(".Referent, .annotation, .song_body-lyrics p a, script, style"):
                        ann.decompose()
                    raw = block.get_text("\n", strip=True)
                    if raw:
                        parts.append(raw)
                text = "\n".join(parts)
                text = _normalize_text(text)
                return text if text else None
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * (attempt + 1))
        self.logger.debug("Falha ao obter letra no Genius para '%s' - '%s': %s", artist, title, last_exc)
        return None


def _normalize_text(text: str) -> str:
    # remove múltiplas linhas em branco e espaços em excesso
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.split("\n")]
    out: list[str] = []
    for ln in lines:
        if ln == "":
            if out and out[-1] == "":
                continue
            out.append("")
        else:
            out.append(ln)
    return "\n".join(out).strip()
