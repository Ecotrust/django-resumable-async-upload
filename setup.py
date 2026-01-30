import os
from setuptools import setup

with open(os.path.join(os.path.dirname(__file__), "README.md")) as f:
    README = f.read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name="django-resumable-async-upload",
    version="4.2.0",
    packages=["admin_resumable_async_upload"],
    package_dir={"": "src"},
    include_package_data=True,
    package_data={
        "django_resumable_async_upload": [
            "templates/admin_resumable/*.html",
            "static/admin_resumable/js/*.js",
        ]
    },
    license="MIT License",
    description="A Django app for the uploading of large files from the django admin site.",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/Ecotrust/django-resumable-async-upload",
    author="Paige Williams",
    author_email="pwilliams@ecotrust.org",
    classifiers=[
        "Environment :: Web Environment",
        "Framework :: Django",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
    ],
    install_requires=[
        "Django>=3.0.14",
    ],
    tests_require=[
        "pytest-django",
    ],
)
