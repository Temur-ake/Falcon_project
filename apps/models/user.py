from django.contrib.auth.models import AbstractUser
from django.db.models import Model, CharField, ForeignKey, CASCADE, PositiveIntegerField, BooleanField, ImageField
from django.db.models import PositiveSmallIntegerField

from apps.models import CreatedBaseModel


class User(AbstractUser):
    has_pro = BooleanField(default=False)
    image = ImageField(upload_to='users/image/', null=True, blank=True)

    @property
    def cart_count(self):
        return self.cartitem_set.count()


class SiteSettings(Model):
    tax = PositiveSmallIntegerField()


class Address(CreatedBaseModel):
    user = ForeignKey('apps.User', CASCADE, related_name='address')
    city = CharField(max_length=255)
    street = CharField(max_length=255)
    zip_code = PositiveIntegerField()
    phone = CharField(max_length=255)
    full_name = CharField(max_length=255)

    def __str__(self):
        return self.city
