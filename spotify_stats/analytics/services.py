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


class SpotifyAPIProcessor:

    def __init__(self):
        self.spotify_client = AsyncSpotifyClient()
        self.parser = SpotifyAPIParser()
        self.batch_size = 50

    async def enrich_spotify_metadata(self, track_spotify_ids: list[uuid.UUID]) -> None:
        tasks = []
        for batch in self.split_into_batches(track_spotify_ids, self.batch_size):
            tasks.append(self.process_tracks_batch(batch))

        await asyncio.gather(*tasks)

        await self.enrich_artists_covers()

    async def enrich_artists_covers(self) -> None:
        artists_spotify_ids = await sync_to_async(
            lambda: list(
                Artist.objects.without_cover().values_list("spotify_id", flat=True)
            )
        )()

        tasks = []
        for batch in self.split_into_batches(artists_spotify_ids, self.batch_size):
            tasks.append(self.process_artists_batch(batch))

        await asyncio.gather(*tasks)

    @retry(
        retry=retry_if_exception_type(ClientError),
        wait=wait_fixed(2),
        stop=stop_after_attempt(3),
        before_sleep=lambda retry_state: log.info(
            f"Retrying {retry_state.fn.__name__} in {retry_state.seconds.since_start}s. "
            f"Attempt #{retry_state.attempt_number}..."
        ),
    )
    async def process_tracks_batch(self, batch: list[str]) -> None:
        try:
            response = await self.spotify_client.get_several_tracks(batch)
            parsed_response = self.parser.parse_several_tracks_response_data(response)
            await sync_to_async(self.process_and_save_tracks_data)(parsed_response)
        except ClientError as e:
            log.warning(f"Client error during tracks batch processing: {e}")
            raise
        except Exception as e:
            log.error(f"Failed to process batch {batch}: {e}")

    @retry(
        retry=retry_if_exception_type(ClientError),
        wait=wait_fixed(2),
        stop=stop_after_attempt(3),
        before_sleep=lambda retry_state: log.info(
            f"Retrying {retry_state.fn.__name__} in {retry_state.seconds.since_start}s. "
            f"Attempt #{retry_state.attempt_number}..."
        ),
    )
    async def process_artists_batch(self, batch: list[str]) -> None:
        try:
            response = await self.spotify_client.get_several_artists(batch)
            parsed_response = self.parser.parse_several_artists_response_data(response)
            await sync_to_async(self.bulk_update_artists)(parsed_response["artists"])
        except ClientError as e:
            log.warning(f"Client error during artists batch processing: {e}")
            raise
        except Exception as e:
            log.error(f"Failed to process batch {batch}: {e}")

    def process_and_save_tracks_data(self, parsed_response: dict) -> None:
        self.bulk_create_artists(parsed_response["artists_to_create"])
        self.bulk_create_albums(parsed_response["albums_to_create"])

        self.bulk_update_tracks(parsed_response["tracks_to_update"])

        self.bulk_create_albums_artists(parsed_response["album_artists_to_create"])
        self.bulk_create_track_artists(parsed_response["track_artists_to_create"])

    def bulk_update_artists(self, data: list[dict]) -> None:
        unique_artist_ids = {r["id"] for r in data}

        artists_map = self.get_objects_map(Artist, unique_artist_ids)

        artists_to_update = []
        for r in data:
            artist = artists_map.get(r["id"])
            if artist:
                artist.cover_url = r["cover_url"]
                artists_to_update.append(artist)

        Artist.objects.bulk_update(
            artists_to_update, batch_size=500, fields=["cover_url"]
        )

    def bulk_update_tracks(self, data: list[dict]) -> None:
        unique_track_ids = {r["track_id"] for r in data}
        unique_album_ids = {r["album_id"] for r in data}

        tracks_map = self.get_objects_map(Track, unique_track_ids)
        albums_map = self.get_objects_map(Album, unique_album_ids)

        tracks_to_update = []
        for r in data:
            track = tracks_map.get(r["track_id"])
            album = albums_map.get(r["album_id"])
            if track and album:
                track.album = album
                tracks_to_update.append(track)

        Track.objects.bulk_update(tracks_to_update, fields=["album"])

    def bulk_create_artists(self, artists_data: list[dict]) -> None:
        artists_to_create = [
            Artist(
                spotify_id=data["id"],
                name=data["name"],
            )
            for data in artists_data
        ]
        Artist.objects.bulk_create(artists_to_create, ignore_conflicts=True)

    def bulk_create_albums(self, albums_data: list[dict]) -> None:
        albums_to_create = [
            Album(
                spotify_id=data["id"],
                name=data["name"],
                cover_url=data["cover_url"],
            )
            for data in albums_data
        ]
        Album.objects.bulk_create(albums_to_create, ignore_conflicts=True)

    def bulk_create_albums_artists(self, data: list[dict]) -> None:
        unique_album_ids = {r["album_id"] for r in data}
        unique_artist_ids = {r["artist_id"] for r in data}

        albums_map = self.get_objects_map(Album, unique_album_ids)
        artists_map = self.get_objects_map(Artist, unique_artist_ids)

        relations_to_create = [
            AlbumArtist(
                album=albums_map[r["album_id"]],
                artist=artists_map[r["artist_id"]],
            )
            for r in data
        ]

        AlbumArtist.objects.bulk_create(relations_to_create, ignore_conflicts=True)

    def bulk_create_track_artists(self, data: list[dict]) -> None:
        unique_track_ids = {r["track_id"] for r in data}
        unique_artist_ids = {r["artist_id"] for r in data}

        tracks_map = self.get_objects_map(Track, unique_track_ids)
        artists_map = self.get_objects_map(Artist, unique_artist_ids)

        relations_to_create = [
            TrackArtist(
                track=tracks_map[r["track_id"]],
                artist=artists_map[r["artist_id"]],
            )
            for r in data
        ]

        TrackArtist.objects.bulk_create(relations_to_create, ignore_conflicts=True)

    def split_into_batches(self, items: list, batch_size: int):
        for i in range(0, len(items), batch_size):
            yield items[i : i + batch_size]

    def get_objects_map(self, model, ids: Iterable[str]) -> dict:
        return {obj.spotify_id: obj for obj in model.objects.filter(spotify_id__in=ids)}


