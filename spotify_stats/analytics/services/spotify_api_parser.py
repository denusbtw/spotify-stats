class SpotifyAPIParser:

    def parse_several_artists_response_data(self, response_data):
        artists_map = {}

        for artist_data in response_data.get("artists", []):
            result = self.parse_artist_response_data(artist_data)

            artists_map.update(result["artists_map"])

        return {
            "artists": list(artists_map.values()),
        }

    def parse_artist_response_data(self, artist_data):
        artists_map = {}

        parsed_artist = self.parse_artist(artist_data)
        if parsed_artist:
            artists_map[parsed_artist["id"]] = parsed_artist

        return {
            "artists_map": artists_map,
        }

    def parse_several_tracks_response_data(self, response_data):
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

    def parse_track_response_data(self, track_data):
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

    def parse_artist(self, data):
        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "cover_url": self.extract_cover_url(data),
        }

    def parse_album(self, data):
        artists = self.parse_several_artists(data.get("artists", []))

        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "cover_url": self.extract_cover_url(data),
            "artists": artists,
        }

    def parse_track(self, data):
        album = self.parse_album(data.get("album", {}))
        artists = self.parse_several_artists(data.get("artists", []))

        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "album": album,
            "artists": artists,
        }

    def parse_several_artists(self, list_data):
        return [self.parse_artist(artist_data) for artist_data in list_data]

    def extract_cover_url(self, data):
        cover_url = ""
        if data.get("images"):
            cover_url = data["images"][0].get("url", "")
        return cover_url
