from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from tqdm import tqdm

from scraper.genius_provider import GeniusDiscographyProvider


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Coleta discografia completa dos Engenheiros do Hawaii usando 100% a API do Genius.")
    parser.add_argument("--out", default="data/engenheiros_genius.json", help="Arquivo de saída JSON")
    parser.add_argument("--csv-dir", default="data/albuns_genius_csv", help="Diretório para salvar CSVs por álbum")
    parser.add_argument("--max-songs", type=int, default=500, help="Máximo de músicas a buscar")
    parser.add_argument("--verbose", action="store_true", help="Log detalhado")
    args = parser.parse_args()

    load_dotenv()
    configure_logging(args.verbose)

    genius_token = os.getenv("GENIUS_ACCESS_TOKEN")
    
    # Usar token embutido como fallback
    genius = GeniusDiscographyProvider(access_token=genius_token)
    
    if not genius.is_enabled():
        logging.error("Token do Genius não disponível. Defina GENIUS_ACCESS_TOKEN no .env")
        return

    logging.info("Buscando álbuns específicos de 'Engenheiros do Hawaii' no Genius...")
    albums_data = genius.search_albums("Engenheiros do Hawaii")
    
    if not albums_data:
        logging.error("Nenhum álbum encontrado para 'Engenheiros do Hawaii'")
        return
    
    logging.info("Encontrados %d álbuns.", len(albums_data))
    
    # Converter para dataclasses
    albums: List[Album] = []
    for album_dict in tqdm(albums_data, desc="Processando álbuns"):
        tracks: List[Track] = []
        for track_dict in album_dict.get("tracks", []):
            tracks.append(Track(
                track_number=track_dict.get("track_number"),
                title=track_dict.get("title", ""),
                lyrics=track_dict.get("lyrics")
            ))
        
        albums.append(Album(
            album_title=album_dict.get("album_title", ""),
            album_url=album_dict.get("album_url", ""),
            release_year=album_dict.get("release_year"),
            tracks=tracks
        ))

    # Salvar JSON
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    with out_path.open("w", encoding="utf-8") as f:
        json.dump([asdict(a) for a in albums], f, ensure_ascii=False, indent=2)

    # Exportar CSV por álbum
    csv_out_dir = Path(args.csv_dir)
    saved_paths: List[Path] = []
    for album in tqdm(albums, desc="Exportando CSVs"):
        csv_path = write_album_csv(album, csv_out_dir)
        saved_paths.append(csv_path)

    logging.info("Concluído!")
    logging.info("JSON salvo em: %s", out_path)
    logging.info("CSVs gerados: %d (em %s)", len(saved_paths), csv_out_dir)
    logging.info("Total de álbuns: %d", len(albums))
    logging.info("Total de faixas: %d", sum(len(a.tracks) for a in albums))


if __name__ == "__main__":
    main()
