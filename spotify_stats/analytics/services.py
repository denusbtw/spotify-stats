import asyncio
import base64
import datetime
import json
import logging
import time
import uuid
from datetime import timedelta
from typing import Iterable, Any

import aiohttp
import requests
from aiohttp import ClientError
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from django.db.models import QuerySet, Sum, Count, FloatField, Avg, Min, Max
from django.db.models.functions import (
    Coalesce,
    Round,
    Cast,
    TruncYear,
    TruncMonth,
    TruncDate,
)
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from tenacity import retry, retry_if_exception_type, wait_fixed, stop_after_attempt

from spotify_stats.analytics.models import (
    SpotifyProfile,
    FileUploadJob,
    ListeningHistory,
)
from spotify_stats.catalog.models import Artist, Track, Album, AlbumArtist, TrackArtist


log = logging.getLogger()


def split_into_batches(items: list, batch_size: int):
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]


def get_objects_map(model, ids: Iterable[str]) -> dict:
    return {obj.spotify_id: obj for obj in model.objects.filter(spotify_id__in=ids)}


class SpotifyClient:

    def __init__(self):
        self.base_url = "https://api.spotify.com"
        self.client_id = settings.SPOTIFY_CLIENT_ID
        self.client_secret = settings.SPOTIFY_CLIENT_SECRET
        self.access_token = None
        self.token_expires_at = 0

    async def get_album(self, spotify_id: str) -> dict:
        url = f"{self.base_url}/v1/albums/{spotify_id}"
        headers = await self._get_headers()
        return await self._make_request("get", url, headers=headers)

    async def get_several_albums(self, spotify_ids: list[str]) -> dict:
        url = f"{self.base_url}/v1/albums"
        headers = await self._get_headers()
        params = {
            "ids": ",".join([id_ for id_ in spotify_ids]),
        }
        return await self._make_request("get", url, headers=headers, params=params)

    async def get_artist(self, spotify_id: str) -> dict:
        url = f"{self.base_url}/v1/artists/{spotify_id}"
        headers = await self._get_headers()
        return await self._make_request("get", url, headers=headers)

    async def get_several_artists(self, spotify_ids: list[str]) -> dict:
        url = f"{self.base_url}/v1/artists"
        headers = await self._get_headers()
        params = {
            "ids": ",".join([str(id_) for id_ in spotify_ids]),
        }
        return await self._make_request("get", url, headers=headers, params=params)

    async def get_track(self, spotify_id: str) -> dict:
        url = f"{self.base_url}/v1/tracks/{spotify_id}"
        headers = await self._get_headers()
        return await self._make_request("get", url, headers=headers)

    async def get_several_tracks(self, spotify_ids: list[str]) -> dict:
        url = f"{self.base_url}/v1/tracks"
        headers = await self._get_headers()
        params = {
            "ids": ",".join([str(id_) for id_ in spotify_ids]),
        }
        return await self._make_request("get", url, headers=headers, params=params)

    async def _make_request(
        self,
        method: str,
        url: str,
        headers: dict = None,
        params: dict = None,
        data: dict = None,
    ):
        async with aiohttp.ClientSession() as session:
            async with getattr(session, method.lower())(
                url, headers=headers, params=params, data=data
            ) as response:
                response.raise_for_status()
                return await response.json()

    async def _get_headers(self) -> dict:
        access_token = await self.get_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}
        return headers

    async def get_access_token(self) -> str | None:
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token

        cached_access_token = cache.get("spotify_access_token")
        if cached_access_token:
            self.access_token = cached_access_token
            return cached_access_token

        basic_string = f"{self.client_id}:{self.client_secret}"
        basic_bytes = basic_string.encode("utf-8")
        basic_bytes_encoded = base64.b64encode(basic_bytes)
        basic_string_decoded = basic_bytes_encoded.decode("utf-8")

        url = "https://accounts.spotify.com/api/token"
        headers = {"Authorization": f"Basic {basic_string_decoded}"}
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            response_data = await self._make_request(
                "post", url, headers=headers, data=data
            )

            access_token = response_data.get("access_token")
            expires_in = response_data.get("expires_in")

            if not all([access_token, expires_in]):
                log.error(f"Missing required token data in response.")
                return None

            self.access_token = access_token
            self.token_expires_at = time.time() + expires_in

            cache.set("spotify_access_token", self.access_token, expires_in - 60)

            return self.access_token

        except Exception as e:
            log.error(f"Failed to get new access token: {e}")
        return None


