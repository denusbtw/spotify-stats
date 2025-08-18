from rest_framework import serializers

from spotify_stats.catalog.models import Artist


class ArtistSerializer(serializers.ModelSerializer):

    class Meta:
        model = Artist
        fields = ["id", "name"]


class AlbumSerializer(serializers.ModelSerializer):

    class Meta:
        model = Artist
        fields = ["id", "name"]
