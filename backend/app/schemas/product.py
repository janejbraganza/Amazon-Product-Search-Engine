"""Pydantic schemas for products.

ProductCreate        validates a product before it is inserted (used by the CSV loader).
ProductRead          the API's JSON representation of one product.
ProductListResponse  one page of products plus pagination metadata.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ProductBase(BaseModel):
    product_name: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    category: str = Field(min_length=1, max_length=100)
    brand: str = Field(min_length=1, max_length=100)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    rating: Decimal = Field(ge=1, le=5, max_digits=2, decimal_places=1)
    review_count: int = Field(ge=0)
    stock_quantity: int = Field(ge=0)


class ProductCreate(ProductBase):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: int = Field(gt=0)
    created_at: datetime


class ProductRead(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime

    # Decimals would be serialised as JSON strings ("19.99") by default; numbers are
    # friendlier for the frontend. Values are stored exactly in PostgreSQL either way.
    @field_serializer("price", "rating")
    def _decimal_to_float(self, value: Decimal) -> float:
        return float(value)


class ProductListResponse(BaseModel):
    items: list[ProductRead]
    total: int = Field(description="Total number of products in the catalogue")
    limit: int
    offset: int


class CategoryCount(BaseModel):
    name: str
    product_count: int


class CategoryListResponse(BaseModel):
    categories: list[CategoryCount] = Field(description="Most products first, then by name")
    total_products: int = Field(description="Sum of all category counts")
