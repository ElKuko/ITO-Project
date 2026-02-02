"""SQLAlchemy ORM models for the Ito merchandising app."""

import datetime

from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, Boolean, ForeignKey, Enum
)
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False, default="merchandiser")  # merchandiser | admin
    region = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    visits = relationship("StoreVisit", back_populates="user")


class Store(Base):
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    region = Column(String(100), nullable=False)
    address = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    approvals = relationship("StoreSKUApproval", back_populates="store")
    visits = relationship("StoreVisit", back_populates="store")


class SKU(Base):
    __tablename__ = "skus"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    brand = Column(String(100), nullable=False)
    category = Column(String(100), nullable=True)
    barcode = Column(String(50), nullable=True, unique=True)
    image_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    approvals = relationship("StoreSKUApproval", back_populates="sku")


class StoreSKUApproval(Base):
    __tablename__ = "store_sku_approvals"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    sku_id = Column(Integer, ForeignKey("skus.id"), nullable=False)
    quarter = Column(String(10), nullable=False)  # e.g. "2026-Q1"
    approved_at = Column(DateTime, default=datetime.datetime.utcnow)

    store = relationship("Store", back_populates="approvals")
    sku = relationship("SKU", back_populates="approvals")


class StoreVisit(Base):
    __tablename__ = "store_visits"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    visited_at = Column(DateTime, default=datetime.datetime.utcnow)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String(20), default="submitted")  # submitted | reviewed

    store = relationship("Store", back_populates="visits")
    user = relationship("User", back_populates="visits")
    sku_actions = relationship("VisitSKUAction", back_populates="visit", cascade="all, delete-orphan")
    photos = relationship("VisitPhoto", back_populates="visit", cascade="all, delete-orphan")


class VisitSKUAction(Base):
    __tablename__ = "visit_sku_actions"

    id = Column(Integer, primary_key=True, index=True)
    visit_id = Column(Integer, ForeignKey("store_visits.id"), nullable=False)
    sku_id = Column(Integer, ForeignKey("skus.id"), nullable=False)
    action_type = Column(String(30), nullable=False)  # needs_refill | placed_on_shelf | needs_order
    notes = Column(Text, nullable=True)

    visit = relationship("StoreVisit", back_populates="sku_actions")
    sku = relationship("SKU")


class VisitPhoto(Base):
    __tablename__ = "visit_photos"

    id = Column(Integer, primary_key=True, index=True)
    visit_id = Column(Integer, ForeignKey("store_visits.id"), nullable=False)
    file_path = Column(String(500), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)
    cv_processed = Column(Boolean, default=False)
    cv_results = Column(Text, nullable=True)  # JSON string

    visit = relationship("StoreVisit", back_populates="photos")
