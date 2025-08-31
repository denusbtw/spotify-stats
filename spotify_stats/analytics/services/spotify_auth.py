import logging

import requests
from django.conf import settings

from .utils import get_base64_auth_string

log = logging.getLogger()


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
        base64_auth_string = get_base64_auth_string(cls.client_id, cls.client_secret)

        headers = {
            "Authorization": f"Basic {base64_auth_string}",
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
        base64_auth_string = get_base64_auth_string(cls.client_id, cls.client_secret)

        headers = {
            "Authorization": f"Basic {base64_auth_string}",
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
