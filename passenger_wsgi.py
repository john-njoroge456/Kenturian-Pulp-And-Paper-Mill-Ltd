import os
import sys

# Make the project folder importable
sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

from mysite.wsgi import application  # noqa: E402
