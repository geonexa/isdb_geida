from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = "GEIDA core"

    def ready(self):
        from django.conf import settings

        from . import checks  # noqa: F401  (registers the GDAL/PROJ startup check)

        if "spatialite" in settings.DATABASES["default"]["ENGINE"]:
            from .spatialite_wkb import install

            install()
