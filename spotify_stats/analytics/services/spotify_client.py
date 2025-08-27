import logging
import time

import aiohttp
import requests
from django.conf import settings
from django.core.cache import cache


log = logging.getLogger()


class BaseSpotifyClient:
    def __init__(self):
        self.base_url = "https://api.spotify.com"
        self.client_id = settings.SPOTIFY_CLIENT_ID
        self.client_secret = settings.SPOTIFY_CLIENT_SECRET
        self.token = None
        self.token_expires_at = 0

    def get_access_token(self):
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

    def _get_headers(self):
        token = self.get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        return headers


class SyncSpotifyClient(BaseSpotifyClient):

    def get_album(self, spotify_id):
        headers = self._get_headers()
        url = f"{self.base_url}/v1/albums/{spotify_id}"

        response = requests.get(url, headers=headers)
        return response.json()

    def get_several_albums(self, spotify_ids: list):
        headers = self._get_headers()
        params = {
            "ids": ",".join([id_ for id_ in spotify_ids]),
        }
        url = f"{self.base_url}/v1/albums"

        response = requests.get(url, headers=headers, params=params)
        return response.json()

    def get_artist(self, spotify_id):
        headers = self._get_headers()
        url = f"{self.base_url}/v1/artists/{spotify_id}"

        response = requests.get(url, headers=headers)
        return response.json()

    def get_several_artists(self, spotify_ids: list):
        headers = self._get_headers()
        params = {
            "ids": ",".join([id_ for id_ in spotify_ids]),
        }
        url = f"{self.base_url}/v1/artists"

        response = requests.get(url, headers=headers, params=params)
        return response.json()

    def get_track(self, spotify_id):
        headers = self._get_headers()
        url = f"{self.base_url}/v1/tracks/{spotify_id}"

        response = requests.get(url, headers=headers)
        return response.json()

    def get_several_tracks(self, spotify_ids: list):
        headers = self._get_headers()
        params = {
            "ids": ",".join([str(id_) for id_ in spotify_ids]),
        }
        url = f"{self.base_url}/v1/tracks"

        response = requests.get(url, headers=headers, params=params)
        return response.json()


class AsyncSpotifyClient(BaseSpotifyClient):

    async def get_album(self, spotify_id):
        headers = self._get_headers()
        url = f"{self.base_url}/v1/albums/{spotify_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                return await response.json()

    async def get_several_albums(self, spotify_ids: list):
        headers = self._get_headers()
        params = {
            "ids": ",".join([id_ for id_ in spotify_ids]),
        }
        url = f"{self.base_url}/v1/albums"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                response.raise_for_status()
                return await response.json()

    async def get_artist(self, spotify_id):
        headers = self._get_headers()
        url = f"{self.base_url}/v1/artists/{spotify_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                return await response.json()

    async def get_several_artists(self, spotify_ids: list):
        headers = self._get_headers()
        params = {
            "ids": ",".join([str(id_) for id_ in spotify_ids]),
        }
        url = f"{self.base_url}/v1/artists"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                response.raise_for_status()
                return await response.json()

    async def get_several_tracks(self, spotify_ids: list):
        headers = self._get_headers()
        params = {
            "ids": ",".join([str(id_) for id_ in spotify_ids]),
        }
        url = f"{self.base_url}/v1/tracks"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                response.raise_for_status()
                return await response.json()

    async def get_track(self, spotify_id):
        headers = self._get_headers()
        url = f"{self.base_url}/v1/tracks/{spotify_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                return await response.json()
