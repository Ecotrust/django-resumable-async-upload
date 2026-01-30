from django.db import models
from django_resumable_async_upload.widgets import ResumableAdminWidget
from django_resumable_async_upload.fields import FormResumableFileField


class AsyncFileField(models.FileField):
    def __init__(self, *args, **kwargs):
        self.max_files = kwargs.pop("max_files", None)
        super(AsyncFileField, self).__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super(AsyncFileField, self).deconstruct()
        if self.max_files is not None:
            kwargs["max_files"] = self.max_files
        return name, path, args, kwargs

    def formfield(self, **kwargs):
        defaults = {"form_class": FormResumableFileField}
        if self.model and self.name:
            defaults["widget"] = ResumableAdminWidget(
                attrs={
                    "model": self.model,
                    "field_name": self.name,
                    "max_files": getattr(self, "max_files", None),
                }
            )
        kwargs.update(defaults)
        return super(AsyncFileField, self).formfield(**kwargs)
