import pytest
from django.contrib.auth.password_validation import validate_password


@pytest.mark.django_db
class TestUserFactory:
    def test_sets_provided_password(self, user_factory):
        password = "123123qq"
        user = user_factory(password=password)
        assert user.check_password(password)

    def test_generates_valid_password(self, user_factory):
        user = user_factory()
        validate_password(user._password)
