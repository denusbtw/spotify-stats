from django.urls import path

from spotify_stats.analytics.api.v1.views import FileUploadJobAPIView
from spotify_stats.users.api.v1.views import MeDetailAPIView

app_name = "v1"
urlpatterns = [
    path("me/", MeDetailAPIView.as_view(), name="me_detail"),
    path("me/uploads/", FileUploadJobAPIView.as_view(), name="me_upload_list"),
]
