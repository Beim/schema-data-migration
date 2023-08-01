import datetime
import enum

from sqlalchemy import BIGINT, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.types import DateTime

from migration.env import cli_env


class Base(DeclarativeBase):
    type_annotation_map = {
        int: BIGINT,
    }


class MigrationState(enum.Enum):
    """
    [new] -> PROCESSING
    PROCESSING -> SUCCESSFUL
    SUCCESSFUL -> ROLLBACKING
    ROLLBACKING -> [deleted]
    """

    PROCESSING = "PROCESSING"
    SUCCESSFUL = "SUCCESSFUL"
    ROLLBACKING = "ROLLBACKING"


TABLE_ARGS = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}


class MigrationHistory(Base):
    __tablename__ = cli_env.TABLE_MIGRATION_HISTORY
    __table_args__ = (
        UniqueConstraint("ver", "name", name="uniq_ver_name"),
        TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ver: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(255))
    state: Mapped[MigrationState]
    created: Mapped[DateTime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    updated: Mapped[DateTime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    def can_match(self, ver: str, name: str) -> bool:
        return self.ver == ver and self.name == name


class MigrationHistoryLog(Base):
    __tablename__ = cli_env.TABLE_MIGRATION_HISTORY_LOG
    __table_args__ = TABLE_ARGS

    id: Mapped[int] = mapped_column(primary_key=True)
    hist_id: Mapped[int] = mapped_column(Integer)
    operation: Mapped[str] = mapped_column(String(255))
    snapshot: Mapped[str] = mapped_column(Text(), default="")
    operator: Mapped[str] = mapped_column(String(255), default="")
    created: Mapped[DateTime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
