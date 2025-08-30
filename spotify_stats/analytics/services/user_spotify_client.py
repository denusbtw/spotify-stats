import logging
from datetime import timedelta

from django.utils import timezone

from spotify_stats.analytics.models import SpotifyProfile
from spotify_stats.analytics.services import SpotifyAuthService


log = logging.getLogger()


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
