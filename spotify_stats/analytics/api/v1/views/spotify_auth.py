import logging
import time
from datetime import datetime, timedelta

from django.shortcuts import redirect
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import views, response, status
from rest_framework_simplejwt.tokens import RefreshToken

from spotify_stats.analytics.models import SpotifyProfile
from spotify_stats.analytics.services import SpotifyAuthService

User = get_user_model()

log = logging.getLogger()


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

        response_data = SpotifyAuthService.get_user_tokens(code)
        if not response_data:
            return response.Response(
                {"error": "Failed to get tokens from Spotify"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        access_token = response_data.get("access_token")
        refresh_token = response_data.get("refresh_token")
        expires_in = response_data.get("expires_in")
        scope = response_data.get("scope")

        if not all([access_token, refresh_token, expires_in, scope]):
            return response.Response(
                {"error": "Missing required token data from Spotify."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        user_data = SpotifyAuthService.get_user_info(access_token)
        if not user_data:
            return response.Response(
                {"error": "Failed to get user info from Spotify"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        spotify_id = user_data.get("id")
        email = user_data.get("email")

        user, _ = User.objects.get_or_create(
            email=email,
            defaults={
                "username": f"spotify_{spotify_id}",
            },
        )

        expires_at = timezone.now() + timedelta(seconds=expires_in)

        spotify_profile, _ = SpotifyProfile.objects.update_or_create(
            user=user,
            defaults={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "spotify_id": spotify_id,
                "scope": scope,
            },
        )

        refresh = RefreshToken.for_user(user)
        return response.Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_200_OK,
        )
