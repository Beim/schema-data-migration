import json
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

    def add_one(
        self, plan: mp.MigrationPlan, operator: str = "", fake: bool = False
    ) -> None:
        # add migration history
        hist = model.MigrationHistory(
            ver=plan.version,
            name=plan.name,
            state=model.MigrationState.PROCESSING,
            type=plan.type,
        )
        self.session.add(hist)
        self.session.flush()
        # add log
        log = model.MigrationHistoryLog(
            hist_id=hist.id,
            operation=Operation.CREATE,
            operator=operator,
            snapshot=self._gen_snapshot_log(plan, fake),
        )
        self.session.add(log)

    def update_succ(
        self, plan: mp.MigrationPlan, operator: str = "", fake: bool = False
    ) -> None:
        self._update(
            plan,
            model.MigrationState.SUCCESSFUL,
            Operation.UPDATE_SUCC,
            operator=operator,
            fake=fake,
        )

    def update_rollback(
        self, plan: mp.MigrationPlan, operator: str = "", fake: bool = False
    ) -> None:
        self._update(
            plan,
            model.MigrationState.ROLLBACKING,
            Operation.UPDATE_ROLLBACK,
            operator=operator,
            fake=fake,
        )

    def _gen_snapshot_log(self, plan: mp.MigrationPlan, fake: bool) -> str:
        plan_for_log = plan.to_dict_for_log()
        if fake:
            plan_for_log.update({"fake": fake})
        return json.dumps(plan_for_log)

    def _update(
        self,
        plan: mp.MigrationPlan,
        state: model.MigrationState,
        operation: Operation,
        operator: str = "",
        fake: bool = False,
    ) -> None:
        # update migration history
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
        # add log
        log = model.MigrationHistoryLog(
            hist_id=hist.id,
            operation=operation,
            operator=operator,
            snapshot=self._gen_snapshot_log(plan, fake),
        )
        self.session.add(log)

    def delete(
        self, plan: mp.MigrationPlan, operator: str = "", fake: bool = False
    ) -> None:
        # delete migration history
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
        # add log
        log = model.MigrationHistoryLog(
            hist_id=hist.id,
            operation=Operation.DELETE,
            operator=operator,
            snapshot=self._gen_snapshot_log(plan, fake),
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
