# credit/__init__.py

from .celery import app as celery_app

# This ensures the app is loaded when Django starts so that
# @shared_task will use this app instance.
__all__ = ('celery_app',)