from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, UniqueConstraint
from sqlalchemy.sql import func
from .db import Base

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    access_token = Column(String, nullable=False, unique=True)
    institution_name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    plaid_txn_id = Column(String, unique=True, nullable=False)
    account_id = Column(String, nullable=False)
    name = Column(String, nullable=True)
    merchant_name = Column(String, nullable=True)
    amount = Column(Float, nullable=False)
    date = Column(String, nullable=False)  
    category = Column(String, nullable=True)  
    subcategory = Column(String, nullable=True)
    iso_currency = Column(String, nullable=True, default="USD")
    pending = Column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("plaid_txn_id", name="uq_plaid_txn_id"),
    )

class Budget(Base):
    __tablename__ = "budgets"
    id = Column(Integer, primary_key=True)
    month = Column(String, nullable=False)
    category = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("month", "category", name="uq_month_category"),
    )
