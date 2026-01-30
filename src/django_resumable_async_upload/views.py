from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse, JsonResponse
from django.utils.functional import cached_property
from django.views.generic import View
from django_resumable_async_upload.files import ResumableFile
from django.core.files.storage import default_storage
import json
import logging

logger = logging.getLogger(__name__)


class UploadView(View):
    """View to handle resumable file uploads via AJAX.
    Supports POST for uploading chunks, GET for checking chunk existence,
    and DELETE for removing uploaded files.
    """

    # inspired by another fork https://github.com/fdemmer/django-admin-resumable-js

    @cached_property
    def request_data(self):
        return getattr(self.request, self.request.method)

    @cached_property
    def model_upload_field(self):
        content_type = ContentType.objects.get_for_id(
            self.request_data["content_type_id"]
        )
        return content_type.model_class()._meta.get_field(
            self.request_data["field_name"]
        )

    def post(self, request, *args, **kwargs):
        chunk = request.FILES.get("file")
        r = ResumableFile(
            self.model_upload_field, user=request.user, params=request.POST
        )
        if not r.chunk_exists:
            r.process_chunk(chunk)
        if r.is_complete:
            file_path = r.collect()
            return HttpResponse(file_path)
        return HttpResponse("chunk uploaded")

    def get(self, request, *args, **kwargs):
        r = ResumableFile(
            self.model_upload_field, user=request.user, params=request.GET
        )
        if not r.chunk_exists:
            return HttpResponse("chunk not found", status=204)
        if r.is_complete:
            return HttpResponse(r.collect())
        return HttpResponse("chunk exists")

    def delete(self, request, *args, **kwargs):
        """Handle file deletion via DELETE request."""
        file_path = None
        try:
            # Parse the file path from request body
            body = json.loads(request.body.decode("utf-8"))
            file_path = body.get("file_path")

            if not file_path:
                return JsonResponse({"error": "file_path required"}, status=400)

            # Delete from storage
            if default_storage.exists(file_path):
                default_storage.delete(file_path)
            return JsonResponse({"status": "success", "message": "File removed"})
        except Exception as e:
            logger.error(f"Failed to delete file: {str(e)}")
            return JsonResponse(
                {"error": f"Failed to delete file: {file_path} "}, status=500
            )


admin_resumable = login_required(UploadView.as_view())
