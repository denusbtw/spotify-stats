import factory

from django.contrib.auth import get_user_model

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    username = factory.Sequence(lambda n: f"user_{n}")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")

    @factory.lazy_attribute
    def email(self):
        return f"{self.username}@spotifystats.com"

    @factory.post_generation
    def password(self, create: bool, extracted: str, **kwargs):
        password = (
            extracted
            if extracted
            else factory.Faker(
                "password",
                length=12,
                special_chars=True,
                digits=True,
                upper_case=True,
                lower_case=True,
            ).evaluate(None, None, extra={"locale": None})
        )
        self.set_password(password)

    class Meta:
        model = User
        skip_postgeneration_save = True