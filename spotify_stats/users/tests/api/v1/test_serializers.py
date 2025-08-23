import pytest
from rest_framework.exceptions import ValidationError

from spotify_stats.users.api.v1.serializers import (
    MeRetrieveSerializer,
    MeUpdateSerializer,
)


@pytest.mark.django_db
class TestMeRetrieveSerializer:

    def test_expected_fields(self, user):
        serializer = MeRetrieveSerializer(user)
        actual_fields = serializer.data.keys()
        expected_fields = {
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "date_joined",
        }
        assert actual_fields == expected_fields


@pytest.mark.django_db
class TestMeUpdateSerializer:

    def test_error_if_invalid_password(self, user, invalid_password):
        data = {"password": invalid_password}
        serializer = MeUpdateSerializer(user, data=data)

        with pytest.raises(ValidationError) as exc:
            serializer.is_valid(raise_exception=True)
        assert "password" in str(exc.value)

    def test_no_error_if_valid_password(self, user, valid_password):
        data = {"password": valid_password}
        serializer = MeUpdateSerializer(user, data=data)
        assert serializer.is_valid(), serializer.errors

    def test_updates_user(self, user_factory):
        user = user_factory(username="test_user", password="old_password")

        data = {"username": "new_username", "password": "new_password"}
        serializer = MeUpdateSerializer(user, data=data)
        assert serializer.is_valid(), serializer.errors
        user = serializer.save()

        assert user.username == "new_username"
        assert user.check_password("new_password")
