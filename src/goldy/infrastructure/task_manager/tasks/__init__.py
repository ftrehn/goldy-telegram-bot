from .catalog_tasks import setup_catalog_tasks
from .outbox_tasks import setup_outbox_tasks
from .site_order_tasks import setup_site_order_tasks

__all__ = ["setup_catalog_tasks", "setup_outbox_tasks", "setup_site_order_tasks"]
