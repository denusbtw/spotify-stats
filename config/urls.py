from django.urls import path, include

urlpatterns = [
    path("api/", include("config.api_router")),
]
