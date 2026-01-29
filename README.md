# django-resumable-async-upload

django-resumable-async-upload is a django app to allow you to upload large files from within the django admin site asynchronously, that means that you can add any number of files on the admin page (e.g. through inline models) and continue editing other fields while files are uploading.

- Currently only tested with the Django default file storage

## Installation

- pip install django-resumable-async-upload
- Add `django_resumable_async_upload` to your `INSTALLED_APPS`
- Add `re_path(r"^django_resumable_async_upload/", include("django_resumable_async_upload.urls")),` to your urls.py
- Add in your models field

```
from django_resumable_async_upload.models import AsyncFileField

class Foo(models.Model):
    bar = models.CharField(max_length=200)
    foo = AsyncFileField()
```

- Add in your admin form:

```
from django_resumable_async_upload.fields import FormResumableMultipleFileField
from django_resumable_async_upload.widgets import ResumableAdminWidget

class MultiUploadForm(forms.ModelForm):
    files = FormResumableMultipleFileField(
        required=False,
        widget=ResumableAdminWidget(attrs={"model": File, "field_name": "file"}),
    )
```

Optional Settings:

- Set `ADMIN_RESUMABLE_CHUNKSIZE`, default is `"1*1024*1024"`
- Set `ADMIN_RESUMABLE_STORAGE`, default is setting of storages and ultimately `'django.core.files.storage.FileSystemStorage'`. If you don't want the default FileSystemStorage behaviour of creating new files on the server with filenames appended with \_1, \_2, etc for consecutive uploads of the same file, then you could use this to set your storage class to something like https://djangosnippets.org/snippets/976/
- Set `ADMIN_RESUMABLE_CHUNK_STORAGE`, default is `'django.core.files.storage.FileSystemStorage'` . If you don't want the default FileSystemStorage behaviour of creating new files on the server with filenames appended with \_1, \_2, etc for consecutive uploads of the same file, then you could use this to set your storage class to something like https://djangosnippets.org/snippets/976/
- Set `ADMIN_RESUMABLE_SHOW_THUMB`, default is False. Shows a thumbnail next to the "Currently:" link.
- Set `ADMIN_SIMULTANEOUS_UPLOADS` to limit number of simultaneous uploads, defaults to `3`. If you have broken pipe issues in local development environment, set this value to `1`.
- Set `MEDIA_URL` to where images are stored to be rendered after upload

Optional Param for `AsyncFileField`

- `max_files`, default is None. Configure how many files are allowed to be uploaded to a file input.

## Versions

0.1.0 - inital fork of django-async-upload 4.0.1 with support for Django 4 and later. Includes admin form updates to pause, resume, cancel and track progress of upload. Also supports uploads of multiple files

## Compatibility

Tested on Django 4.2 running on python 3.12

## Thanks to

original django-admin-resumable-js by jonatron https://github.com/jonatron/django-admin-resumable-js

django-admin-resumable-js fork by roxel https://github.com/roxel/django-admin-resumable-js

django-admin-async-upload fork by DataGreed https://github.com/DataGreed/django-admin-async-upload

django-async-upload fork by bit https://github.com/bit/django-async-upload

Resumable.js https://github.com/23/resumable.js

Typescript supported version of resumable.js https://github.com/augustcodes08/resumable-uploads

django-resumable https://github.com/jeanphix/django-resumable