class BaseSpotifyClient:
    def __init__(self):
        self.base_url = "https://api.spotify.com"
        self.client_id = settings.SPOTIFY_CLIENT_ID
        self.client_secret = settings.SPOTIFY_CLIENT_SECRET
        self.token = None
        self.token_expires_at = 0

    def get_access_token(self) -> str:
        if self.token and time.time() < self.token_expires_at:
            return self.token

        cached_token = cache.get("spotify_access_token")
        if cached_token:
            self.token = cached_token
            return cached_token

        auth_url = "https://accounts.spotify.com/api/token"
        auth_data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        response = requests.post(auth_url, data=auth_data)
        token_data = response.json()

        self.token = token_data["access_token"]
        expires_in = token_data["expires_in"]

        cache.set("spotify_access_token", self.token, expires_in - 60)
        self.token_expires_at = time.time() + expires_in

        return self.token

    def _get_headers(self) -> dict:
        token = self.get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        return headers


class SyncSpotifyClient(BaseSpotifyClient):

    def get_album(self, spotify_id: str) -> dict:
        headers = self._get_headers()
        url = f"{self.base_url}/v1/albums/{spotify_id}"

        response = requests.get(url, headers=headers)
        return response.json()

    def get_several_albums(self, spotify_ids: list[str]) -> list[dict]:
        headers = self._get_headers()
        params = {
            "ids": ",".join([id_ for id_ in spotify_ids]),
        }
        url = f"{self.base_url}/v1/albums"

        response = requests.get(url, headers=headers, params=params)
        return response.json()

    def get_artist(self, spotify_id: str) -> dict:
        headers = self._get_headers()
        url = f"{self.base_url}/v1/artists/{spotify_id}"

        response = requests.get(url, headers=headers)
        return response.json()

    def get_several_artists(self, spotify_ids: list[str]) -> list[dict]:
        headers = self._get_headers()
        params = {
            "ids": ",".join([id_ for id_ in spotify_ids]),
        }
        url = f"{self.base_url}/v1/artists"

        response = requests.get(url, headers=headers, params=params)
        return response.json()

    def get_track(self, spotify_id: str) -> dict:
        headers = self._get_headers()
        url = f"{self.base_url}/v1/tracks/{spotify_id}"

        response = requests.get(url, headers=headers)
        return response.json()

    def get_several_tracks(self, spotify_ids: list[str]) -> list[dict]:
        headers = self._get_headers()
        params = {
            "ids": ",".join([str(id_) for id_ in spotify_ids]),
        }
        url = f"{self.base_url}/v1/tracks"

        response = requests.get(url, headers=headers, params=params)
        return response.json()


