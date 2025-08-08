from django.urls import include, path

urlpatterns = [
    path("v1/", include("spotify_stats.api.v1.urls")),
]