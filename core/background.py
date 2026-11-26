"""
Tareas de fondo que se lanzan al abrir el dashboard (como en el video 16):
descargar tasas de cambio y actualizar la foto diaria de stock.

Mejoras frente al video:
  - Un candado evita lanzar varios hilos a la vez si varios usuarios abren
    el dashboard al mismo tiempo.
  - Se ejecutan como máximo cada BACKGROUND_TASKS_INTERVAL_MINUTES.
  - Las tareas se pueden correr a mano con:
        python manage.py update_exchange_rates
        python manage.py sync_stock
"""
import logging
import threading
from datetime import timedelta

from django.conf import settings
from django.db import connection
from django.utils import timezone

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_last_run = None


def run_background_tasks():
    """Ejecuta todas las tareas en orden. Se puede llamar directo (sin hilo)."""
    from core.exchange_rates import update_exchange_rates
    from inventory.services import fill_missing_exchange_rates, sync_daily_stock

    try:
        update_exchange_rates()
        fixed = fill_missing_exchange_rates()
        # Si cambió la tasa de movimientos viejos, se recalcula toda la historia
        sync_daily_stock(full=bool(fixed))
    except Exception:
        logger.exception("Background tasks failed")
    finally:
        connection.close()


def _worker():
    global _last_run
    try:
        run_background_tasks()
    finally:
        _last_run = timezone.now()
        _lock.release()


def trigger_background_tasks():
    """Lanza las tareas en un hilo si están habilitadas y no corrieron hace poco."""
    if not getattr(settings, 'BACKGROUND_TASKS_ENABLED', True):
        return False

    interval = timedelta(minutes=getattr(settings, 'BACKGROUND_TASKS_INTERVAL_MINUTES', 30))
    if _last_run and timezone.now() - _last_run < interval:
        return False

    if not _lock.acquire(blocking=False):
        return False   # ya hay un hilo trabajando

    threading.Thread(target=_worker, daemon=True).start()
    return True
