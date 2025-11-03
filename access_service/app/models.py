from sqlalchemy import Column, Integer, String, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional
from .db import Base


class Resource(Base):
    """
    Модель ресурса, к которому требуется доступ.
    Поля:
    - id: уникальный идентификатор ресурса
    - name: уникальное имя ресурса
    - description: произвольное описание
    Связи:
    - required_accesses: список требуемых доступов (`ResourceAccess`)
    """

    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    required_accesses: Mapped[list["ResourceAccess"]] = relationship(
        "ResourceAccess",
        back_populates="resource",
        cascade="all, delete-orphan"
    )


class Access(Base):
    """
    Модель типа доступа (например, DB_READ, API_KEY).
    Поля:
    - id: уникальный идентификатор доступа
    - code: уникальный код доступа
    - description: описание
    Связи:
    - groups: связи доступа с группами (`GroupAccess`)
    """

    __tablename__ = "accesses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    groups: Mapped[list["GroupAccess"]] = relationship(
        "GroupAccess",
        back_populates="access",
        cascade="all, delete-orphan"
    )


class RightGroup(Base):
    """
    Модель группы прав (роль), агрегирующей доступы.
    Поля:
    - id: идентификатор группы
    - code: уникальный код группы (например, DEVELOPER)
    - description: описание
    Связи:
    - accesses: список доступов группы (`GroupAccess`)
    """

    __tablename__ = "right_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    accesses: Mapped[list["GroupAccess"]] = relationship(
        "GroupAccess",
        back_populates="group",
        cascade="all, delete-orphan"
    )


class GroupAccess(Base):
    """
    Связь группа-доступ (многие-ко-многим через явную таблицу).
    Уникальность (group_id, access_id) гарантирует отсутствие дубликатов.
    """

    __tablename__ = "group_accesses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("right_groups.id", ondelete="CASCADE"), nullable=False
    )
    access_id: Mapped[int] = mapped_column(
        ForeignKey("accesses.id", ondelete="CASCADE"), nullable=False
    )

    group: Mapped[RightGroup] = relationship(
        "RightGroup",
        back_populates="accesses"
    )
    access: Mapped[Access] = relationship("Access", back_populates="groups")

    __table_args__ = (
        UniqueConstraint("group_id", "access_id", name="uq_group_access"),
    )


class ResourceAccess(Base):
    """
    Связь ресурс→требуемый доступ.
    Уникальность (resource_id, access_id) предотвращает дублирование требований.
    """

    __tablename__ = "resource_accesses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), nullable=False
    )
    access_id: Mapped[int] = mapped_column(
        ForeignKey("accesses.id", ondelete="CASCADE"), nullable=False
    )

    resource: Mapped[Resource] = relationship(
        "Resource", back_populates="required_accesses"
    )
    access: Mapped[Access] = relationship("Access")

    __table_args__ = (
        UniqueConstraint("resource_id", "access_id", name="uq_resource_access"),
    )


class UserAccess(Base):
    """
    Прямой доступ пользователя (не через группу).
    Уникальность (user_id, access_id) обеспечивает идемпотентность выдачи.
    """

    __tablename__ = "user_accesses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    access_id: Mapped[int] = mapped_column(
        ForeignKey("accesses.id", ondelete="CASCADE"), nullable=False
    )

    access: Mapped[Access] = relationship("Access")

    __table_args__ = (UniqueConstraint("user_id", "access_id", name="uq_user_access"),)


class UserGroup(Base):
    """
    Принадлежность пользователя группе прав.
    Уникальность (user_id, group_id) предотвращает повторные назначения.
    """

    __tablename__ = "user_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("right_groups.id", ondelete="CASCADE"), nullable=False
    )

    group: Mapped[RightGroup] = relationship("RightGroup")

    __table_args__ = (UniqueConstraint("user_id", "group_id", name="uq_user_group"),)
