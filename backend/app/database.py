"""
database.py — SQLite (PoC) / PostgreSQL (production) layer for e₹ Bridge.

Tables: users, wallets, transactions, audit_log, corridors
Switch to PostgreSQL: set DATABASE_URL=postgresql://... in .env
"""

import os, uuid
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, String, Float, Integer,
    Boolean, DateTime, Text, ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.sql import func

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./erupee_bridge.db")
engine = create_engine(DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(20))
    country = Column(String(10), default="IN")
    hashed_password = Column(String(255), nullable=False)
    kyc_status = Column(String(20), default="pending")
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    lrs_used_inr = Column(Float, default=0.0)
    lrs_year = Column(Integer, default=lambda: datetime.now().year)
    created_at = Column(DateTime, server_default=func.now())
    wallets = relationship("Wallet", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")

class Wallet(Base):
    __tablename__ = "wallets"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    wallet_id = Column(String(50), unique=True, nullable=False, index=True)
    currency = Column(String(10), default="INR")
    cbdc_type = Column(String(20), default="retail")
    balance = Column(Float, default=0.0)
    is_frozen = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    user = relationship("User", back_populates="wallets")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tx_id = Column(String(36), unique=True, nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    sender_wallet = Column(String(50), nullable=False, index=True)
    recipient_address = Column(String(100), nullable=False)
    recipient_country = Column(String(10), nullable=False)
    amount_inr = Column(Float, nullable=False)
    bridge_fee_inr = Column(Float)
    fx_rate = Column(Float)
    converted_amount = Column(Float)
    target_currency = Column(String(10))
    purpose_code = Column(String(10), nullable=False)
    status = Column(String(20), default="pending")
    cbdc_tx_hash = Column(String(80))
    bridge_tx_hash = Column(String(80))
    settlement_block = Column(Integer)
    ai_risk_score = Column(Integer)
    ai_risk_level = Column(String(10))
    ai_fema_confidence = Column(String(10))
    corridor_type = Column(String(20), default="direct")
    dollar_used = Column(Boolean, default=False)
    data_stored_india = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    settled_at = Column(DateTime)
    user = relationship("User", back_populates="transactions")

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    details = Column(Text)
    ip_address = Column(String(45))
    severity = Column(String(10), default="INFO")
    created_at = Column(DateTime, server_default=func.now())
    user = relationship("User", back_populates="audit_logs")

class Corridor(Base):
    __tablename__ = "corridors"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_country = Column(String(10), nullable=False)
    source_currency = Column(String(10), nullable=False)
    dest_country = Column(String(10), nullable=False)
    dest_currency = Column(String(10), nullable=False)
    fx_rate_from_inr = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    srva_enabled = Column(Boolean, default=False)
    cbdc_enabled = Column(Boolean, default=False)
    bridge_fee_pct = Column(Float, default=0.2)
    swift_fee_pct = Column(Float, default=6.3)
    volume_30d_inr = Column(Float, default=0.0)
    tx_count_30d = Column(Integer, default=0)

def create_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def seed_corridors(db):
    if db.query(Corridor).count() == 0:
        for row in [
            ("IN","INR","AE","AED",0.044,True,True),
            ("CA","CAD","AE","AED",0.044,True,True),
            ("US","USD","AE","AED",0.044,True,True),
            ("IN","INR","SG","SGD",0.016,True,True),
            ("IN","INR","RU","RUB",0.93,True,False),
            ("IN","INR","BR","BRL",0.016,False,False),
            ("IN","INR","ZA","ZAR",0.22,False,False),
            ("IN","INR","SA","SAR",0.045,True,False),
            ("IN","INR","EG","EGP",0.37,False,False),
            ("IN","INR","ID","IDR",1360.0,False,False),
            ("IN","INR","MY","MYR",0.055,True,False),
            ("IN","INR","GB","GBP",0.0095,False,False),
        ]:
            db.add(Corridor(source_country=row[0],source_currency=row[1],
                dest_country=row[2],dest_currency=row[3],fx_rate_from_inr=row[4],
                srva_enabled=row[5],cbdc_enabled=row[6],bridge_fee_pct=0.2,swift_fee_pct=6.3))
        db.commit()
