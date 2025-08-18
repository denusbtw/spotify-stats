from rest_framework import generics, permissions

from spotify_stats.users.api.v1.serializers import (
    MeUpdateSerializer,
    MeRetrieveSerializer,
)


class MeDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in {"PUT", "PATCH"}:
            return MeUpdateSerializer
        return MeRetrieveSerializer
