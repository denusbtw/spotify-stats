from rest_framework import serializers

from spotify_stats.catalog.models import Artist, Album


class ArtistNestedSerializer(serializers.ModelSerializer):

    class Meta:
        model = Artist
        fields = ("id", "name", "cover_url")


class AlbumNestedSerializer(serializers.ModelSerializer):

    class Meta:
        model = Album
        fields = ("id", "name", "cover_url")
