from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

from lyric_overlay.config import FETCHED_LRC_DIR, LRC_DIR, TOKEN_CACHE, ensure_directories, load_config
from lyric_overlay.lyrics import LyricsRepository, sanitize_filename


SPOTIFY_READ_SCOPES = "user-library-read playlist-read-private playlist-read-collaborative"
DEFAULT_REPORT_PATH = FETCHED_LRC_DIR / "lrc_download_report.json"


@dataclass(slots=True)
class SpotifyTrack:
    track_id: str
    title: str
    artist: str
    album: str
    duration_ms: int
    source: str
    spotify_url: str


@dataclass(slots=True)
class DownloadResult:
    track_id: str
    title: str
    artist: str
    album: str
    source: str
    status: str
    detail: str
    spotify_url: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download synced .lrc files from LRCLIB for Spotify liked songs and playlists."
    )
    parser.add_argument(
        "--source",
        choices=("all", "liked", "playlists"),
        default="all",
        help="Spotify track source to read. Default: all.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of unique tracks to process. 0 means no limit.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help=f"JSON report path. Default: {DEFAULT_REPORT_PATH}",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Do not write a JSON report.",
    )
    return parser.parse_args()


def create_spotify_client() -> Spotify:
    config = load_config()
    if not config.spotify_client_id or not config.spotify_client_secret or not config.spotify_redirect_uri:
        raise RuntimeError(
            "Spotify credentials are incomplete in .env. Fill SPOTIFY_CLIENT_ID, "
            "SPOTIFY_CLIENT_SECRET, and SPOTIFY_REDIRECT_URI first."
        )

    auth_manager = SpotifyOAuth(
        client_id=config.spotify_client_id,
        client_secret=config.spotify_client_secret,
        redirect_uri=config.spotify_redirect_uri,
        scope=SPOTIFY_READ_SCOPES,
        cache_path=str(TOKEN_CACHE),
        open_browser=True,
    )
    return Spotify(auth_manager=auth_manager, requests_timeout=10)


def iter_liked_tracks(spotify: Spotify) -> Iterable[SpotifyTrack]:
    offset = 0
    limit = 50
    while True:
        payload = spotify.current_user_saved_tracks(limit=limit, offset=offset)
        items = payload.get("items") or []
        for item in items:
            track = track_from_payload(item.get("track"), source="liked")
            if track is not None:
                yield track

        if not payload.get("next"):
            break
        offset += limit


def iter_playlist_tracks(spotify: Spotify) -> Iterable[SpotifyTrack]:
    playlist_offset = 0
    playlist_limit = 50
    while True:
        playlists = spotify.current_user_playlists(limit=playlist_limit, offset=playlist_offset)
        for playlist in playlists.get("items") or []:
            playlist_id = playlist.get("id")
            playlist_name = playlist.get("name") or "playlist"
            if not playlist_id:
                continue

            track_offset = 0
            track_limit = 100
            while True:
                tracks = spotify.playlist_items(
                    playlist_id,
                    fields="items(track(id,name,artists(name),album(name),duration_ms,"
                    "external_urls,is_local,type)),next",
                    limit=track_limit,
                    offset=track_offset,
                    additional_types=("track",),
                )
                for item in tracks.get("items") or []:
                    track = track_from_payload(item.get("track"), source=f"playlist:{playlist_name}")
                    if track is not None:
                        yield track

                if not tracks.get("next"):
                    break
                track_offset += track_limit

        if not playlists.get("next"):
            break
        playlist_offset += playlist_limit


def track_from_payload(payload: dict[str, Any] | None, source: str) -> SpotifyTrack | None:
    if not payload or payload.get("type") != "track" or payload.get("is_local"):
        return None

    track_id = str(payload.get("id") or "")
    title = str(payload.get("name") or "").strip()
    artists = payload.get("artists") or []
    artist = ", ".join(str(item.get("name") or "").strip() for item in artists if item.get("name"))
    if not track_id or not title or not artist:
        return None

    album = str((payload.get("album") or {}).get("name") or "").strip()
    external_urls = payload.get("external_urls") or {}
    return SpotifyTrack(
        track_id=track_id,
        title=title,
        artist=artist,
        album=album,
        duration_ms=int(payload.get("duration_ms") or 0),
        source=source,
        spotify_url=str(external_urls.get("spotify") or ""),
    )


