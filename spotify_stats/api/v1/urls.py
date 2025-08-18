from django.urls import path

from spotify_stats.analytics.api.v1.views import (
    UserFileUploadJobListCreateView,
    UserTopTracksListView,
    UserTopAlbumsListView,
    UserTopArtistsListView,
    UserListeningStatsView,
    UserListeningActivityView,
)
from spotify_stats.users.api.v1.views import MeDetailView

app_name = "v1"
urlpatterns = [
    path("me/", MeDetailView.as_view(), name="me_detail"),
    path(
        "me/uploads/",
        UserFileUploadJobListCreateView.as_view(),
        name="user_upload_list",
    ),
    path(
        "me/analytics/top-artists/",
        UserTopArtistsListView.as_view(),
        name="user_top_artists",
    ),
    path(
        "me/analytics/top-albums/",
        UserTopAlbumsListView.as_view(),
        name="user_top_albums",
    ),
    path(
        "me/analytics/top-tracks/",
        UserTopTracksListView.as_view(),
        name="user_top_tracks",
    ),
    path(
        "me/analytics/stats/",
        UserListeningStatsView.as_view(),
        name="user_listening_stats",
    ),
    path(
        "me/analytics/activity/",
        UserListeningActivityView.as_view(),
        name="user_listening_activity",
    ),
]
