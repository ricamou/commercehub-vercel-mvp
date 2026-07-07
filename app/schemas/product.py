from pydantic import BaseModel


class Product(BaseModel):
    sku: str
    name: str
    description: str
    cost_price: float
    stock: int
    weight_kg: float
    height_cm: float
    width_cm: float
    length_cm: float
    category: str
    brand: str
    ean: str
    image_url: str
