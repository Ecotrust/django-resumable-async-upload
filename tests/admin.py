from django.contrib import admin
from admin_async_upload.admin import AsyncFileCleanupMixin
from .models import Foo


class FooAdmin(AsyncFileCleanupMixin, admin.ModelAdmin):
    pass

admin.site.register(Foo, FooAdmin)
