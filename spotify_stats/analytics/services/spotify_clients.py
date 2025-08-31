import logging
import time
from datetime import timedelta

import aiohttp
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from spotify_stats.analytics.models import SpotifyProfile
from .utils import get_base64_auth_string
from .spotify_auth import SpotifyAuthService

log = logging.getLogger()


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

        base64_auth_string = get_base64_auth_string(self.client_id, self.client_secret)

        url = "https://accounts.spotify.com/api/token"
        headers = {"Authorization": f"Basic {base64_auth_string}"}
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
