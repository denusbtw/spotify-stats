import logging

from spotify_stats.analytics.models import ListeningHistory
from spotify_stats.catalog.models import Artist, Album, Track, AlbumArtist, TrackArtist
from .utils import get_objects_map

log = logging.getLogger()


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
                spotify_id__in=[a["spotify_id"] for a in artists_data]
            ).values_list("spotify_id", flat=True)
        )

        artists_to_create = [
            Artist(
                spotify_id=data["spotify_id"],
                name=data["name"],
            )
            for data in artists_data
            if data["spotify_id"] not in existing_artist_spotify_ids
        ]

        if artists_to_create:
            Artist.objects.bulk_create(artists_to_create, ignore_conflicts=True)
            log.info(f"Created {len(artists_to_create)} new artists.")

    def bulk_update_artists(self, artists_data: list[dict]) -> None:
        unique_artist_ids = {data["spotify_id"] for data in artists_data}
        artists_map = get_objects_map(Artist, unique_artist_ids)

        artists_to_update = []
        for data in artists_data:
            artist = artists_map.get(data["spotify_id"])
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
                spotify_id__in=[a["spotify_id"] for a in albums_data]
            ).values_list("spotify_id", flat=True)
        )

        albums_to_create = [
            Album(
                spotify_id=data["spotify_id"],
                name=data["name"],
                cover_url=data["cover_url"],
            )
            for data in albums_data
            if data["spotify_id"] not in existing_album_spotify_ids
        ]

        if albums_to_create:
            Album.objects.bulk_create(albums_to_create, ignore_conflicts=True)
            log.info(f"Created {len(albums_to_create)} new albums.")

    def bulk_create_tracks(self, tracks_data: list[dict]) -> None:
        existing_tracks_spotify_ids = set(
            Track.objects.filter(
                spotify_id__in={data["spotify_id"] for data in tracks_data}
            ).values_list("spotify_id", flat=True)
        )

        tracks_to_create = [
            Track(
                spotify_id=data["spotify_id"],
                name=data["name"],
            )
            for data in tracks_data
            if data["spotify_id"] not in existing_tracks_spotify_ids
        ]

        if tracks_to_create:
            Track.objects.bulk_create(
                tracks_to_create, batch_size=500, ignore_conflicts=True
            )
            log.info(f"Created {len(tracks_to_create)} new tracks.")

    def bulk_update_tracks(self, tracks_data: list[dict]) -> None:
        unique_track_spotify_ids = {data["track_spotify_id"] for data in tracks_data}
        unique_album_spotify_ids = {data["album_spotify_id"] for data in tracks_data}

        tracks_map = get_objects_map(Track, unique_track_spotify_ids)
        albums_map = get_objects_map(Album, unique_album_spotify_ids)

        tracks_to_update = []
        for data in tracks_data:
            track = tracks_map.get(data["track_spotify_id"])
            album = albums_map.get(data["album_spotify_id"])
            if track and album:
                track.album = album
                tracks_to_update.append(track)

        if tracks_to_update:
            Track.objects.bulk_update(tracks_to_update, fields=["album"])
            log.info(f"Updated {len(tracks_to_update)} tracks.")

    def bulk_create_albums_artists(self, relations_data: list[dict]) -> None:
        unique_album_spotify_ids = {data["album_spotify_id"] for data in relations_data}
        unique_artist_spotify_ids = {
            data["artist_spotify_id"] for data in relations_data
        }

        albums_map = get_objects_map(Album, unique_album_spotify_ids)
        artists_map = get_objects_map(Artist, unique_artist_spotify_ids)

        relations_to_create = []
        for data in relations_data:
            album = albums_map[data["album_spotify_id"]]
            artist = artists_map[data["artist_spotify_id"]]

            if album and artist:
                relations_to_create.append(
                    AlbumArtist(album=album, artist=artist),
                )

        if relations_to_create:
            AlbumArtist.objects.bulk_create(relations_to_create, ignore_conflicts=True)
            log.info(f"Created {len(relations_to_create)} albums artists.")

    def bulk_create_track_artists(self, relations_data: list[dict]) -> None:
        unique_track_spotify_ids = {data["track_spotify_id"] for data in relations_data}
        unique_artist_spotify_ids = {
            data["artist_spotify_id"] for data in relations_data
        }

        tracks_map = get_objects_map(Track, unique_track_spotify_ids)
        artists_map = get_objects_map(Artist, unique_artist_spotify_ids)

        relations_to_create = []
        for data in relations_data:
            track = tracks_map[data["track_spotify_id"]]
            artist = artists_map[data["artist_spotify_id"]]

            if track and artist:
                relations_to_create.append(
                    TrackArtist(track=track, artist=artist),
                )

        if relations_to_create:
            TrackArtist.objects.bulk_create(relations_to_create, ignore_conflicts=True)
            log.info(f"Created {len(relations_to_create)} tracks artists.")

    def bulk_create_listening_history(self, user, history_data: list[dict]):
        tracks_spotify_ids = {data["track_spotify_id"] for data in history_data}
        tracks_map = get_objects_map(Track, tracks_spotify_ids)

        listening_history_to_create = []
        for data in history_data:
            track = tracks_map.get(data["track_spotify_id"])
            data.pop("track_spotify_id")
            if track:
                listening_history_to_create.append(
                    ListeningHistory(user=user, track=track, **data)
                )

        if listening_history_to_create:
            ListeningHistory.objects.bulk_create(
                listening_history_to_create, batch_size=500, ignore_conflicts=True
            )
            log.info(
                f"Created {len(listening_history_to_create)} listening history records."
            )
