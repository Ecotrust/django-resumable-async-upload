import pytest
import os
import tempfile
from selenium import webdriver

browsers = {
    "chrome": webdriver.Chrome,
}

browser_options = {"chrome": webdriver.ChromeOptions()}

browser_options["chrome"].add_argument("--headless")
browser_options["chrome"].add_argument("--no-sandbox")
browser_options["chrome"].add_argument("--disable-dev-shm-usage")


# Session-scoped fixture to create a temporary directory for test artifacts
@pytest.fixture(scope="session")
def test_temp_dir(tmp_path_factory):
    """Create a temporary directory for test database and other artifacts."""
    temp_dir = tmp_path_factory.mktemp("test_artifacts")
    return temp_dir


@pytest.fixture(scope="session", params=browsers.keys())
def driver(request):
    b = browsers[request.param](options=browser_options[request.param])

    request.addfinalizer(lambda *args: b.quit())

    return b


def pytest_configure():
    import django
    from django.conf import settings
    
    # Create a temporary directory for the test database
    test_db_dir = tempfile.mkdtemp(prefix="django_test_")
    test_db_path = os.path.join(test_db_dir, "test_db.sqlite3")

    settings.configure(
        DEBUG=False,
        DEBUG_PROPAGATE_EXCEPTIONS=True,
        DATABASES={
            "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": test_db_path}
        },
        SITE_ID=1,
        SECRET_KEY="not very secret in tests",
        USE_I18N=True,
        USE_L10N=True,
        STATIC_URL="/static/",
        ROOT_URLCONF="tests.urls",
        LOGIN_URL="/admin/login/",
        TEMPLATE_LOADERS=(
            "django.template.loaders.filesystem.Loader",
            "django.template.loaders.app_directories.Loader",
        ),
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [],
                "APP_DIRS": True,
                "OPTIONS": {
                    "context_processors": [
                        "django.contrib.auth.context_processors.auth",
                        "django.template.context_processors.debug",
                        "django.template.context_processors.i18n",
                        "django.template.context_processors.media",
                        "django.template.context_processors.static",
                        "django.template.context_processors.tz",
                        "django.contrib.messages.context_processors.messages",
                    ],
                },
            },
        ],
        MIDDLEWARE=(
            "django.middleware.security.SecurityMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.middleware.common.CommonMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware",
        ),
        INSTALLED_APPS=(
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.sites",
            "django.contrib.messages",
            "django.contrib.staticfiles",
            "admin_async_upload",
            "tests",
        ),
        PASSWORD_HASHERS=("django.contrib.auth.hashers.MD5PasswordHasher",),
        MEDIA_ROOT=os.path.join(os.path.dirname(__file__), "media"),
        ADMIN_SIMULTANEOUS_UPLOADS=1
    )
    
    # Store the test DB directory for cleanup
    settings.TEST_DB_DIR = test_db_dir
    
    try:
        import django

        django.setup()
    except AttributeError:
        pass


def pytest_unconfigure():
    """Clean up temporary test database directory after all tests."""
    import shutil
    from django.conf import settings
    
    if hasattr(settings, 'TEST_DB_DIR') and os.path.exists(settings.TEST_DB_DIR):
        try:
            shutil.rmtree(settings.TEST_DB_DIR)
        except Exception as e:
            print(f"Warning: Could not clean up test DB directory: {e}")
