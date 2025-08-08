from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from rest_framework import serializers

User = get_user_model()


class MeRetrieveSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "date_joined")


class MeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "password")
        extra_kwargs = {
            "username": {"required": False},
            "password": {"write_only": True, "required": False},
        }

    def validate_password(self, password):
        validate_password(password, self.instance)
        return password

    def update(self, instance, validated_data):
        new_password = validated_data.pop("password", None)
        if new_password:
            instance.set_password(new_password)

        return super().update(instance, validated_data)
