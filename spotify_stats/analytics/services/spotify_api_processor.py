import asyncio
import logging

from asgiref.sync import sync_to_async

from .spotify_client import AsyncSpotifyClient
from .spotify_api_parser import SpotifyAPIParser
from spotify_stats.catalog.models import Artist, Album, AlbumArtist, Track, TrackArtist


log = logging.getLogger()


# TODO: add logging
class SpotifyAPIProcessor:

    def __init__(self):
        self.spotify_client = AsyncSpotifyClient()
        self.parser = SpotifyAPIParser()
        self.batch_size = 50

    async def enrich_spotify_metadata(self, track_ids: list):
        tasks = []
        for batch in self.split_into_batches(track_ids, self.batch_size):
            tasks.append(self.process_tracks_batch(batch))

        await asyncio.gather(*tasks)

        await self.enrich_artists_covers()

    async def enrich_artists_covers(self):
        artists_without_cover_spotify_ids = await sync_to_async(
            lambda: list(
                Artist.objects.filter(cover_url="").values_list("spotify_id", flat=True)
            )
        )()

        tasks = []
        for batch in self.split_into_batches(
            artists_without_cover_spotify_ids, self.batch_size
        ):
            tasks.append(self.process_artists_batch(batch))

        await asyncio.gather(*tasks)

    async def process_tracks_batch(self, batch):
        # TODO: add retry mechanism
        response = await self.spotify_client.get_several_tracks(batch)
        parsed_response = self.parser.parse_several_tracks_response_data(response)

        await sync_to_async(self.process_and_save_tracks_data)(parsed_response)

    async def process_artists_batch(self, batch):
        response = await self.spotify_client.get_several_artists(batch)
        parsed_response = self.parser.parse_several_artists_response_data(response)

        await sync_to_async(self.bulk_update_artists)(parsed_response["artists"])

    def process_and_save_tracks_data(self, parsed_response):
        self.bulk_create_artists(parsed_response["artists_to_create"])
        self.bulk_create_albums(parsed_response["albums_to_create"])

        self.bulk_update_tracks(parsed_response["tracks_to_update"])

        self.bulk_create_albums_artists(parsed_response["album_artists_to_create"])
        self.bulk_create_track_artists(parsed_response["track_artists_to_create"])

    def bulk_update_artists(self, data):
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

    def bulk_update_tracks(self, data):
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

    def bulk_create_artists(self, artists_data):
        artists_to_create = [
            Artist(
                spotify_id=data["id"],
                name=data["name"],
            )
            for data in artists_data
        ]
        Artist.objects.bulk_create(artists_to_create, ignore_conflicts=True)

    def bulk_create_albums(self, albums_data):
        albums_to_create = [
            Album(
                spotify_id=data["id"],
                name=data["name"],
                cover_url=data["cover_url"],
            )
            for data in albums_data
        ]
        Album.objects.bulk_create(albums_to_create, ignore_conflicts=True)

    def bulk_create_albums_artists(self, data):
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

    def bulk_create_track_artists(self, data):
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

    def split_into_batches(self, items, batch_size):
        for i in range(0, len(items), batch_size):
            yield items[i : i + batch_size]

    def get_objects_map(self, model, ids):
        return {obj.spotify_id: obj for obj in model.objects.filter(spotify_id__in=ids)}
