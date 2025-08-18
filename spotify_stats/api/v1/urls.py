from django.urls import path

from spotify_stats.analytics.api.v1.views import (
    FileUploadJobAPIView,
    TopTracksAPIView,
    TopAlbumsAPIView,
    TopArtistsAPIView, ListeningStatsAPIView, ListeningActivityAPIView,
)
from spotify_stats.users.api.v1.views import MeDetailAPIView

app_name = "v1"
urlpatterns = [
    path("me/", MeDetailAPIView.as_view(), name="me_detail"),
    path("me/uploads/", FileUploadJobAPIView.as_view(), name="me_upload_list"),
    path("me/analytics/top-artists/", TopArtistsAPIView.as_view(), name="me_analytics_top_artists"),
    path("me/analytics/top-albums/", TopAlbumsAPIView.as_view(), name="me_analytics_top_albums"),
    path("me/analytics/top-tracks/", TopTracksAPIView.as_view(), name="me_analytics_top_tracks"),
    path("me/analytics/stats/", ListeningStatsAPIView.as_view(), name="me_analytics_stats"),
    path("me/analytics/activity/", ListeningActivityAPIView.as_view(), name="me_analytics_activity")
]
