from spotify_stats.analytics.services.spotify_api_parser import SpotifyAPIParser
from spotify_stats.analytics.services.spotify_client import SpotifyClient
from spotify_stats.catalog.models import Artist, Album, AlbumArtist, Track, TrackArtist


class SpotifyProcessor:

    def __init__(self):
        self.spotify_client = SpotifyClient()
        self.parser = SpotifyAPIParser()
        self.batch_size = 50

    def enrich_spotify_metadata(self, track_ids: list):
        for batch in self.split_into_batches(track_ids):
            self.process_batch(batch)

    def process_batch(self, batch):
        existing_artist_ids = set(Artist.objects.values_list("spotify_id", flat=True))
        existing_album_ids = set(Album.objects.values_list("spotify_id", flat=True))

        response = self.spotify_client.get_several_tracks(batch)
        parsed_response = self.parser.parse_several_tracks_response_data(response)

        artists_to_create = parsed_response["artists_to_create"]
        self.bulk_create_artists(artists_to_create, existing_artist_ids)

        albums_to_create = parsed_response["albums_to_create"]
        self.bulk_create_albums(albums_to_create, existing_album_ids)

        tracks_to_update = parsed_response["tracks_to_update"]
        self.bulk_update_tracks(tracks_to_update)

        self.bulk_create_albums_artists(parsed_response["album_artists_to_create"])
        self.bulk_create_track_artists(parsed_response["track_artists_to_create"])

    def bulk_update_tracks(self, data):
        unique_track_ids = {r["track_id"] for r in data}
        unique_album_ids = {r["album_id"] for r in data}

        tracks_map = {
            track.spotify_id: track
            for track in Track.objects.filter(spotify_id__in=unique_track_ids)
        }
        albums_map = {
            album.spotify_id: album
            for album in Album.objects.filter(spotify_id__in=unique_album_ids)
        }

        tracks_to_update = []
        for r in data:
            track = tracks_map.get(r["track_id"])
            album = albums_map.get(r["album_id"])
            if track and album:
                track.album = album
                tracks_to_update.append(track)

        Track.objects.bulk_update(tracks_to_update, fields=["album"])

    def bulk_create_artists(self, artists_data, existing_ids):
        artists_to_create = [
            Artist(
                spotify_id=data["id"],
                name=data["name"],
                cover_url=data["cover_url"],
            )
            for data in artists_data
            if data["id"] not in existing_ids
        ]
        Artist.objects.bulk_create(artists_to_create, ignore_conflicts=True)

    def bulk_create_albums(self, albums_data, existing_ids):
        albums_to_create = [
            Album(
                spotify_id=data["id"],
                name=data["name"],
                cover_url=data["cover_url"],
            )
            for data in albums_data
            if data["id"] not in existing_ids
        ]
        Album.objects.bulk_create(albums_to_create, ignore_conflicts=True)

    def bulk_create_albums_artists(self, data):
        unique_album_ids = {r["album_id"] for r in data}
        unique_artist_ids = {r["artist_id"] for r in data}

        albums_map = {
            album.spotify_id: album
            for album in Album.objects.filter(spotify_id__in=unique_album_ids)
        }

        artists_map = {
            artist.spotify_id: artist
            for artist in Artist.objects.filter(spotify_id__in=unique_artist_ids)
        }

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

        tracks_map = {
            track.spotify_id: track
            for track in Track.objects.filter(spotify_id__in=unique_track_ids)
        }

        artists_map = {
            artist.spotify_id: artist
            for artist in Artist.objects.filter(spotify_id__in=unique_artist_ids)
        }

        relations_to_create = [
            TrackArtist(
                track=tracks_map[r["track_id"]],
                artist=artists_map[r["artist_id"]],
            )
            for r in data
        ]

        TrackArtist.objects.bulk_create(relations_to_create, ignore_conflicts=True)

    def split_into_batches(self, items):
        for i in range(0, len(items), self.batch_size):
            yield items[i : i + self.batch_size]