class AsyncSpotifyClient(BaseSpotifyClient):

    async def get_album(self, spotify_id: str) -> dict:
        headers = self._get_headers()
        url = f"{self.base_url}/v1/albums/{spotify_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                return await response.json()

    async def get_several_albums(self, spotify_ids: list[str]) -> list[dict]:
        headers = self._get_headers()
        params = {
            "ids": ",".join([id_ for id_ in spotify_ids]),
        }
        url = f"{self.base_url}/v1/albums"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                response.raise_for_status()
                return await response.json()

    async def get_artist(self, spotify_id: str) -> dict:
        headers = self._get_headers()
        url = f"{self.base_url}/v1/artists/{spotify_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                return await response.json()

    async def get_several_artists(self, spotify_ids: list[str]) -> list[dict]:
        headers = self._get_headers()
        params = {
            "ids": ",".join([str(id_) for id_ in spotify_ids]),
        }
        url = f"{self.base_url}/v1/artists"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                response.raise_for_status()
                return await response.json()

    async def get_track(self, spotify_id: str) -> dict:
        headers = self._get_headers()
        url = f"{self.base_url}/v1/tracks/{spotify_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                return await response.json()

    async def get_several_tracks(self, spotify_ids: list[str]) -> list[dict]:
        headers = self._get_headers()
        params = {
            "ids": ",".join([str(id_) for id_ in spotify_ids]),
        }
        url = f"{self.base_url}/v1/tracks"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                response.raise_for_status()
                return await response.json()


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

    def parse_several_artists_response_data(self, response_data: list[dict]) -> dict:
        artists_map = {}

        for artist_data in response_data.get("artists", []):
            result = self.parse_artist_response_data(artist_data)

            artists_map.update(result["artists_map"])

        return {
            "artists": list(artists_map.values()),
        }

    def parse_artist_response_data(self, artist_data: dict) -> dict:
        artists_map = {}

        parsed_artist = self.parse_artist(artist_data)
        if parsed_artist:
            artists_map[parsed_artist["id"]] = parsed_artist

        return {
            "artists_map": artists_map,
        }

    def parse_several_tracks_response_data(self, response_data: list[dict]) -> dict:
        artists_map = {}
        albums_map = {}
        tracks_map = {}

        album_artists_relations = []
        track_artists_relations = []

        tracks_data = response_data.get("tracks", [])
        for track_data in tracks_data:
            result = self.parse_track_response_data(track_data)

            artists_map.update(result["artists_map"])
            albums_map.update(result["albums_map"])
            tracks_map.update(result["tracks_map"])
            album_artists_relations.extend(result["album_artists_relations"])
            track_artists_relations.extend(result["track_artists_relations"])

        return {
            "artists_to_create": list(artists_map.values()),
            "albums_to_create": list(albums_map.values()),
            "tracks_to_update": list(tracks_map.values()),
            "album_artists_to_create": album_artists_relations,
            "track_artists_to_create": track_artists_relations,
        }

    def parse_track_response_data(self, track_data: dict) -> dict:
        albums_map = {}
        artists_map = {}
        tracks_map = {}
        album_artists_relations = []
        track_artists_relations = []

        parsed_track = self.parse_track(track_data)
        parsed_album = parsed_track.get("album", {})

        if parsed_album:
            parsed_album_short = parsed_album.copy()
            del parsed_album_short["artists"]

            albums_map[parsed_album["id"]] = parsed_album_short

            tracks_map[parsed_track["id"]] = {
                "track_id": parsed_track["id"],
                "album_id": parsed_album["id"],
            }

        album_artists_data = parsed_album.get("artists", [])
        for artist_data in album_artists_data:
            artists_map[artist_data["id"]] = artist_data
            album_artists_relations.append(
                {
                    "album_id": parsed_album["id"],
                    "artist_id": artist_data["id"],
                }
            )

        track_artists_data = parsed_track.get("artists", [])
        for artist_data in track_artists_data:
            artists_map[artist_data["id"]] = artist_data
            track_artists_relations.append(
                {
                    "track_id": parsed_track["id"],
                    "artist_id": artist_data["id"],
                }
            )

        return {
            "artists_map": artists_map,
            "albums_map": albums_map,
            "tracks_map": tracks_map,
            "album_artists_relations": album_artists_relations,
            "track_artists_relations": track_artists_relations,
        }

    def parse_artist(self, data: dict) -> dict:
        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "cover_url": self.extract_cover_url(data),
        }

    def parse_album(self, data: dict) -> dict:
        artists = self.parse_several_artists(data.get("artists", []))

        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "cover_url": self.extract_cover_url(data),
            "artists": artists,
        }

    def parse_track(self, data: dict) -> dict:
        album = self.parse_album(data.get("album", {}))
        artists = self.parse_several_artists(data.get("artists", []))

        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "album": album,
            "artists": artists,
        }

    def parse_several_artists(self, list_data: list[dict]) -> list[dict]:
        return [self.parse_artist(artist_data) for artist_data in list_data]

    def extract_cover_url(self, data: dict) -> str:
        cover_url = ""
        if data.get("images"):
            cover_url = data["images"][0].get("url", "")
        return cover_url


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
