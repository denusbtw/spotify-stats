import pytest
from django.urls import reverse
from rest_framework import status


@pytest.fixture
def url():
    return reverse("v1:me_detail")


@pytest.mark.django_db
class TestMeDetailAPIView:

    @pytest.mark.parametrize(
        "method, expected_status",
        [
            ("get", status.HTTP_401_UNAUTHORIZED),
            ("patch", status.HTTP_401_UNAUTHORIZED),
        ],
    )
    def test_anonymous_user(self, api_client, url, method, expected_status):
        response = getattr(api_client, method)(url)
        assert response.status_code == expected_status

    @pytest.mark.parametrize(
        "method, expected_status",
        [
            ("get", status.HTTP_200_OK),
            ("patch", status.HTTP_200_OK),
        ],
    )
    def test_authenticated_user(self, api_client, url, user, method, expected_status):
        api_client.force_authenticate(user=user)
        response = getattr(api_client, method)(url)
        assert response.status_code == expected_status

    def test_returns_current_user(self, api_client, url, user, user_factory):
        api_client.force_authenticate(user=user)

        user_factory.create_batch(2)

        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == str(user.id)

    def test_updates_current_user(self, api_client, url, user):
        api_client.force_authenticate(user=user)

        data = {"username": "username_upd"}
        response = api_client.patch(url, data=data)

        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.username == data["username"]
