"""Shared base for every table: naming rules for constraints, id, and timestamps."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, Enum, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Predictable constraint names, e.g. "fk_projects_user_id_users".
# Without this, Postgres invents names and later migrations can't find them to change or drop.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class IdMixin:
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)


class TimestampMixin:
    # Timezone-aware, set by the database clock (not the app server's).
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def text_enum[E: StrEnum](enum_cls: type[E], name: str) -> Enum:
    """Store a Python enum as plain text plus a CHECK constraint (not a Postgres ENUM type).

    Adding a value later is then a simple migration. The stored text is the enum's value
    ("new"), not its Python name ("NEW").
    """
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        values_callable=lambda e: [m.value for m in e],
    )
