from django.conf import settings
from django.db import models

from admin_async_upload.models import AsyncFileField


# Stolen from the README
class Foo(models.Model):
    bar = models.CharField(max_length=200)
    foo = AsyncFileField()
    bat = AsyncFileField(upload_to=settings.MEDIA_ROOT + "/upto/")
