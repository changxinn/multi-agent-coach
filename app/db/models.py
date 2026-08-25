"""
SQLAlchemy ORM models for database tables.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    Boolean,
    DateTime,
    ForeignKey,
    text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    """
    User model for systemdb.users table.

    This table stores authentication and basic user information.
    Fitness profile data is stored in UserFitnessProfile table.
    """

    __tablename__ = "users"
    __table_args__ = {"schema": "systemdb"}

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
    __table_args__ = {"schema": "systemdb"}

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
