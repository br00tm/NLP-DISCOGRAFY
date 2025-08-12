from __future__ import annotations

import argparse
import json
import logging
import os
import re
import csv
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from dotenv import load_dotenv
from tqdm import tqdm

from scraper.crawler import HttpCrawler
from scraper.discography_scraper import WikipediaDiscographyScraper
from scraper.genius_provider import GeniusLyricsProvider



@dataclass
class Track:
    track_number: Optional[int]
    title: str
    lyrics: Optional[str] = None


@dataclass
class Album:
    album_title: str
    album_url: str
    release_year: Optional[int]
    tracks: List[Track]


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def sanitize_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[\\/:*?\"<>|]", "_", name)
    name = re.sub(r"\s+", " ", name)
    return name[:200] if len(name) > 200 else name


def normalize_key(text: str) -> str:
    norm = unicodedata.normalize("NFD", text or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", norm).strip().lower()


def write_album_csv(album: Album, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    base = album.album_title or "album"
    if album.release_year:
        base = f"{base} ({album.release_year})"
    filename = sanitize_filename(base) + ".csv"
    path = out_dir / filename

    # evitar sobrescrever se houver duplicados
    counter = 1
    while path.exists():
        filename = sanitize_filename(base) + f"_{counter}.csv"
        path = out_dir / filename
        counter += 1

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["track_number", "title", "lyrics"]) 
        for track in album.tracks:
            writer.writerow([track.track_number if track.track_number is not None else "", track.title, track.lyrics or ""]) 
    return path


def scrape_and_merge(
    sources: List[str],
    crawler: HttpCrawler,
    include_lyrics: bool,
    lyrics_source: Optional[str],  # None, 'vagalume_api', 'genius', 'vagalume_web', 'genius_vagalume'
    prefer_api_lyrics: bool,
    prefer_genius: bool,
    api_key: Optional[str],
    genius_token: Optional[str],
) -> List[Album]:
    genius_api = GeniusLyricsProvider(access_token=genius_token)

    scraper_map = {
        "wikipedia": WikipediaDiscographyScraper(crawler)
    }

    # acumulador por álbum
    albums_acc: Dict[str, dict] = {}

    for src in sources:
        scraper = scraper_map[src]
        album_urls = list(scraper.iter_album_urls())
        logging.info("[%s] Álbuns encontrados: %d", src, len(album_urls))
        for album_url in tqdm(album_urls, desc=f"Álbuns ({src})"):
            album_dict = scraper.parse_album_page(album_url)
            if not album_dict:
                continue
            album_title = album_dict.get("album_title", "").strip()
            if not album_title:
                continue
            key = normalize_key(album_title)
            acc = albums_acc.get(key)
            if not acc:
                acc = {
                    "album_title": album_title,
                    "album_url": album_dict.get("album_url", album_url),
                    "release_year": album_dict.get("release_year"),
                    "tracks": {},  # title_key -> {track_number, title, lyrics}
                }
                albums_acc[key] = acc
            else:
                if not acc.get("release_year") and album_dict.get("release_year"):
                    acc["release_year"] = album_dict.get("release_year")

            for trk in album_dict.get("tracks", []) or []:
                title = (trk.get("title") or "").strip()
                if not title:
                    continue
                tkey = normalize_key(title)
                dest = acc["tracks"].get(tkey)
                if not dest:
                    acc["tracks"][tkey] = {
                        "track_number": trk.get("track_number"),
                        "title": title,
                        "lyrics": trk.get("lyrics"),
                    }
                else:
                    if dest.get("track_number") is None and trk.get("track_number") is not None:
                        dest["track_number"] = trk.get("track_number")
                    if not dest.get("lyrics") and trk.get("lyrics"):
                        dest["lyrics"] = trk.get("lyrics")

    # conversor para objetos Album + preenchimento de letras de acordo com a política
    albums: List[Album] = []
    for _, acc in albums_acc.items():
        tracks_list = list(acc["tracks"].values())
        tracks_list.sort(key=lambda t: (9999 if t.get("track_number") is None else t.get("track_number"), normalize_key(t.get("title"))))

        completed_tracks: List[Track] = []
        for t in tracks_list:
            title = t.get("title")
            lyrics: Optional[str] = t.get("lyrics")

            if include_lyrics and lyrics_source:
                # usar somente a fonte escolhida
                if lyrics_source == "vagalume_api" and vagalume_api.is_enabled():
                    lyrics = vagalume_api.get_lyrics("Engenheiros do Hawaii", title)
                elif lyrics_source == "genius" and genius_api.is_enabled():
                    lyrics = genius_api.get_lyrics("Engenheiros do Hawaii", title)
                elif lyrics_source == "vagalume_web":
                    lyrics = vagalume_web.get_lyrics("Engenheiros do Hawaii", title)
                elif lyrics_source == "genius_vagalume":
                    # usa genius para resolver a canção correta (título pode já resolver), mas extrai letra do vagalume
                    # se genius retornar, mantemos título original e apenas confiamos na correspondência
                    if genius_api.is_enabled():
                        _ = genius_api.get_lyrics("Engenheiros do Hawaii", title)  # força busca/prior match
                    lyrics = vagalume_web.get_lyrics("Engenheiros do Hawaii", title)
                else:
                    # fallback: mantém o que já tiver
                    pass
            else:
                # política antiga (preferências) se nenhuma fonte única foi definida
                lyrics = t.get("lyrics")
                if prefer_genius and genius_api.is_enabled():
                    g_lyrics = genius_api.get_lyrics("Engenheiros do Hawaii", title)
                    if g_lyrics:
                        lyrics = g_lyrics
                elif (prefer_api_lyrics or (include_lyrics and not lyrics)) and vagalume_api.is_enabled():
                    v_lyrics = vagalume_api.get_lyrics("Engenheiros do Hawaii", title)
                    if v_lyrics:
                        lyrics = v_lyrics
                elif include_lyrics and not lyrics and genius_api.is_enabled():
                    g_lyrics = genius_api.get_lyrics("Engenheiros do Hawaii", title)
                    if g_lyrics:
                        lyrics = g_lyrics

            completed_tracks.append(Track(track_number=t.get("track_number"), title=title, lyrics=lyrics))

        albums.append(
            Album(
                album_title=acc.get("album_title"),
                album_url=acc.get("album_url"),
                release_year=acc.get("release_year"),
                tracks=completed_tracks,
            )
        )

    albums.sort(key=lambda a: (9999 if a.release_year is None else a.release_year, normalize_key(a.album_title)))
    return albums


def main() -> None:
    parser = argparse.ArgumentParser(description="Coleta discografia dos Engenheiros do Hawaii de múltiplas fontes (Wikipédia, Vagalume, Letras) e letras.")
    parser.add_argument("--out", default="data/engenheiros_discografia.json", help="Arquivo de saída JSON")
    parser.add_argument("--include-lyrics", action="store_true", help="Ativar busca de letras (usando provedores configurados)")
    parser.add_argument("--lyrics-source", choices=["vagalume_api", "genius", "vagalume_web", "genius_vagalume"], help="Origem ÚNICA das letras; quando definida, ignora letras de outras fontes")
    parser.add_argument("--prefer-api-lyrics", action="store_true", help="Sempre preferir letras vindas da API do Vagalume quando disponível (se --lyrics-source não for usado)")
    parser.add_argument("--prefer-genius", action="store_true", help="Sempre preferir letras vindas do Genius quando disponível (se --lyrics-source não for usado)")
    parser.add_argument("--source", choices=["wikipedia", "vagalume", "letras", "all"], default="wikipedia", help="Fonte de dados")
    parser.add_argument("--max-albums", type=int, default=0, help="Limitar número de álbuns por fonte (0 = todos)")
    parser.add_argument("--csv-dir", default="data/albuns_csv", help="Diretório para salvar CSVs por álbum")
    parser.add_argument("--verbose", action="store_true", help="Log detalhado")
    args = parser.parse_args()

    load_dotenv()
    configure_logging(args.verbose)

    api_key = os.getenv("VAGALUME_API_KEY")
    genius_token = os.getenv("GENIUS_ACCESS_TOKEN")

    if args.lyrics_source == "vagalume_api" and not api_key:
        logging.info("--lyrics-source=vagalume_api definido, mas VAGALUME_API_KEY ausente; letras serão ignoradas.")

    crawler = HttpCrawler()

    if args.source == "all":
        sources = ["letras", "vagalume", "wikipedia"]
    else:
        sources = [args.source]

    albums_all = scrape_and_merge(
        sources,
        crawler,
        include_lyrics=args.include_lyrics,
        lyrics_source=args.lyrics_source,
        prefer_api_lyrics=args.prefer_api_lyrics,
        prefer_genius=args.prefer_genius,
        api_key=api_key,
        genius_token=genius_token,
    )

    if args.max_albums > 0:
        albums = albums_all[: args.max_albums]
    else:
        albums = albums_all

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as f:
        json.dump([asdict(a) for a in albums], f, ensure_ascii=False, indent=2)

    csv_out_dir = Path(args.csv_dir)
    saved_paths: List[Path] = []
    for album in tqdm(albums, desc="Exportando CSVs"):
        csv_path = write_album_csv(album, csv_out_dir)
        saved_paths.append(csv_path)

    logging.info("Concluído. Arquivo JSON salvo em: %s", out_path)
    logging.info("CSVs gerados: %d (em %s)", len(saved_paths), csv_out_dir)


if __name__ == "__main__":
    main() 