class SpotifyAPIParser:

    def parse_artist(self, data: dict) -> dict:
        return {
            "spotify_id": data.get("id"),
            "name": data.get("name"),
            "cover_url": self.extract_cover_url(data),
        }

    def parse_album(self, data: dict) -> dict:
        artists = [self.parse_artist(d) for d in data.get("artists")]

        return {
            "spotify_id": data.get("id"),
            "name": data.get("name"),
            "cover_url": self.extract_cover_url(data),
            "artists": artists,
        }

    def parse_track(self, data: dict) -> dict:
        album = self.parse_album(data.get("album", {}))
        artists = [self.parse_artist(d) for d in data.get("artists")]

        return {
            "spotify_id": data.get("id"),
            "name": data.get("name"),
            "album": album,
            "artists": artists,
        }

    def extract_cover_url(self, data: dict) -> str:
        cover_url = ""
        if data.get("images"):
            cover_url = data["images"][0].get("url", "")
        return cover_url
