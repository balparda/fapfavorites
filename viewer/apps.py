"""App config."""

from django.apps import AppConfig


class ViewerConfig(AppConfig):
  """Viewer app config class."""

  default_auto_field = 'django.db.models.BigAutoField'
  name = 'viewer'
