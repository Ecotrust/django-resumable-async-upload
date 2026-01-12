from admin_async_upload.utils import clear_cleanup_list


class AsyncFileCleanupMixin:
    """
    Mixin for ModelAdmin classes to automatically clean up session-tracked files
    after successful form save.
    
    Usage:
        class MyModelAdmin(AsyncFileCleanupMixin, admin.ModelAdmin):
            pass
    """
    
    def save_model(self, request, obj, form, change):
        """Override save_model to clear the cleanup list after saving."""
        super().save_model(request, obj, form, change)
        clear_cleanup_list(request)
    
    def save_formset(self, request, form, formset, change):
        """Override save_formset to clear the cleanup list after saving inline formsets."""
        super().save_formset(request, form, formset, change)
        clear_cleanup_list(request)