def collect_tracks(spotify: Spotify, source: str, limit: int) -> list[SpotifyTrack]:
    seen: set[str] = set()
    tracks: list[SpotifyTrack] = []
    iterators: list[Iterable[SpotifyTrack]] = []
    if source in {"all", "liked"}:
        iterators.append(iter_liked_tracks(spotify))
    if source in {"all", "playlists"}:
        iterators.append(iter_playlist_tracks(spotify))

    for iterator in iterators:
        for track in iterator:
            if track.track_id in seen:
                continue
            seen.add(track.track_id)
            tracks.append(track)
            if limit > 0 and len(tracks) >= limit:
                return tracks
    return tracks


def exact_lrc_paths(track: SpotifyTrack) -> list[Path]:
    filename = f"{sanitize_filename(track.artist)} - {sanitize_filename(track.title)}.lrc"
    return [LRC_DIR / filename, FETCHED_LRC_DIR / filename]


def download_lrc(track: SpotifyTrack, repository: LyricsRepository) -> DownloadResult:
    for path in exact_lrc_paths(track):
        if path.exists():
            return result_for(track, "skipped_existing", path.name)

    lyrics = repository.get_lyrics(
        artist=track.artist,
        title=track.title,
        duration_ms=track.duration_ms,
    )
    if lyrics.is_empty:
        return result_for(track, "missing", "LRCLIB synced lyrics not found")
    if lyrics.source.startswith("local:"):
        return result_for(track, "skipped_existing", lyrics.source.removeprefix("local:"))
    return result_for(track, "downloaded", lyrics.source)


def result_for(track: SpotifyTrack, status: str, detail: str) -> DownloadResult:
    return DownloadResult(
        track_id=track.track_id,
        title=track.title,
        artist=track.artist,
        album=track.album,
        source=track.source,
        status=status,
        detail=detail,
        spotify_url=track.spotify_url,
    )


def write_report(path: Path, results: list[DownloadResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": summarize(results),
        "tracks": [asdict(result) for result in results],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def summarize(results: list[DownloadResult]) -> dict[str, int]:
    summary = {
        "total": len(results),
        "downloaded": 0,
        "missing": 0,
        "skipped_existing": 0,
        "error": 0,
    }
    for result in results:
        summary[result.status] = summary.get(result.status, 0) + 1
    return summary


def print_summary(results: list[DownloadResult]) -> None:
    summary = summarize(results)
    print("\nSummary")
    print(f"  Total tracks:      {summary['total']}")
    print(f"  Downloaded:        {summary['downloaded']}")
    print(f"  Existing skipped:  {summary['skipped_existing']}")
    print(f"  Missing:           {summary['missing']}")
    print(f"  Errors:            {summary['error']}")


def main() -> int:
    args = parse_args()
    ensure_directories()
    spotify = create_spotify_client()
    tracks = collect_tracks(spotify=spotify, source=args.source, limit=args.limit)
    repository = LyricsRepository(lrclib_enabled=True, auto_save_fetched_lrc=True)
    results: list[DownloadResult] = []

    print(f"Found {len(tracks)} unique Spotify tracks.")
    for index, track in enumerate(tracks, start=1):
        label = f"{track.artist} - {track.title}"
        print(f"[{index}/{len(tracks)}] {label}")
        try:
            result = download_lrc(track, repository)
        except Exception as exc:
            result = result_for(track, "error", str(exc))
        results.append(result)
        print(f"  {result.status}: {result.detail}")

    if not args.no_report:
        write_report(args.report, results)
        print(f"\nReport written to {args.report}")
    print_summary(results)
    return 0 if not any(result.status == "error" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
