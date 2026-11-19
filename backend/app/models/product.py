"""Product table definition.

See README.md ("Database schema") for the reasoning behind each type and constraint.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Identity,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Product(Base):
    __tablename__ = "products"

    # BY DEFAULT (not ALWAYS) so the loader can insert the dataset's fixed IDs, which
    # makes re-loading idempotent; new rows without an id still get one from the sequence.
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    brand: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # NUMERIC, never FLOAT, for money: exact decimal arithmetic.
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, index=True)
    rating: Mapped[Decimal] = mapped_column(Numeric(2, 1), nullable=False, index=True)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    __table_args__ = (
        CheckConstraint("length(trim(product_name)) > 0", name="ck_products_name_not_blank"),
        CheckConstraint("length(trim(description)) > 0", name="ck_products_description_not_blank"),
        CheckConstraint("price > 0", name="ck_products_price_positive"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_products_rating_range"),
        CheckConstraint("review_count >= 0", name="ck_products_review_count_non_negative"),
        CheckConstraint("stock_quantity >= 0", name="ck_products_stock_non_negative"),
    )

    def __repr__(self) -> str:
        return f"<Product id={self.id} name={self.product_name!r}>"