class UserSpotifyClient:

    def __init__(self, spotify_profile: SpotifyProfile):
        self.profile = spotify_profile
        self.base_url = "https://api.spotify.com"

    def _get_access_token(self) -> str | None:
        if not self.profile.is_token_expired:
            return self.profile.access_token

        log.info(
            f"Token for {self.profile.user.email} is expired. Attempting to refresh."
        )

        response_data = SpotifyAuthService.refresh_access_token(
            self.profile.refresh_token
        )

        if not response_data:
            log.error(f"Failed to refresh token for {self.profile.user.email}.")
            return None

        self.profile.access_token = response_data.get("access_token")
        expires_in = response_data.get("expires_in")
        self.profile_expires_at = timezone.now() + timedelta(seconds=expires_in)

        refresh_token = response_data.get("refresh_token")
        if refresh_token:
            self.profile.refresh_token = refresh_token

        self.profile.save()
        log.info(f"Token for {self.profile.user.email} successfully refreshed.")

        return self.profile.access_token

    def _get_headers(self) -> dict:
        access_token = self._get_access_token()
        log.info(f"Access token: {access_token}")
        if access_token:
            return {"Authorization": f"Bearer {access_token}"}
        return {}


class SpotifyAuthService:
    client_id = settings.SPOTIFY_CLIENT_ID
    client_secret = settings.SPOTIFY_CLIENT_SECRET
    redirect_uri = settings.SPOTIFY_REDIRECT_URI
    token_url = "https://accounts.spotify.com/api/token"
    user_info_url = "https://api.spotify.com/v1/me"

    @classmethod
    def get_auth_url(
        cls, scope="user-read-private user-read-email user-read-recently-played"
    ):
        url = (
            "https://accounts.spotify.com/authorize"
            f"?response_type=code&client_id={cls.client_id}"
            f"&scope={scope}&redirect_uri={cls.redirect_uri}"
            "&show_dialog=true"
        )
        return url

    @classmethod
    def get_user_tokens(cls, code):
        basic_string = f"{cls.client_id}:{cls.client_secret}"
        basic_bytes = basic_string.encode("utf-8")
        basic_bytes_encoded = base64.b64encode(basic_bytes)
        basic_string_decoded = basic_bytes_encoded.decode("utf-8")

        headers = {
            "Authorization": f"Basic {basic_string_decoded}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": cls.redirect_uri,
        }

        try:
            response = requests.post(cls.token_url, headers=headers, data=data)
            response_data = response.json()
            log.info(f"Response data: {response_data}")
            response.raise_for_status()
            return response_data
        except requests.exceptions.RequestException as e:
            log.error(f"Error getting Spotify tokens: {e}")
            return None

    @classmethod
    def get_user_info(cls, access_token):
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            response = requests.get(cls.user_info_url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            log.error(f"Error getting Spotify user info: {e}")
            return None

    @classmethod
    def refresh_access_token(cls, refresh_token):
        basic_string = f"{cls.client_id}:{cls.client_secret}"
        basic_bytes = basic_string.encode("utf-8")
        basic_bytes_encoded = base64.b64encode(basic_bytes)
        basic_string_decoded = basic_bytes_encoded.decode("utf-8")

        headers = {
            "Authorization": f"Basic {basic_string_decoded}",
            "Content-Type": "application/x-www-form-urlencoded.",
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        try:
            response = requests.post(cls.token_url, headers=headers, data=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            log.error(f"Error refreshing Spotify token: {e}")
            return None


class SpotifyAPIParser:

    def parse_artist(self, data: dict) -> dict:
        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "cover_url": self.extract_cover_url(data),
        }

    def parse_album(self, data: dict) -> dict:
        artists = [self.parse_artist(d) for d in data.get("artists")]

        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "cover_url": self.extract_cover_url(data),
            "artists": artists,
        }

    def parse_track(self, data: dict) -> dict:
        album = self.parse_album(data.get("album", {}))
        artists = [self.parse_artist(d) for d in data.get("artists")]

        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "album": album,
            "artists": artists,
        }

    def extract_cover_url(self, data: dict) -> str:
        cover_url = ""
        if data.get("images"):
            cover_url = data["images"][0].get("url", "")
        return cover_url


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
            self.artists_map[parsed_artist["id"]] = parsed_artist

    def process_several_tracks_data(self, tracks_data: list[dict]):
        for track_data in tracks_data:
            self.process_track_data(track_data)

    def process_track_data(self, track_data: dict):
        parsed_track = self.parser.parse_track(track_data)

        parsed_album = parsed_track.get("album")
        if parsed_album:
            self.albums_map[parsed_album["id"]] = parsed_album

            self.tracks_map[parsed_track["id"]] = {
                "track_id": parsed_track["id"],
                "album_id": parsed_album["id"],
            }

        for parsed_artist in parsed_track.get("artists"):
            self.artists_map[parsed_artist["id"]] = parsed_artist
            self.track_artists_relations.append(
                {
                    "track_id": parsed_track["id"],
                    "artist_id": parsed_artist["id"],
                }
            )

        if parsed_album:
            for parsed_artist in parsed_album.get("artists"):
                self.artists_map[parsed_artist["id"]] = parsed_artist
                self.album_artists_relations.append(
                    {
                        "album_id": parsed_album["id"],
                        "artist_id": parsed_artist["id"],
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


class SpotifyDBService:

    def save_enriched_data(
        self,
        artists: list[dict],
        albums: list[dict],
        tracks: list[dict],
        album_artists_relations: list[dict],
        track_artists_relations: list[dict],
    ):
        try:
            self.bulk_create_artists(artists)
            self.bulk_create_albums(albums)
            self.bulk_update_tracks(tracks)
            self.bulk_create_albums_artists(album_artists_relations)
            self.bulk_create_track_artists(track_artists_relations)

            log.info("Successfully saved enriched Spotify metadata to the database.")

        except Exception as e:
            log.error(f"Failed to save enriched data: {e}")
            raise

    def bulk_create_artists(self, artists_data: list[dict]) -> None:
        existing_artist_spotify_ids = set(
            Artist.objects.filter(
                spotify_id__in=[a["id"] for a in artists_data]
            ).values_list("spotify_id", flat=True)
        )

        artists_to_create = [
            Artist(
                spotify_id=data["id"],
                name=data["name"],
            )
            for data in artists_data
            if data["id"] not in existing_artist_spotify_ids
        ]

        if artists_to_create:
            Artist.objects.bulk_create(artists_to_create, ignore_conflicts=True)
            log.info(f"Created {len(artists_to_create)} new artists.")

    def bulk_update_artists(self, artists_data: list[dict]) -> None:
        unique_artist_ids = {data["id"] for data in artists_data}
        artists_map = get_objects_map(Artist, unique_artist_ids)

        artists_to_update = []
        for data in artists_data:
            artist = artists_map.get(data["id"])
            if artist:
                artist.cover_url = data["cover_url"]
                artists_to_update.append(artist)

        if artists_to_update:
            Artist.objects.bulk_update(
                artists_to_update, batch_size=500, fields=["cover_url"]
            )
            log.info(f"Updated {len(artists_to_update)} artists.")

    def bulk_create_albums(self, albums_data: list[dict]) -> None:
        existing_album_spotify_ids = set(
            Album.objects.filter(
                spotify_id__in=[a["id"] for a in albums_data]
            ).values_list("spotify_id", flat=True)
        )

        albums_to_create = [
            Album(
                spotify_id=data["id"],
                name=data["name"],
                cover_url=data["cover_url"],
            )
            for data in albums_data
            if data["id"] not in existing_album_spotify_ids
        ]

        if albums_to_create:
            Album.objects.bulk_create(albums_to_create, ignore_conflicts=True)
            log.info(f"Created {len(albums_to_create)} new albums.")

    def bulk_update_tracks(self, tracks_data: list[dict]) -> None:
        unique_track_ids = {r["track_id"] for r in tracks_data}
        unique_album_ids = {r["album_id"] for r in tracks_data}

        tracks_map = get_objects_map(Track, unique_track_ids)
        albums_map = get_objects_map(Album, unique_album_ids)

        tracks_to_update = []
        for r in tracks_data:
            track = tracks_map.get(r["track_id"])
            album = albums_map.get(r["album_id"])
            if track and album:
                track.album = album
                tracks_to_update.append(track)

        if tracks_to_update:
            Track.objects.bulk_update(tracks_to_update, fields=["album"])
            log.info(f"Updated {len(tracks_to_update)} tracks.")

    def bulk_create_albums_artists(self, relations_data: list[dict]) -> None:
        unique_album_ids = {data["album_id"] for data in relations_data}
        unique_artist_ids = {data["artist_id"] for data in relations_data}

        albums_map = get_objects_map(Album, unique_album_ids)
        artists_map = get_objects_map(Artist, unique_artist_ids)

        relations_to_create = []
        for data in relations_data:
            album = albums_map[data["album_id"]]
            artist = artists_map[data["artist_id"]]

            if album and artist:
                relations_to_create.append(
                    AlbumArtist(album=album, artist=artist),
                )

        if relations_to_create:
            AlbumArtist.objects.bulk_create(relations_to_create, ignore_conflicts=True)
            log.info(f"Created {len(relations_to_create)} albums artists.")

    def bulk_create_track_artists(self, relations_data: list[dict]) -> None:
        unique_track_ids = {data["track_id"] for data in relations_data}
        unique_artist_ids = {data["artist_id"] for data in relations_data}

        tracks_map = get_objects_map(Track, unique_track_ids)
        artists_map = get_objects_map(Artist, unique_artist_ids)

        relations_to_create = []
        for data in relations_data:
            track = tracks_map[data["track_id"]]
            artist = artists_map[data["artist_id"]]

            if track and artist:
                relations_to_create.append(
                    TrackArtist(track=track, artist=artist),
                )

        if relations_to_create:
            TrackArtist.objects.bulk_create(relations_to_create, ignore_conflicts=True)
            log.info(f"Created {len(relations_to_create)} tracks artists.")


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
            f"Retrying {retry_state.fn.__name__} in {retry_state.seconds.since_start}s. "
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
            f"Retrying {retry_state.fn.__name__} in {retry_state.seconds.since_start}s. "
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


class FileProcessingService:

    def process_file_upload_jobs(self, job_ids: list[uuid.UUID]) -> None:
        jobs = FileUploadJob.objects.filter(id__in=job_ids)

        for job in jobs:
            job.status = FileUploadJob.Status.PROCESSING
            job.save(update_fields=["status"])

            try:
                success = self.process_single_job(job)
                job_succeeded = success

                if success:
                    log.info("Job %s completed successfully" % job.id)
                else:
                    log.warning("Job %s failed during processing" % job.id)
            except Exception as e:
                log.error("Job %s crashed with exception: %s" % (job.id, e))
                job_succeeded = False

            job.status = (
                FileUploadJob.Status.COMPLETED
                if job_succeeded
                else FileUploadJob.Status.FAILED
            )
            job.save(update_fields=["status"])

    def process_single_job(self, job: FileUploadJob) -> bool:
        streaming_records = self.validate_job_file_content(job)
        if streaming_records is None:
            return False

        existing_track_spotify_ids = set(
            Track.objects.values_list("spotify_id", flat=True)
        )

        tracks_to_create = []
        listening_history_data = []

        for record in streaming_records:
            record = self.validate_record(record)
            if record is None:
                continue

            track_name = record["track_name"]
            spotify_track_uri = record["spotify_track_uri"]
            played_at = record["played_at"]
            ms_played = record["ms_played"]

            spotify_id = spotify_track_uri.split(":")[-1]
            if spotify_id not in existing_track_spotify_ids:
                tracks_to_create.append(
                    Track(
                        spotify_id=spotify_id,
                        name=track_name,
                    )
                )
                existing_track_spotify_ids.add(spotify_id)

            listening_history_data.append(
                {
                    "spotify_id": spotify_id,
                    "played_at": played_at,
                    "ms_played": ms_played,
                }
            )

        Track.objects.bulk_create(
            tracks_to_create, batch_size=500, ignore_conflicts=True
        )

        all_spotify_ids = [data["spotify_id"] for data in listening_history_data]
        tracks_map = {
            track.spotify_id: track
            for track in Track.objects.filter(spotify_id__in=all_spotify_ids)
        }

        listening_history_to_create = []
        for data in listening_history_data:
            track = tracks_map.get(data["spotify_id"])
            if track:
                listening_history_to_create.append(
                    ListeningHistory(
                        user=job.user,
                        track=track,
                        played_at=data["played_at"],
                        ms_played=data["ms_played"],
                    )
                )

        ListeningHistory.objects.bulk_create(
            listening_history_to_create, batch_size=500, ignore_conflicts=True
        )

        log.info(
            "Created %d listening history records." % len(listening_history_to_create)
        )

        return True

    def validate_job_file_content(self, job: FileUploadJob) -> list | None:
        try:
            streaming_records = json.load(job.file)
        except json.JSONDecodeError as e:
            log.error("Invalid JSON in job %s: %s" % (job.id, e))
            return None

        if not isinstance(streaming_records, list):
            log.error(
                "Job %s: Expected list, got %s" % (job.id, type(streaming_records))
            )
            return None

        return streaming_records

    def validate_record(self, record: dict) -> dict | None:
        if not isinstance(record, dict):
            # log.warning("Invalid record type: %s" % type(record))
            return None

        track_name = self.safe_strip(record.get("master_metadata_track_name"))
        spotify_track_uri = self.safe_strip(record.get("spotify_track_uri"))
        ts = self.safe_strip(record.get("ts"))
        ms_played = record.get("ms_played")

        missing_fields = self.get_missing_fields(
            track_name, spotify_track_uri, ts, ms_played
        )

        if missing_fields:
            # log.warning("Missing required fields: %s" % ", ".join(missing_fields))
            return None

        ms_played = self.validate_ms_played(ms_played)
        if ms_played is None:
            return None

        played_at = self.validate_played_at(ts)
        if played_at is None:
            return None

        record_ = {
            "track_name": track_name,
            "spotify_track_uri": spotify_track_uri,
            "played_at": played_at,
            "ms_played": ms_played,
        }

        return record_

    def get_missing_fields(
        self, track_name: str, spotify_track_uri: str, ts: str, ms_played: int
    ) -> list:
        missing_fields = []
        if not ts:
            missing_fields.append("ts")
        if not ms_played:
            missing_fields.append("ms_played")
        if not track_name:
            missing_fields.append("track_name")
        if not spotify_track_uri:
            missing_fields.append("spotify_track_uri")

        return missing_fields

    def validate_ms_played(self, ms_played: int) -> int | None:
        try:
            ms_played = int(ms_played)
            if ms_played < 0:
                # log.warning("Negative ms_played: %d" % ms_played)
                return None
        except (ValueError, TypeError) as e:
            # log.warning("Invalid ms_played '%s': %s" % (ms_played, e))
            return None

        return ms_played

    def validate_played_at(self, played_at: str) -> datetime.datetime | None:
        try:
            played_at = parse_datetime(played_at)
            if played_at is None:
                # log.warning("Invalid datetime format: %s" % played_at)
                return None
        except ValueError as e:
            # log.warning("Datetime parsing error for '%s': '%s'" % (played_at, e))
            return None

        return played_at

    def split_into_batches(self, items: list, batch_size: int):
        for i in range(0, len(items), batch_size):
            yield items[i : i + batch_size]

    def safe_strip(self, value: str) -> str | None:
        return value.strip() if isinstance(value, str) else None


class StreamingAnalyticsService:

    @staticmethod
    def top_artists(base_queryset: QuerySet[ListeningHistory]) -> QuerySet[Artist]:
        return Artist.objects.filter(tracks__history__in=base_queryset).annotate(
            total_ms_played=Sum("tracks__history__ms_played"),
            play_count=Count("tracks__history__id", distinct=True),
        )

    @staticmethod
    def top_albums(base_queryset: QuerySet[ListeningHistory]) -> QuerySet[Album]:
        return (
            Album.objects.filter(tracks__history__in=base_queryset)
            .prefetch_related("artists")
            .annotate(
                total_ms_played=Sum("tracks__history__ms_played"),
                play_count=Count("tracks__history__id", distinct=True),
            )
        )

    @staticmethod
    def top_tracks(base_queryset: QuerySet[ListeningHistory]) -> QuerySet[Track]:
        return (
            Track.objects.filter(history__in=base_queryset)
            .select_related("album")
            .prefetch_related("artists")
            .annotate(
                total_ms_played=Sum("history__ms_played"),
                play_count=Count("history__id", distinct=True),
            )
        )

    @staticmethod
    def listening_stats(base_queryset: QuerySet[ListeningHistory]) -> dict[str, Any]:
        return base_queryset.aggregate(
            total_ms_played=Coalesce(Sum("ms_played"), 0),
            total_mins_played=Coalesce(
                Round(Cast(Sum("ms_played"), FloatField()) / 1000 / 60, 2),
                0,
                output_field=FloatField(),
            ),
            total_hours_played=Coalesce(
                Round(
                    Cast(Sum("ms_played"), FloatField()) / 1000 / 60 / 60,
                    2,
                ),
                0,
                output_field=FloatField(),
            ),
            total_tracks_played=Count("id", distinct=True),
            unique_tracks=Count("track_id", distinct=True),
            unique_artists=Count("track__artists__id", distinct=True),
            unique_albums=Count("track__album_id", distinct=True),
            average_ms_played=Coalesce(Avg("ms_played"), 0, output_field=FloatField()),
            average_mins_played=Coalesce(
                Round(Cast(Avg("ms_played"), FloatField()) / 1000 / 60, 2),
                0,
                output_field=FloatField(),
            ),
            average_hours_played=Coalesce(
                Round(
                    Cast(Avg("ms_played"), FloatField()) / 1000 / 60 / 60,
                    2,
                ),
                0,
                output_field=FloatField(),
            ),
            first_play=Min("played_at"),
            last_play=Max("played_at"),
        )

    @staticmethod
    def yearly_activity(
        base_queryset: QuerySet[ListeningHistory],
    ):
        return (
            base_queryset.annotate(year=TruncYear("played_at"))
            .values("year")
            .annotate(
                total_ms_played=Sum("ms_played"),
                total_mins_played=Coalesce(
                    Round(Cast(Sum("ms_played"), FloatField()) / 1000 / 60, 2),
                    0,
                    output_field=FloatField(),
                ),
                total_hours_played=Coalesce(
                    Round(Cast(Sum("ms_played"), FloatField()) / 1000 / 60 / 60, 2),
                    0,
                    output_field=FloatField(),
                ),
                tracks_played=Count("id"),
            )
            .order_by("year")
        )

    @staticmethod
    def monthly_activity(base_queryset: QuerySet[ListeningHistory]):
        return (
            base_queryset.annotate(month=TruncMonth("played_at"))
            .values("month")
            .annotate(
                total_ms_played=Sum("ms_played"),
                total_mins_played=Coalesce(
                    Round(Cast(Sum("ms_played"), FloatField()) / 1000 / 60, 2),
                    0,
                    output_field=FloatField(),
                ),
                total_hours_played=Coalesce(
                    Round(Cast(Sum("ms_played"), FloatField()) / 1000 / 60 / 60, 2),
                    0,
                    output_field=FloatField(),
                ),
                tracks_played=Count("id"),
            )
            .order_by("month")
        )

    @staticmethod
    def daily_activity(base_queryset: QuerySet[ListeningHistory]):
        return (
            base_queryset.annotate(date=TruncDate("played_at"))
            .values("date")
            .annotate(
                total_ms_played=Sum("ms_played"),
                total_mins_played=Coalesce(
                    Round(Cast(Sum("ms_played"), FloatField()) / 1000 / 60, 2),
                    0,
                    output_field=FloatField(),
                ),
                total_hours_played=Coalesce(
                    Round(Cast(Sum("ms_played"), FloatField()) / 1000 / 60 / 60, 2),
                    0,
                    output_field=FloatField(),
                ),
                tracks_played=Count("id"),
            )
            .order_by("date")
        )
