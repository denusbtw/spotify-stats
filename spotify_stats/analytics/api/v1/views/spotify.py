import logging
from datetime import timedelta

from django.shortcuts import redirect
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import views, response, status
from rest_framework_simplejwt.tokens import RefreshToken

from spotify_stats.analytics.exceptions import SpotifyServiceError
from spotify_stats.analytics.models import SpotifyProfile

from spotify_stats.analytics.services import SpotifyAuthService

log = logging.getLogger()

User = get_user_model()


class SpotifyLoginView(views.APIView):

    def get(self, request, *args, **kwargs):
        url = SpotifyAuthService.get_auth_url()
        return redirect(url)


class SpotifyCallbackView(views.APIView):

    def get(self, request, *args, **kwargs):
        code = request.query_params.get("code")
        if not code:
            log.error("Spotify callback: 'code' is missing.")
            return response.Response(
                {"error": "Authorization code not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            tokens = self._get_spotify_tokens(code)
            user_data = self._get_user_data(tokens.get("access_token"))
            user = self._get_or_create_user(user_data)
            self._update_or_create_spotify_profile(user, tokens, user_data.get("id"))
            jwt_tokens = self._generate_jwt_tokens(user)

            return response.Response(jwt_tokens, status=status.HTTP_200_OK)

        except SpotifyServiceError as e:
            return response.Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_spotify_tokens(self, code: str):
        tokens = SpotifyAuthService.get_user_tokens(code)
        if not tokens:
            raise SpotifyServiceError("Failed to get tokens from Spotify.")
        return tokens

    def _get_user_data(self, access_token: str):
        user_data = SpotifyAuthService.get_user_info(access_token)
        if not user_data:
            raise SpotifyServiceError("Failed to get user info from Spotify.")
        return user_data

    def _get_or_create_user(self, user_data: dict):
        email = user_data.get("email")
        display_name = user_data.get("display_name")
        if not all([display_name, email]):
            raise SpotifyServiceError("Missing user data from Spotify.")

        user, _ = User.objects.get_or_create(
            email=email, defaults={"username": display_name}
        )
        return user

    def _update_or_create_spotify_profile(self, user, tokens: dict, spotify_id: str):
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        expires_in = tokens.get("expires_in")
        scope = tokens.get("scope")

        if not all([access_token, refresh_token, expires_in, scope]):
            raise SpotifyServiceError("Missing required token data from Spotify.")

        expires_at = timezone.now() + timedelta(seconds=expires_in)
        SpotifyProfile.objects.update_or_create(
            user=user,
            defaults={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "spotify_id": spotify_id,
                "scope": scope,
            },
        )

    def _generate_jwt_tokens(self, user):
        refresh = RefreshToken.for_user(user)
        return {"access": str(refresh.access_token), "refresh": str(refresh)}
