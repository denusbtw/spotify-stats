import pytest
from django.db import IntegrityError

from spotify_stats.catalog.models import AlbumArtist


class TestAlbumArtistModel:

    def test_not_unique_album_artist(self, album, artist):
        AlbumArtist.objects.create(album=album, artist=artist)

        with pytest.raises(IntegrityError) as e:
            AlbumArtist.objects.create(album=album, artist=artist)
        assert 'unique constraint "unique_album_artist"' in str(e)
