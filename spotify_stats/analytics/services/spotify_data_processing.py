import asyncio
import logging
import uuid

from aiohttp import ClientError
from asgiref.sync import sync_to_async
from tenacity import retry, retry_if_exception_type, wait_fixed, stop_after_attempt

from .database import SpotifyDBService
from .spotify_api_parser import SpotifyAPIParser
from .spotify_clients import SpotifyClient
from .utils import split_into_batches
from spotify_stats.catalog.models import Artist

log = logging.getLogger()


class SpotifyDataAggregator:

    def __init__(self, parser: SpotifyAPIParser):
        self.artists_map = {}
        self.albums_map = {}
        self.tracks_map = {}
        self.album_artists_relations = []
        self.track_artists_relations = []
        self.parser = parser

    def process_several_artists_data(self, artists_data: list[dict]):
        for artist_data in artists_data:
            self.process_artist_data(artist_data)

    def process_artist_data(self, artist_data: dict):
        parsed_artist = self.parser.parse_artist(artist_data)
        if parsed_artist:
            self.artists_map[parsed_artist["spotify_id"]] = parsed_artist

    def process_several_tracks_data(self, tracks_data: list[dict]):
        for track_data in tracks_data:
            self.process_track_data(track_data)

    def process_track_data(self, track_data: dict):
        parsed_track = self.parser.parse_track(track_data)

        parsed_album = parsed_track.get("album")
        if parsed_album:
            self.albums_map[parsed_album["spotify_id"]] = parsed_album

            self.tracks_map[parsed_track["spotify_id"]] = {
                "track_spotify_id": parsed_track["spotify_id"],
                "album_spotify_id": parsed_album["spotify_id"],
            }

        for parsed_artist in parsed_track.get("artists"):
            self.artists_map[parsed_artist["spotify_id"]] = parsed_artist
            self.track_artists_relations.append(
                {
                    "track_spotify_id": parsed_track["spotify_id"],
                    "artist_spotify_id": parsed_artist["spotify_id"],
                }
            )

        if parsed_album:
            for parsed_artist in parsed_album.get("artists"):
                self.artists_map[parsed_artist["spotify_id"]] = parsed_artist
                self.album_artists_relations.append(
                    {
                        "album_spotify_id": parsed_album["spotify_id"],
                        "artist_spotify_id": parsed_artist["spotify_id"],
                    }
                )

    def get_aggregated_data(self) -> dict:
        return {
            "artists": list(self.artists_map.values()),
            "albums": list(self.albums_map.values()),
            "tracks": list(self.tracks_map.values()),
            "album_artists_relations": self.album_artists_relations,
            "track_artists_relations": self.track_artists_relations,
        }


class SpotifyAPIProcessor:

    def __init__(
        self,
        spotify_client: SpotifyClient,
        db_service: SpotifyDBService,
        parser: SpotifyAPIParser,
    ):
        self.spotify_client = spotify_client
        self.db_service = db_service
        self.parser = parser
        self.batch_size = 50

    async def enrich_spotify_metadata(self, track_spotify_ids: list[uuid.UUID]) -> None:
        aggregator = SpotifyDataAggregator(parser=self.parser)
        tasks = []
        for batch in split_into_batches(track_spotify_ids, self.batch_size):
            tasks.append(self.process_tracks_batch(batch, aggregator))

        await asyncio.gather(*tasks)

        aggregated_data = aggregator.get_aggregated_data()
        await sync_to_async(self.db_service.save_enriched_data)(
            artists=aggregated_data["artists"],
            albums=aggregated_data["albums"],
            tracks=aggregated_data["tracks"],
            album_artists_relations=aggregated_data["album_artists_relations"],
            track_artists_relations=aggregated_data["track_artists_relations"],
        )

        await self.enrich_artists_covers()

    async def enrich_artists_covers(self) -> None:
        artists_spotify_ids = await sync_to_async(
            lambda: list(
                Artist.objects.without_cover().values_list("spotify_id", flat=True)
            )
        )()

        aggregator = SpotifyDataAggregator(parser=self.parser)
        tasks = []
        for batch in split_into_batches(artists_spotify_ids, self.batch_size):
            tasks.append(self.process_artists_batch(batch, aggregator))

        await asyncio.gather(*tasks)

        aggregated_data = aggregator.get_aggregated_data()
        await sync_to_async(self.db_service.bulk_update_artists)(
            aggregated_data["artists"]
        )

    @retry(
        retry=retry_if_exception_type(ClientError),
        wait=wait_fixed(2),
        stop=stop_after_attempt(3),
        before_sleep=lambda retry_state: log.info(
            f"Retrying {retry_state.fn.__name__} in {retry_state.seconds_since_start}s. "
            f"Attempt #{retry_state.attempt_number}..."
        ),
    )
    async def process_tracks_batch(self, batch: list[str], aggregator) -> None:
        try:
            response_data = await self.spotify_client.get_several_tracks(batch)
            if "tracks" not in response_data:
                raise ClientError

            tracks_data = response_data["tracks"]
            aggregator.process_several_tracks_data(tracks_data)
        except ClientError as e:
            log.warning(f"Client error during tracks batch processing: {e}")
            raise
        except Exception as e:
            log.error(
                f"Failed to process tracks batch {batch}, type: {type(batch)}: {e}"
            )

    @retry(
        retry=retry_if_exception_type(ClientError),
        wait=wait_fixed(2),
        stop=stop_after_attempt(3),
        before_sleep=lambda retry_state: log.info(
            f"Retrying {retry_state.fn.__name__} in {retry_state.seconds_since_start}s. "
            f"Attempt #{retry_state.attempt_number}..."
        ),
    )
    async def process_artists_batch(self, batch: list[str], aggregator) -> None:
        try:
            response_data = await self.spotify_client.get_several_artists(batch)
            if "artists" not in response_data:
                raise ClientError

            artists_data = response_data["artists"]
            aggregator.process_several_artists_data(artists_data)
        except ClientError as e:
            log.warning(f"Client error during artists batch processing: {e}")
            raise
        except Exception as e:
            log.error(
                f"Failed to process artists batch {batch}, type: {type(batch)}: {e}"
            )
