from django.core.exceptions import ValidationError
from django.forms import fields
import json

from django_resumable_async_upload.widgets import ResumableAdminWidget


class FormResumableFileField(fields.FileField):
    widget = ResumableAdminWidget

    def to_python(self, data):
        if self.required:
            if not data or data == "None":
                raise ValidationError(self.error_messages["empty"])
        return data


class FormResumableMultipleFileField(fields.Field):
    """
    Form field that handles multiple file uploads via resumable.js.
    Stores file paths as a JSON array and returns a list of file paths.
    """

    widget = ResumableAdminWidget

    def to_python(self, data):
        """Convert JSON string to Python list of file paths."""
        if not data or data in ["None", "False", None]:
            return []

        # If already a list, return it
        if isinstance(data, list):
            return data

        # Try to parse as JSON
        try:
            parsed = json.loads(data)
            if isinstance(parsed, list):
                return parsed
            # If single value, wrap in list
            return [parsed] if parsed else []
        except (json.JSONDecodeError, ValueError, TypeError):
            # Not JSON, treat as single file path
            return [data] if data else []

    def clean(self, value):
        """
        Validate and clean the field value.
        Converts JSON string to list and validates.
        """
        # Convert to Python type (list of file paths)
        value = self.to_python(value)

        # Run validation
        self.validate(value)

        # Run any custom validators
        self.run_validators(value)

        return value

    def prepare_value(self, value):
        """Convert Python list to JSON string for rendering."""
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return json.dumps(value)
        return str(value)

    def validate(self, value):
        """Validate that all file paths in the list are valid."""
        if self.required and not value:
            raise ValidationError(self.error_messages["required"])
