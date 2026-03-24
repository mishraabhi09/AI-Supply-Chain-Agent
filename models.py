from pydantic import BaseModel, ConfigDict
from typing import Optional

class Product(BaseModel):
    product_id: str
    name: str
    category: str
    model_config = ConfigDict(from_attributes=True)

class Inventory(BaseModel):
    product_id: str
    stock: int
    reorder_level: int
    lead_time_days: int
    model_config = ConfigDict(from_attributes=True)

class Supplier(BaseModel):
    supplier_id: str
    name: str
    location: str
    status: str
    model_config = ConfigDict(from_attributes=True)

class Order(BaseModel):
    order_id: str
    product_id: str
    supplier_id: str
    quantity: int
    cost: float
    status: str
    model_config = ConfigDict(from_attributes=True)

class Event(BaseModel):
    event_id: str
    type: str
    location: str
    severity: str
    timestamp: str
    model_config = ConfigDict(from_attributes=True)

class AuditLog(BaseModel):
    log_id: Optional[int] = None
    timestamp: str
    action: str
    decision: str
    guardrail_status: str
    details: str
    model_config = ConfigDict(from_attributes=True)
