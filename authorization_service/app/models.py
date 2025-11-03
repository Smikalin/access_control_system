from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, UniqueConstraint
from .db import Base


class ConflictingGroup(Base):
    __tablename__ = "conflicting_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_code_a: Mapped[str] = mapped_column(String(100), nullable=False)
    group_code_b: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (
        UniqueConstraint("group_code_a", "group_code_b", name="uq_conflict_pair"),
    )
