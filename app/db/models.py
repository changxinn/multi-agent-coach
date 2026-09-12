"""
SQLAlchemy ORM models for database tables.
"""
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Uuid,
    text,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    """
    User model for systemdb.users table.

    This table stores authentication and basic user information.
    Fitness profile data is stored in UserFitnessProfile table.
    """

    __tablename__ = "users"
    __table_args__ = ({"schema": "systemdb"},)

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)  # bcrypt hash
    name = Column(String(255), nullable=False)
    role = Column(
        String(20),
        nullable=False,
        default="USER",
        server_default=text("'USER'"),
    )
    enabled = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, server_default=text("CURRENT_TIMESTAMP")
    )

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"


class UserFitnessProfile(Base):
    """
    Fitness profile model for systemdb.user_fitness_profiles table.

    Stores fitness-related user data (goals, level, measurements).
    Linked to users table via user_id foreign key.
    """

    __tablename__ = "user_fitness_profiles"
    __table_args__ = ({"schema": "systemdb"},)

    user_id = Column(
        Integer,
        ForeignKey("systemdb.users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    fitness_goal = Column(
        String(255), nullable=False, default="general fitness", server_default=text("'general fitness'")
    )
    fitness_level = Column(
        String(50), nullable=False, default="beginner", server_default=text("'beginner'")
    )
    weight_kg = Column(Numeric(5, 2), nullable=True)
    height_cm = Column(Numeric(5, 2), nullable=True)
    age = Column(Integer, nullable=True)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=datetime.utcnow,
    )

    def __repr__(self):
        return f"<UserFitnessProfile(user_id={self.user_id}, goal={self.fitness_goal})>"


class ChatSession(Base):
    """Durable, user-owned chat session lifecycle and summary state."""

    __tablename__ = "chat_sessions"
    __table_args__ = ({"schema": "systemdb"},)

    id = Column(BigInteger, primary_key=True)
    session_id = Column(String(37), unique=True, nullable=False)
    user_id = Column(BigInteger, ForeignKey("systemdb.users.id", ondelete="CASCADE"), nullable=False)
    history_start_sequence = Column(BigInteger, nullable=False, default=0)
    next_sequence = Column(BigInteger, nullable=False, default=1)
    summary = Column(String, nullable=True)
    summary_through_sequence = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    deleted_at = Column(DateTime(timezone=True), nullable=True)


class ChatMessageRecord(Base):
    """Append-only durable chat message record."""

    __tablename__ = "chat_messages"
    __table_args__ = ({"schema": "systemdb"},)

    id = Column(BigInteger, primary_key=True)
    session_id = Column(BigInteger, ForeignKey("systemdb.chat_sessions.id", ondelete="CASCADE"), nullable=False)
    sequence = Column(BigInteger, nullable=False)
    role = Column(String(16), nullable=False)
    agent_name = Column(String(100), nullable=True)
    content = Column(String, nullable=False)
    message_metadata = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class ChatTurn(Base):
    """Durable idempotency and response-replay state for one submitted turn."""

    __tablename__ = "chat_turns"
    __table_args__ = ({"schema": "systemdb"},)

    id = Column(BigInteger, primary_key=True)
    session_id = Column(BigInteger, ForeignKey("systemdb.chat_sessions.id", ondelete="CASCADE"), nullable=False)
    idempotency_key = Column(Uuid(as_uuid=False), nullable=False)
    request_fingerprint = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False)
    response_text = Column(String, nullable=True)
    response_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    completed_at = Column(DateTime(timezone=True), nullable=True)
