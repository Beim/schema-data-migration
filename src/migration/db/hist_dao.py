from enum import StrEnum
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from migration import migration_plan as mp

from . import model


class Operation(StrEnum):
    CREATE = "create"
    DELETE = "delete"
    UPDATE_SUCC = "update_succ"
    UPDATE_ROLLBACK = "update_rollback"


class MigrationHistoryDAO:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_one(self, plan: mp.MigrationPlan, operator: str = "") -> None:
        hist = model.MigrationHistory(
            ver=plan.version,
            name=plan.name,
            state=model.MigrationState.PROCESSING,
        )
        self.session.add(hist)
        self.session.flush()
        log = model.MigrationHistoryLog(
            hist_id=hist.id,
            operation=Operation.CREATE,
            operator=operator,
            snapshot=plan.to_log_str(),
        )
        self.session.add(log)

    def update_succ(self, plan: mp.MigrationPlan, operator: str = "") -> None:
        self._update(
            plan,
            model.MigrationState.SUCCESSFUL,
            Operation.UPDATE_SUCC,
            operator=operator,
        )

    def update_rollback(self, plan: mp.MigrationPlan, operator: str = "") -> None:
        self._update(
            plan,
            model.MigrationState.ROLLBACKING,
            Operation.UPDATE_ROLLBACK,
            operator=operator,
        )

    def _update(
        self,
        plan: mp.MigrationPlan,
        state: model.MigrationState,
        operation: Operation,
        operator: str = "",
    ) -> None:
        stmt = (
            select(model.MigrationHistory)
            .where(
                model.MigrationHistory.ver == plan.version
                and model.MigrationHistory.name == plan.name
            )
            .with_for_update()
        )
        hist = self.session.scalars(stmt).one()
        hist.state = state

        log = model.MigrationHistoryLog(
            hist_id=hist.id,
            operation=operation,
            operator=operator,
            snapshot=plan.to_log_str(),
        )
        self.session.add(log)

    def delete(self, plan: mp.MigrationPlan, operator: str = "") -> None:
        stmt = (
            select(model.MigrationHistory)
            .where(
                model.MigrationHistory.ver == plan.version
                and model.MigrationHistory.name == plan.name
            )
            .with_for_update()
        )
        hist = self.session.scalars(stmt).one()
        self.session.delete(hist)

        log = model.MigrationHistoryLog(
            hist_id=hist.id,
            operation=Operation.DELETE,
            operator=operator,
            snapshot=plan.to_log_str(),
        )
        self.session.add(log)

    def get_all(self) -> List[model.MigrationHistory]:
        return (
            self.session.query(model.MigrationHistory)
            .order_by(model.MigrationHistory.id.asc())
            .with_for_update()
            .all()
        )

    def get_latest(self) -> model.MigrationHistory:
        return (
            self.session.query(model.MigrationHistory)
            .order_by(model.MigrationHistory.id.desc())
            .with_for_update()
            .first()
        )

    def get_by_ver(self, ver: str) -> List[model.MigrationHistory]:
        return (
            self.session.query(model.MigrationHistory)
            .filter(model.MigrationHistory.ver == ver)
            .with_for_update()
            .all()
        )

    def clear_all(self) -> None:
        self.session.query(model.MigrationHistory).delete()

    def commit(self) -> None:
        self.session.commit()
