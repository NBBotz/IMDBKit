import logging
from .api import IMDBKit

__all__ = ["IMDBKit"]

logging.getLogger(__name__).addHandler(logging.NullHandler())
