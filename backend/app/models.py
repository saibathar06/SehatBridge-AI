import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, Float, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc).timestamp()


class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email_hash: Mapped[str] = mapped_column(String(64), unique=True)
    email: Mapped[str] = mapped_column(Text)
    password: Mapped[str] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    token_version: Mapped[int] = mapped_column(Integer, default=0)


class Owned:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    data: Mapped[str] = mapped_column(Text)  # AES-GCM authenticated, table + owner bound


class Profile(Owned, Base):
    __tablename__ = 'profiles'
    __table_args__ = (UniqueConstraint('user_id'),)


class OTP(Owned, Base):
    __tablename__ = 'otp_challenges'
    purpose: Mapped[str] = mapped_column(String(20))
    digest: Mapped[str] = mapped_column(String(64))
    expires: Mapped[int] = mapped_column(Integer)
    created: Mapped[int] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class Refresh(Owned, Base):
    __tablename__ = 'refresh_tokens'
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    expires: Mapped[int] = mapped_column(Integer)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class Document(Owned, Base):
    __tablename__ = 'medical_documents'
    status: Mapped[str] = mapped_column(String(20), default='queued', index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[int] = mapped_column(Integer, default=0)


class Page(Owned, Base):
    __tablename__ = 'document_pages'
    document_id: Mapped[str] = mapped_column(ForeignKey('medical_documents.id', ondelete='CASCADE'))
    position: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint('document_id', 'position'),)


class Analysis(Owned, Base):
    __tablename__ = 'document_analyses'
    document_id: Mapped[str] = mapped_column(ForeignKey('medical_documents.id', ondelete='CASCADE'), unique=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class Treatment(Owned, Base):
    __tablename__ = 'treatments'
    document_id: Mapped[str] = mapped_column(ForeignKey('medical_documents.id', ondelete='CASCADE'), unique=True)
    status: Mapped[str] = mapped_column(String(20), default='active')
    revision: Mapped[int] = mapped_column(Integer, default=1)


class Medicine(Owned, Base):
    __tablename__ = 'treatment_medicines'
    treatment_id: Mapped[str] = mapped_column(ForeignKey('treatments.id', ondelete='CASCADE'))


class Schedule(Owned, Base):
    __tablename__ = 'medication_schedules'
    treatment_id: Mapped[str] = mapped_column(ForeignKey('treatments.id', ondelete='CASCADE'))
    medicine_id: Mapped[str] = mapped_column(ForeignKey('treatment_medicines.id', ondelete='CASCADE'))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Dose(Owned, Base):
    __tablename__ = 'dose_instances'
    schedule_id: Mapped[str] = mapped_column(ForeignKey('medication_schedules.id', ondelete='CASCADE'))
    due_at: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(16), default='upcoming')
    __table_args__ = (UniqueConstraint('schedule_id', 'due_at'),)


class DoseEvent(Owned, Base):
    __tablename__ = 'dose_events'
    dose_id: Mapped[str] = mapped_column(ForeignKey('dose_instances.id', ondelete='CASCADE'))
    idempotency_key: Mapped[str] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint('user_id', 'idempotency_key'),)


class FollowUp(Owned, Base):
    __tablename__ = 'follow_up_visits'
    treatment_id: Mapped[str] = mapped_column(ForeignKey('treatments.id', ondelete='CASCADE'))


class LabTest(Owned, Base):
    __tablename__ = 'laboratory_tests'
    treatment_id: Mapped[str] = mapped_column(ForeignKey('treatments.id', ondelete='CASCADE'))


class Instruction(Owned, Base):
    __tablename__ = 'care_instructions'
    treatment_id: Mapped[str] = mapped_column(ForeignKey('treatments.id', ondelete='CASCADE'))


class Conversation(Owned, Base):
    __tablename__ = 'chat_conversations'
    __table_args__ = (UniqueConstraint('user_id'),)


class Chat(Owned, Base):
    __tablename__ = 'chat_messages'
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey('chat_conversations.id', ondelete='CASCADE', name='fk_chat_messages_conversation'), nullable=True)
    created_at: Mapped[float] = mapped_column(Float, default=now)


class Preferences(Owned, Base):
    __tablename__ = 'notification_preferences'
    __table_args__ = (UniqueConstraint('user_id'),)


class Device(Owned, Base):
    __tablename__ = 'device_tokens'
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)


class Delivery(Owned, Base):
    __tablename__ = 'notification_deliveries'
    dose_id: Mapped[str] = mapped_column(ForeignKey('dose_instances.id', ondelete='CASCADE'))
    device_id: Mapped[str] = mapped_column(ForeignKey('device_tokens.id', ondelete='CASCADE'))
    status: Mapped[str] = mapped_column(String(20))
    __table_args__ = (UniqueConstraint('dose_id', 'device_id'),)


class Provider(Base):
    __tablename__ = 'demo_providers'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(100))
    data: Mapped[str] = mapped_column(Text)  # public synthetic catalogue


class Slot(Base):
    __tablename__ = 'demo_slots'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    provider_id: Mapped[str] = mapped_column(ForeignKey('demo_providers.id'))
    starts: Mapped[str] = mapped_column(String(40))


class Booking(Owned, Base):
    __tablename__ = 'demo_bookings'
    slot_id: Mapped[str | None] = mapped_column(ForeignKey('demo_slots.id'), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='booked')


class Inventory(Base):
    __tablename__ = 'demo_inventory'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    provider_id: Mapped[str] = mapped_column(ForeignKey('demo_providers.id'))
    name: Mapped[str] = mapped_column(String(100))
    price_paise: Mapped[int] = mapped_column(Integer)


class Order(Owned, Base):
    __tablename__ = 'demo_orders'
    status: Mapped[str] = mapped_column(String(20), default='simulated')


class OrderItem(Owned, Base):
    __tablename__ = 'demo_order_items'
    order_id: Mapped[str] = mapped_column(ForeignKey('demo_orders.id', ondelete='CASCADE'))


class Audit(Owned, Base):
    __tablename__ = 'audit_events'
