"""SQLAlchemy models. Importing this package registers every table on ``Base.metadata``."""

from app.models.product import Product

__all__ = ["Product"]
