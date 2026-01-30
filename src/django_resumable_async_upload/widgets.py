from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models.fields.files import FieldFile
from django.forms import FileInput, CheckboxInput, forms
from django.template import loader
from django.templatetags.static import static
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy

from django_resumable_async_upload.storage import ResumableStorage


class ResumableBaseWidget(FileInput):
    template_name = "admin_resumable/admin_file_input.html"
    clear_checkbox_label = gettext_lazy("Clear")
    allow_multiple_selected = False  # Can be overridden per instance

    def __init__(self, attrs=None):
        super().__init__(attrs)

        if attrs and attrs.get("max_files") != 1:
            self.allow_multiple_selected = True

    def render(self, name, value, attrs=None, **kwargs):
        persistent_storage = ResumableStorage().get_persistent_storage()
        if value:
            if isinstance(value, FieldFile):
                value_name = value.name
            else:
                value_name = value
            file_name = value
            file_url = mark_safe(persistent_storage.url(value_name))

        else:
            file_name = ""
            file_url = ""

        chunk_size = getattr(settings, "ADMIN_RESUMABLE_CHUNKSIZE", "1*1024*1024")
        show_thumb = getattr(settings, "ADMIN_RESUMABLE_SHOW_THUMB", False)
        simultaneous_uploads = getattr(settings, "ADMIN_SIMULTANEOUS_UPLOADS", 3)
        media_url = getattr(settings, "MEDIA_URL", None)
        max_files = self.attrs.get("max_files", None)

        content_type_id = ContentType.objects.get_for_model(self.attrs["model"]).id

        context = {
            "name": name,
            "value": value,
            "id": attrs["id"],
            "chunk_size": chunk_size,
            "show_thumb": show_thumb,
            "field_name": self.attrs["field_name"],
            "content_type_id": content_type_id,
            "file_url": file_url,
            "file_name": file_name,
            "simultaneous_uploads": simultaneous_uploads,
            "max_files": max_files,
            "MEDIA_URL": media_url,
        }

        instance = self.attrs.get("instance")
        if instance and instance.pk:
            context["instance_id"] = instance.pk

        if not self.is_required:
            template_with_clear = (
                '<span class="clearable-file-input">%(clear)s '
                '<label for="%(clear_checkbox_id)s">%(clear_checkbox_label)s</label></span>'
            )
            substitutions = {
                "clear_checkbox_id": attrs["id"] + "-clear-id",
                "clear_checkbox_name": attrs["id"] + "-clear",
                "clear_checkbox_label": self.clear_checkbox_label,
            }
            substitutions["clear"] = CheckboxInput().render(
                substitutions["clear_checkbox_name"],
                False,
                attrs={"id": substitutions["clear_checkbox_id"]},
            )
            clear_checkbox = mark_safe(template_with_clear % substitutions)
            context.update({"clear_checkbox": clear_checkbox})
        return loader.render_to_string(self.template_name, context)

    def value_from_datadict(self, data, files, name):
        if not self.is_required and data.get("id_" + name + "-clear"):
            return False  # False signals to clear any existing value, as opposed to just None

        value = data.get(name, None)
        if value in ["None", "False", None]:
            return None

        return value


class ResumableAdminWidget(ResumableBaseWidget):
    @property
    def media(self):
        js = ["resumable.js"]
        return forms.Media(js=[static("admin_resumable/js/%s" % path) for path in js])


class ResumableWidget(ResumableBaseWidget):
    template_name = "admin_resumable/user_file_input.html"
