"""
django_app.py - Django entry point, URL routing and server start.

A normal Django project has manage.py, settings.py, urls.py, wsgi.py, etc.
Here, settings.configure() replaces settings.py, this file doubles as the
URL configuration, and execute_from_command_line() replaces manage.py.

Run with:  python django_app.py
"""
import sys
from pathlib import Path

from django.conf import settings

BASE_DIR = Path(__file__).resolve().parent

# Settings must be configured before the rest of Django is used.
if not settings.configured:
    settings.configure(
        DEBUG=True,                                  # local demo only
        SECRET_KEY="demo-only-key-change-me",        # fine for local learning, never for production
        ROOT_URLCONF=__name__,                       # urlpatterns below live in this file
        ALLOWED_HOSTS=["localhost", "127.0.0.1", "[::1]"],
        MIDDLEWARE=[
            "django.middleware.common.CommonMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",   # CSRF protection for POST requests
        ],
    )

from django.core.management import execute_from_command_line  # noqa: E402
from django.http import HttpResponse                          # noqa: E402
from django.urls import path                                  # noqa: E402
from django.views.decorators.csrf import ensure_csrf_cookie   # noqa: E402

import backend  # noqa: E402  (backend.py in the same folder)


@ensure_csrf_cookie   # makes Django send the "csrftoken" cookie that index.html reads
def home(request):
    html = (BASE_DIR / "index.html").read_text(encoding="utf-8")
    return HttpResponse(html, content_type="text/html; charset=utf-8")


urlpatterns = [
    path("", home),                                        # the web page
    path("api/share/", backend.share_location),            # POST: start/update sharing
    path("api/location/", backend.get_location),           # GET:  retrieve shared location
    path("api/stop/", backend.stop_sharing),               # POST: stop sharing
]


if __name__ == "__main__":
    # "python django_app.py" alone starts the local server.
    # --noreload keeps ONE process, so the in-memory dictionary is not duplicated.
    if len(sys.argv) == 1:
        sys.argv += ["runserver", "127.0.0.1:8000", "--noreload"]
    execute_from_command_line(sys.argv)