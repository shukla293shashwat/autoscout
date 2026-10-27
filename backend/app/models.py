"""Declarative base for SQLAlchemy models. Tables are added in later phases."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
