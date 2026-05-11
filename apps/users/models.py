from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    username = models.CharField(max_length=150, blank=True, default="")
    nickname = models.CharField(max_length=50, unique=True)
    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nickname", "first_name", "last_name"]

    def __str__(self) -> str:
        return self.nickname
