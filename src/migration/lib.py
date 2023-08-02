import collections
import configparser
import importlib.util
import logging
import os
import shlex
import shutil
import subprocess
import tempfile
from argparse import Namespace
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session
from tabulate import tabulate

from . import err, helper
from . import migration_plan as mp
from .db import hist_dao, model
from .db.db import make_session
from .env import cli_env

logger = logging.getLogger(__name__)


def check_file_existence(paths: List[str]):
    for path in paths:
        if os.path.exists(path):
            raise Exception(f"{path} already exists")


def call_skeema(raw_args: List[str], cwd: str = cli_env.MIGRATION_CWD, env=None):
    # https://stackoverflow.com/questions/39872088/executing-interactive-shell-script-in-python
    cmd = f"{cli_env.SKEEMA_CMD_PATH} " + " ".join(raw_args)
    logger.info("Run %s", cmd)
    subprocess.check_call(shlex.split(cmd), cwd=cwd, env=env)


def parse_env_ini() -> configparser.ConfigParser:
    file_path = os.path.join(cli_env.MIGRATION_CWD, cli_env.ENV_INI_FILE)
    with open(file_path) as f:
        data = "[DEFAULT]\n" + f.read()
    config = configparser.ConfigParser()
    config.read_string(data)
    return config


def get_env_ini_section(env: str) -> configparser.SectionProxy:
    cfg = parse_env_ini()
    if not cfg.has_section(env):
        raise Exception(f"env {env} not found in {cli_env.ENV_INI_FILE}")
    return cfg[env]


def get_env_with_update(update_env: Dict[str, str]) -> Dict[str, str]:
    os_env = os.environ.copy()
    os_env.update(update_env)
    return os_env


def build_session_from_env(env: str, echo: bool = False) -> Session:
    section = get_env_ini_section(env)
    return make_session(
        host=section["host"],
        port=int(section["port"]),
        user=section["user"],
        password=cli_env.MYSQL_PWD,
        schema=section["schema"],
        echo=echo,
    )


def files_under_dir(dir_path: str, ends_with: str) -> Dict[str, str]:
    """
    return a map of file name to file path
    """
    res: Dict[str, str] = {}
    for root, _, files in os.walk(dir_path):
        for file in files:
            if not file.endswith(ends_with):
                continue
            res[file] = os.path.join(root, file)
    return res


class Migrator:
    def forward(self, migration_plan: mp.MigrationPlan, args: Namespace):
        raise NotImplementedError

    def backward(self, migration_plan: mp.MigrationPlan, args: Namespace):
        raise NotImplementedError


class CLIMigrator(Migrator):
    def forward(self, migration_plan: mp.MigrationPlan, args: Namespace):
        logger.info(f"Executing {migration_plan}")
        if migration_plan.type == mp.Type.SCHEMA:
            sha1 = migration_plan.change.forward.id
            self.move_schema_to(sha1, args)
            return
        if migration_plan.type in [mp.Type.DATA, mp.Type.REPEATABLE]:
            if migration_plan.change.forward.type == mp.DataChangeType.SQL:
                self.migrate_data_sql(migration_plan.change.forward.sql, args)
                return
            if migration_plan.change.forward.type == mp.DataChangeType.SQL_FILE:
                self.migrate_data_sql_file(migration_plan.change.forward.file, args)
                return
            if migration_plan.change.forward.type == mp.DataChangeType.PYTHON:
                self.migrate_data_python(migration_plan.change.forward.file, args)
                return
            if migration_plan.change.forward.type == mp.DataChangeType.SHELL:
                self.migrate_data_shell(migration_plan.change.forward.file, args)
                return
            if migration_plan.change.forward.type == mp.DataChangeType.TYPESCRIPT:
                self.migrate_data_typescript(migration_plan.change.forward.file, args)
                return

    def backward(self, migration_plan: mp.MigrationPlan, args: Namespace):
        logger.info(f"Rollbacking {migration_plan}")
        if migration_plan.type == mp.Type.SCHEMA:
            sha1 = migration_plan.change.backward.id
            self.move_schema_to(sha1, args)
            return
        if migration_plan.type == mp.Type.DATA:
            if migration_plan.change.backward.type == mp.DataChangeType.SQL:
                self.migrate_data_sql(migration_plan.change.backward.sql, args)
                return
            if migration_plan.change.backward.type == mp.DataChangeType.SQL_FILE:
                self.migrate_data_sql_file(migration_plan.change.backward.file, args)
                return
            if migration_plan.change.backward.type == mp.DataChangeType.PYTHON:
                self.migrate_data_python(migration_plan.change.backward.file, args)
                return
            if migration_plan.change.backward.type == mp.DataChangeType.SHELL:
                self.migrate_data_shell(migration_plan.change.backward.file, args)
                return
            if migration_plan.change.backward.type == mp.DataChangeType.TYPESCRIPT:
                self.migrate_data_typescript(migration_plan.change.backward.file, args)
                return

    def migrate_data_shell(self, shell_file: str, args: Namespace):
        shell_file_path = os.path.join(
            cli_env.MIGRATION_CWD, cli_env.DATA_DIR, shell_file
        )
        section = get_env_ini_section(args.environment)
        cmd = f"sh {shell_file_path}"
        subprocess.check_call(
            shlex.split(cmd),
            cwd=cli_env.MIGRATION_CWD,
            env=get_env_with_update(
                {
                    "MYSQL_PWD": cli_env.MYSQL_PWD,
                    "HOST": section["host"],
                    "PORT": section["port"],
                    "USER": section["user"],
                    "SCHEMA": section["schema"],
                }
            ),
        )

    def migrate_data_typescript(self, ts_file: str, args: Namespace):
        section = get_env_ini_section(args.environment)
        ts_file_path = os.path.join(cli_env.MIGRATION_CWD, cli_env.DATA_DIR, ts_file)
        # create temporary directory under migration cwd/tmp
        with tempfile.TemporaryDirectory(dir=cli_env.MIGRATION_CWD) as temp_dir:
            src_path = os.path.join(temp_dir, "src")
            os.makedirs(src_path)
            # copy ts file to temp directory
            with open(os.path.join(src_path, "index.ts"), "w") as f:
                f.write(
                    cli_env.SAMPLE_INDEX_TS
                    % ("true" if cli_env.ALLOW_ECHO_SQL else "false")
                )
            shutil.copy(
                ts_file_path,
                os.path.join(src_path, "migration.ts"),  # import by index.ts
            )
            # build js file
            subprocess.check_call(
                shlex.split(f"{cli_env.NPM_CMD_PATH} run build"), cwd=temp_dir
            )
            # run js file
            subprocess.check_call(
                [cli_env.NODE_CMD_PATH, "src/index.js"],
                cwd=temp_dir,
                env=get_env_with_update(
                    {
                        "MYSQL_PWD": cli_env.MYSQL_PWD,
                        "HOST": section["host"],
                        "PORT": section["port"],
                        "USER": section["user"],
                        "SCHEMA": section["schema"],
                    }
                ),
            )

    def migrate_data_python(self, python_file: str, args: Namespace):
        python_file_path = os.path.join(
            cli_env.MIGRATION_CWD, cli_env.DATA_DIR, python_file
        )
        spec = importlib.util.spec_from_file_location("run_python", python_file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        session = build_session_from_env(args.environment, echo=cli_env.ALLOW_ECHO_SQL)
        module.run(session)

    def migrate_data_sql_file(self, sql_file: str, args: Namespace):
        with open(os.path.join(cli_env.MIGRATION_CWD, cli_env.DATA_DIR, sql_file)) as f:
            sql = f.read()
        self.migrate_data_sql(sql, args)

    def migrate_data_sql(self, sql: str, args: Namespace):
        session = build_session_from_env(args.environment, echo=cli_env.ALLOW_ECHO_SQL)
        with session.begin():
            result = session.execute(text(sql))
            logger.info(f"migrate data, sql={sql}, result.rowcount={result.rowcount}")

    def move_schema_to(self, sha1: str, args: Namespace):
        index_file = os.path.join(
            cli_env.MIGRATION_CWD, cli_env.SCHEMA_STORE_DIR, sha1[:2], sha1[2:]
        )
        with open(index_file, "r") as f:
            lines = f.readlines()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.makedirs(os.path.join(temp_dir, cli_env.SCHEMA_DIR), exist_ok=False)
            shutil.copy(
                os.path.join(cli_env.MIGRATION_CWD, cli_env.SCHEMA_DIR, ".skeema"),
                os.path.join(temp_dir, cli_env.SCHEMA_DIR, ".skeema"),
            )
            for line in lines:
                [sha1, sql_filename] = line.split(":")
                shutil.copy(
                    os.path.join(
                        cli_env.MIGRATION_CWD,
                        cli_env.SCHEMA_STORE_DIR,
                        sha1[:2],
                        sha1[2:],
                    ),  # sql_filepath
                    os.path.join(temp_dir, cli_env.SCHEMA_DIR, sql_filename.strip()),
                )
            skeema_args = [
                "push",
                args.environment,
            ]
            if cli_env.ALLOW_UNSAFE:
                skeema_args.extend(["--allow-unsafe"])
            call_skeema(raw_args=skeema_args, cwd=temp_dir)
        pass


class CLI:
    def __init__(self, args: Namespace = None, migrator: Migrator = CLIMigrator()):
        self.args = args
        self.mpm: mp.MigrationPlanManager = None
        self.dao: hist_dao.MigrationHistoryDAO = None
        self.migrator = migrator

    def build_dao(self) -> hist_dao.MigrationHistoryDAO:
        session = build_session_from_env(
            self.args.environment, echo=cli_env.ALLOW_ECHO_SQL
        )
        self.dao = hist_dao.MigrationHistoryDAO(session)
        return self.dao

    def _check_migration_histories(
        self, migration_histories: List[model.MigrationHistory], fix: bool = False
    ):
        if len(migration_histories) > self.mpm.count():
            raise Exception(
                "unexpected migration history,"
                f" len(migration_histories)={len(migration_histories)},"
                f" len(migration_plans)={self.mpm.count()}"
            )
        # the history and migration plans should match
        for idx, hist in enumerate(migration_histories):
            if hist.state != model.MigrationState.SUCCESSFUL:
                # if fix mode, the last history can be PROCESSING or ROLLBACKING
                if fix and idx == len(migration_histories) - 1:
                    if (
                        hist.state == model.MigrationState.PROCESSING
                        or hist.state == model.MigrationState.ROLLBACKING
                    ):
                        continue
                raise Exception(
                    f"migration is not successful, ver={hist.ver}, name={hist.name}"
                )
            plan = self.mpm.get_plan_by_index(idx)
            if not hist.can_match(plan.version, plan.name, plan.get_checksum()):
                raise Exception(
                    f"unexpected migration history, ver={hist.ver}, name={hist.name},"
                    f" checksum={hist.checksum}"
                )

    def _get_and_check_versioned_migration_histories(
        self, fix: bool = False
    ) -> List[model.MigrationHistory]:
        migration_histories = self.dao.get_all_versioned()
        self._check_migration_histories(migration_histories, fix=fix)
        return migration_histories

    def fix_rollback(self):
        self.fix_migrate(forward=False)

    def fix_migrate(self, forward: bool = True):
        self.read_migration_plans()
        fake = self.args.fake if "fake" in self.args else False
        operator = self.args.operator if "operator" in self.args else ""

        dao = self.build_dao()
        with dao.session.begin():
            migration_histories = self._get_and_check_versioned_migration_histories(
                fix=True
            )
            if (
                len(migration_histories) == 0
                or migration_histories[-1].state == model.MigrationState.SUCCESSFUL
            ):
                logger.info("no need to fix migration")
                return
            target_plan = self.mpm.get_plan_by_index(len(migration_histories) - 1)
            if forward:
                if not fake:
                    self.migrator.forward(target_plan, self.args)
                dao.update_succ(target_plan, operator=operator, fake=fake)
            else:
                if not fake:
                    self.migrator.backward(target_plan, self.args)
                dao.delete(target_plan, operator=operator, fake=fake)
            dao.commit()

    def print_dry_run(self, plans: List[mp.MigrationPlan], is_migrate: bool):
        new_plans = plans if is_migrate else reversed(plans)
        print(
            tabulate(
                [
                    [
                        p.version,
                        p.name,
                        p.type,
                        (
                            p.change.forward.to_str_for_print()
                            if p.change.forward is not None
                            else None
                        ),
                        (
                            p.change.backward.to_str_for_print()
                            if p.change.backward is not None
                            else None
                        ),
                    ]
                    for p in new_plans
                ],
                headers=[
                    "ver",
                    "name",
                    "type",
                    "forward",
                    "backward",
                ],
                tablefmt="orgtbl",
            )
        )

    def _migrate_versioned(
        self, ver: str, name: str, fake: bool, dry_run: bool, operator: str = ""
    ) -> List[mp.MigrationPlan]:
        """
        Apply versioned migration plans
        return applied plans
        """
        dao = self.build_dao()
        applied_plans: List[mp.MigrationPlan] = []
        with dao.session.begin():
            versioned_migration_histories = (
                self._get_and_check_versioned_migration_histories()
            )
            len_applied_versioned = len(versioned_migration_histories)
            applied_plans = self.mpm.get_plans()[:len_applied_versioned]

            # versioned migration has been applied
            if len_applied_versioned == self.mpm.count():
                return applied_plans
            # create new migration history if needed
            next_plan_index = len_applied_versioned
            if ver is None:
                new_plans = self.mpm.must_get_plan_between(next_plan_index, None)
            else:
                new_plans = self.mpm.must_get_plan_between(
                    next_plan_index,
                    mp.MigrationSignature(version=ver, name=name),
                )
            if len(new_plans) > 0:
                if dry_run:
                    logger.info("migration plans to execute:")
                    self.print_dry_run(new_plans, is_migrate=True)
                    return applied_plans
                dao.add_one(new_plans[0], operator=operator, fake=fake)
                dao.commit()

        while len(new_plans) > 0:
            # migrate operation
            if not fake:
                self.migrator.forward(new_plans[0], self.args)
            # update migration history and create new migration history if needed
            with dao.session.begin():
                latest_hist = dao.get_latest_versioned()
                if latest_hist is None:
                    raise Exception("unexpected migration history, latest_hist is None")
                if not latest_hist.can_match(
                    new_plans[0].version, new_plans[0].name, new_plans[0].get_checksum()
                ):
                    raise Exception(
                        f"unexpected migration history, ver={latest_hist.ver},"
                        f" name={latest_hist.name}"
                    )
                if latest_hist.state != model.MigrationState.PROCESSING:
                    raise Exception(
                        f"unexpected migration history state, ver={latest_hist.ver},"
                        f" name={latest_hist.name}, state={latest_hist.state}"
                    )
                dao.update_succ(new_plans[0], operator=operator, fake=fake)
                applied_plans.append(new_plans[0])
                new_plans = new_plans[1:]
                if len(new_plans) > 0:
                    dao.add_one(new_plans[0], operator=operator, fake=fake)
                dao.commit()

        return applied_plans

    def migrate(self):
        ver = (
            self.args.version.zfill(4)
            if ("version" in self.args) and (self.args.version is not None)
            else None
        )
        name = self.args.name if "name" in self.args else None
        fake = self.args.fake if "fake" in self.args else False
        dry_run = self.args.dry_run if "dry_run" in self.args else False
        operator = self.args.operator if "operator" in self.args else ""

        if dry_run:
            logger.info("running in dry run mode, no migration will be executed")

        self.read_migration_plans()
        self._check_integrity()

        logger.debug(
            f"migrate options: ver={ver}, name={name}, fake={fake}, dry_run={dry_run}"
        )

        # versioned migration
        applied_plans: List[mp.MigrationPlan] = self._migrate_versioned(
            ver, name, fake, dry_run, operator=operator
        )
        # repeatable migration
        self._migrate_repeatable(applied_plans, ver, name, dry_run, operator=operator)

    def _migrate_repeatable(
        self,
        applied_histories: List[model.MigrationHistory],
        ver: str,
        name: str,
        dry_run: bool,
        operator: str = "",
    ):
        if dry_run:
            # since it's dry_run, assume the target version is the latest version
            if ver is not None:
                applied_plans = self.mpm.must_get_plan_between(
                    0, mp.MigrationSignature(version=ver, name=name)
                )
            else:
                applied_plans = self.mpm.get_plans()
            to_execute_plans = self._get_to_execute_repeatable_plans(applied_plans)
            if len(to_execute_plans) > 0:
                logger.info("repeatable migration plans to execute:")
                self.print_dry_run(to_execute_plans, is_migrate=True)
            return

        to_execute_plans = self._get_to_execute_repeatable_plans(applied_histories)
        if len(to_execute_plans) == 0:
            logger.debug("no valid repeatable migration to execute")
            return

        dao = self.dao
        for plan in to_execute_plans:
            # try get the migration history
            with dao.session.begin():
                hist = dao.get_by_sig(plan.sig())
                if hist is None:
                    dao.add_one(plan, operator=operator)
                else:
                    # no need to check if state is SUCCESSFUL,
                    #   because it is repeatable migration
                    # just treat updating PROCESSING to PROCESSING
                    #   as retry the migration
                    dao.update_processing(plan, operator=operator)
                dao.commit()
            # execute the migration
            self.migrator.forward(plan, self.args)

            with dao.session.begin():
                dao.update_succ(plan, operator=operator)

    def _get_to_execute_repeatable_plans(
        self, applied_plans: List[mp.MigrationPlan]
    ) -> List[mp.MigrationPlan]:
        # get repeatable migration plans
        plans = self.mpm.get_repeatable_plans()
        # check if repeatable migration can be executed
        to_execute_plans: List[mp.MigrationPlan] = []
        for p in plans:
            if p.dependencies is not None and len(p.dependencies) > 0:
                dep_sig = p.dependencies[0]
                # check if dep_sig is in applied_histories
                if not any(ap.match(dep_sig) for ap in applied_plans):
                    logger.warning(
                        "repeatable migration %s is not executed because dependency %s"
                        " is not applied",
                        p,
                        dep_sig,
                    )
                    continue

            if p.ignore_after is not None:
                ignore_sig = p.ignore_after
                # check if ignore_sig is in applied_histories
                if any(ap.match(dep_sig) for ap in applied_plans):
                    logger.debug(
                        "repeatable migration %s is not executed because ignore_after"
                        " %s is applied",
                        p,
                        ignore_sig,
                    )
                    continue

            hist_dto = self.dao.get_by_sig_dto(p.sig())
            if hist_dto is not None and hist_dto.checksum == p.get_checksum():
                logger.debug(
                    "repeatable migration %s is not executed because it has been"
                    " executed",
                    p,
                )
                continue

            to_execute_plans.append(p)
        return to_execute_plans

    def rollback(self):
        self.read_migration_plans()
        self._check_integrity()
        ver = self.args.version.zfill(4)
        name = self.args.name if "name" in self.args else None
        fake = self.args.fake if "fake" in self.args else False
        dry_run = self.args.dry_run if "dry_run" in self.args else False
        operator = self.args.operator if "operator" in self.args else ""
        _, target_migration_plan_index = self.mpm.must_get_plan_by_signature(
            mp.MigrationSignature(ver, name)
        )

        dao = self.build_dao()
        with dao.session.begin():
            migration_histories = self._get_and_check_versioned_migration_histories()

            latest_migration_plan_index = len(migration_histories) - 1

            if target_migration_plan_index > latest_migration_plan_index:
                raise Exception("target migration plan is not applied yet")
            elif target_migration_plan_index == latest_migration_plan_index:
                return

            to_rollback_cfgs = self.mpm.must_get_plan_between(
                target_migration_plan_index + 1, latest_migration_plan_index
            )

            if len(to_rollback_cfgs) > 0:
                if dry_run:
                    logger.info("migration plans to rollback:")
                    self.print_dry_run(to_rollback_cfgs, is_migrate=False)
                    return

                dao.update_rollback(to_rollback_cfgs[-1], operator=operator, fake=fake)
                dao.commit()

        while len(to_rollback_cfgs) > 0:
            # rollback operation
            if not fake:
                self.migrator.backward(to_rollback_cfgs[-1], self.args)

            with dao.session.begin():
                latest_hist = dao.get_latest_versioned()
                if latest_hist is None:
                    raise Exception("unexpected migration history, latest_hist is None")
                if not latest_hist.can_match(
                    to_rollback_cfgs[-1].version,
                    to_rollback_cfgs[-1].name,
                    to_rollback_cfgs[-1].get_checksum(),
                ):
                    raise Exception(
                        f"unexpected migration history, ver={latest_hist.ver},"
                        f" name={latest_hist.name}"
                    )
                if latest_hist.state != model.MigrationState.ROLLBACKING:
                    raise Exception(
                        f"unexpected migration history state, ver={latest_hist.ver},"
                        f" name={latest_hist.name}, state={latest_hist.state}"
                    )
                dao.delete(to_rollback_cfgs[-1], operator=operator, fake=fake)
                to_rollback_cfgs = to_rollback_cfgs[:-1]
                if len(to_rollback_cfgs) > 0:
                    dao.update_rollback(
                        to_rollback_cfgs[-1], operator=operator, fake=fake
                    )
                dao.commit()

    def _clear(self, schema: str):
        dao = self.build_dao()
        with dao.session.begin():
            rows = dao.session.execute(
                text(
                    "select table_name from information_schema.tables where"
                    f" TABLE_SCHEMA = '{schema}';"
                )
            ).all()
            for [table_name] in rows:
                dao.session.execute(text(f"drop table {table_name};"))
            dao.commit()

    def read_migration_plans(self) -> mp.MigrationPlanManager:
        self.mpm = mp.MigrationPlanManager()
        return self.mpm

    def parse_migration_plans_to_map(
        self, plans: List[mp.MigrationPlan]
    ) -> Dict[str, Dict[str, mp.MigrationPlan]]:
        plan_map = collections.defaultdict(
            lambda: collections.defaultdict(mp.MigrationPlan)
        )
        for p in plans:
            plan_map[p.version][p.name] = p
        return plan_map

    def clean_cwd(self):
        shutil.rmtree(cli_env.MIGRATION_CWD, ignore_errors=True)

    def add_environment(self):
        call_skeema(
            [
                "add-environment",
                self.args.environment,
                "--host",
                self.args.host,
                "--port",
                str(self.args.port),
                "--user",
                self.args.user,
                "-d",
                cli_env.SCHEMA_DIR,
                "--ignore-table",
                cli_env.TABLE_MIGRATION_HISTORY,
            ]
        )

    def _init_migration_plan_dir(self):
        os.makedirs(
            os.path.join(cli_env.MIGRATION_CWD, cli_env.MIGRATION_PLAN_DIR),
            exist_ok=False,
        )

    def _init_schema_dir(self):
        # init schema dir
        call_skeema(
            [
                "init",
                "--host",
                self.args.host,
                "--port",
                str(self.args.port),
                "--user",
                self.args.user,
                "--schema",
                self.args.schema,
                "-d",
                cli_env.SCHEMA_DIR,
                "--ignore-table",
                cli_env.TABLE_MIGRATION_HISTORY,
            ]
        )
        os.link(
            os.path.join(cli_env.MIGRATION_CWD, cli_env.SCHEMA_DIR, ".skeema"),
            os.path.join(cli_env.MIGRATION_CWD, cli_env.ENV_INI_FILE),
        )

    def _init_schema_store_dir(self):
        os.makedirs(
            os.path.join(cli_env.MIGRATION_CWD, cli_env.SCHEMA_STORE_DIR),
            exist_ok=False,
        )
        hex_list = [format(i, "02x") for i in range(256)]
        for hex in hex_list:
            hex_dir_path = os.path.join(
                cli_env.MIGRATION_CWD, cli_env.SCHEMA_STORE_DIR, hex
            )
            os.makedirs(
                hex_dir_path,
                exist_ok=False,
            )
            with open(os.path.join(hex_dir_path, ".gitkeep"), "w") as f:
                f.write("")

    def _init_file_existence_check(self):
        check_file_existence(
            [
                os.path.join(cli_env.MIGRATION_CWD, cli_env.SCHEMA_DIR),
                os.path.join(cli_env.MIGRATION_CWD, cli_env.MIGRATION_PLAN_DIR),
                os.path.join(cli_env.MIGRATION_CWD, cli_env.DATA_DIR),
                os.path.join(cli_env.MIGRATION_CWD, cli_env.SCHEMA_STORE_DIR),
                os.path.join(cli_env.MIGRATION_CWD, cli_env.ENV_INI_FILE),
                os.path.join(cli_env.MIGRATION_CWD, ".gitignore"),
                os.path.join(cli_env.MIGRATION_CWD, "pre-commit"),
                os.path.join(cli_env.MIGRATION_CWD, "package.json"),
                os.path.join(cli_env.MIGRATION_CWD, "tsconfig.json"),
                os.path.join(cli_env.MIGRATION_CWD, ".env"),
            ]
        )

    def init(self):
        author = self.args.author if "author" in self.args else ""
        self._init_file_existence_check()
        self._init_migration_plan_dir()
        self._init_schema_dir()
        self._init_schema_store_dir()

        # move schema files to schema store
        sql_files, index_sha1, index_content = self.read_sql_files()
        self.write_schema_store(index_sha1, index_content)
        for f in sql_files:
            self.write_schema_store(f.sha1, f.content)

        # init first migration plan
        init_plan = mp.MigrationPlan(
            version=mp.InitialMigrationSignature.version,
            name=mp.InitialMigrationSignature.name,
            author=author,
            type=mp.Type.SCHEMA,
            change=mp.Change(forward=mp.SchemaForward(id=index_sha1), backward=None),
            dependencies=[],
        )
        init_plan.save()

        # make data dir
        os.makedirs(os.path.join(cli_env.MIGRATION_CWD, cli_env.DATA_DIR))

        # create gitignore
        with open(os.path.join(cli_env.MIGRATION_CWD, ".gitignore"), "w") as f:
            f.write(cli_env.SAMPLE_GIT_IGNORE)

        # create pre-commit hook
        with open(os.path.join(cli_env.MIGRATION_CWD, "pre-commit"), "w") as f:
            f.write(cli_env.SAMPLE_PRE_COMMIT)

        # create dot env file
        dot_env_file_path = os.path.join(cli_env.MIGRATION_CWD, ".env")
        with open(dot_env_file_path, "w") as f:
            f.write(cli_env.SAMPLE_DOT_ENV % cli_env.MYSQL_PWD)
            logger.info("MYSQL_WD is saved in .env file, path=%s", dot_env_file_path)

        # create package.json
        with open(os.path.join(cli_env.MIGRATION_CWD, "package.json"), "w") as f:
            f.write(cli_env.SAMPLE_PCKAGE_JSON)

        # create tsconfig.json
        with open(os.path.join(cli_env.MIGRATION_CWD, "tsconfig.json"), "w") as f:
            f.write(cli_env.SAMPLE_TSCONFIG_JSON)

    def read_sql_files(self) -> Tuple[List[mp.SQLFile], str, str]:
        """
        read sql files from schema dir, and return the index sha1 and content
        """
        sql_files: List[mp.SQLFile] = []
        for file in os.listdir(os.path.join(cli_env.MIGRATION_CWD, cli_env.SCHEMA_DIR)):
            if file.endswith(".sql"):
                with open(
                    os.path.join(cli_env.MIGRATION_CWD, cli_env.SCHEMA_DIR, file)
                ) as f:
                    content = f.read()
                    sha1 = self.sha1_encode(content)
                    sql_files.append(mp.SQLFile(file, content, sha1))
        sql_files.sort(key=lambda x: x.sha1)
        index_sha1 = self.sha1_encode([sql_file.sha1 for sql_file in sql_files])
        index_content = "\n".join([f"{f.sha1}:{f.name}" for f in sql_files])
        return sql_files, index_sha1, index_content

    def make_repeatable_migration(self) -> str:
        name = self.args.name
        author = self.args.author if "author" in self.args else ""
        data_change_type = self.args.type
        if not mp.DataChangeType.is_valid(data_change_type):
            raise Exception(f"invalid type {data_change_type}")
        self.read_migration_plans()
        if self.mpm.count() == 0:
            raise Exception("no migration plan found, run migration init first")
        next_plan = mp.MigrationPlan(
            version=mp.RepeatableVersion,
            name=name,
            author=author,
            type=mp.Type.REPEATABLE,
            change=mp.Change(
                forward=mp.DataForward(type=data_change_type),
                backward=None,
            ),
            dependencies=[],
            ignore_after=None,
        )

        match data_change_type:
            case mp.DataChangeType.SQL:
                next_plan.change.forward.sql = (
                    "INSERT INTO `testtable` (`id`, `name`) VALUES (1, 'foo.bar') ON"
                    " DUPLICATE KEY UPDATE `name` = 'foo.bar';"
                )
            case mp.DataChangeType.SQL_FILE:
                next_plan.change.forward.file = "your_sql_file.sql"
            case mp.DataChangeType.PYTHON:
                next_plan.change.forward.file = "your_python_file.py"
                logger.info("Sample python file:\n%s", cli_env.SAMPLE_PYTHON_FILE)
            case mp.DataChangeType.SHELL:
                next_plan.change.forward.file = "your_shell_file.sh"
                logger.info("Sample shell file:\n%s", cli_env.SAMPLE_SHELL_FILE)
            case mp.DataChangeType.TYPESCRIPT:
                next_plan.change.forward.file = "your_typescript_file.ts"
                logger.info("Sample typescript file:\n%s", cli_env.SAMPLE_MIGRATION_TS)

        return next_plan.save()

    def make_data_migration(self) -> str:
        name = self.args.name
        author = self.args.author if "author" in self.args else ""
        data_change_type = self.args.type
        if not mp.DataChangeType.is_valid(data_change_type):
            raise Exception(f"invalid type {data_change_type}")
        self.read_migration_plans()
        if self.mpm.count() == 0:
            raise Exception("no migration plan found, run migration init first")
        latest_plan = self.mpm.get_latest_plan()
        next_plan = mp.MigrationPlan(
            version=self.bump_version(latest_plan.version),
            name=name,
            author=author,
            type=mp.Type.DATA,
            change=mp.Change(
                forward=mp.DataForward(type=data_change_type),
                backward=None,
            ),
            dependencies=[
                mp.MigrationSignature(
                    version=latest_plan.version, name=latest_plan.name
                )
            ],
        )

        match data_change_type:
            case mp.DataChangeType.SQL:
                next_plan.change.forward.sql = (
                    "INSERT INTO `testtable` (`id`, `name`) VALUES (1, 'foo.bar');"
                )
            case mp.DataChangeType.SQL_FILE:
                next_plan.change.forward.file = "your_sql_file.sql"
            case mp.DataChangeType.PYTHON:
                next_plan.change.forward.file = "your_python_file.py"
                logger.info("Sample python file:\n%s", cli_env.SAMPLE_PYTHON_FILE)
            case mp.DataChangeType.SHELL:
                next_plan.change.forward.file = "your_shell_file.sh"
                logger.info("Sample shell file:\n%s", cli_env.SAMPLE_SHELL_FILE)
            case mp.DataChangeType.TYPESCRIPT:
                next_plan.change.forward.file = "your_typescript_file.ts"
                logger.info("Sample typescript file:\n%s", cli_env.SAMPLE_MIGRATION_TS)

        return next_plan.save()

    def bump_version(self, version: str):
        next_version = int(version) + 1
        return str(next_version).zfill(4)

    def make_schema_migration(self) -> str:
        name = self.args.name
        author = self.args.author if "author" in self.args else ""
        self.read_migration_plans()
        if self.mpm.count() == 0:
            raise Exception("no migration plan found, run migration init first")
        latest_plan = self.mpm.get_latest_plan()
        latest_schema_plan = self.mpm.get_latest_plan(mp.Type.SCHEMA)

        latest_schema_index_sha1 = latest_schema_plan.change.forward.id
        sql_files, index_sha1, index_content = self.read_sql_files()
        if latest_schema_index_sha1 == index_sha1:
            logger.info("no schema change")
            return
        self.write_schema_store(index_sha1, index_content)
        for f in sql_files:
            self.write_schema_store(f.sha1, f.content)
        new_plan = mp.MigrationPlan(
            version=self.bump_version(latest_plan.version),
            name=name,
            author=author,
            type=mp.Type.SCHEMA,
            change=mp.Change(
                forward=mp.SchemaForward(id=index_sha1),
                backward=mp.SchemaBackward(id=latest_schema_index_sha1),
            ),
            dependencies=[
                mp.MigrationSignature(
                    version=latest_plan.version, name=latest_plan.name
                )
            ],
        )
        return new_plan.save()

    def write_schema_store(self, sha1: str, content: str):
        folder = os.path.join(cli_env.MIGRATION_CWD, cli_env.SCHEMA_STORE_DIR, sha1[:2])
        filename = sha1[2:]
        # if file exist, return directly, otherwise write file
        filepath = os.path.join(folder, filename)
        logger.debug("Wrote schema store file to %s", filepath)
        if os.path.exists(filepath):
            return
        with open(filepath, "w") as f:
            f.write(content)

    def sha1_encode(self, str_list: List[str]):
        return helper.sha1_encode(str_list=str_list)

    def skeema(self, raw_args: List[str], cwd: str = cli_env.MIGRATION_CWD):
        # https://stackoverflow.com/questions/39872088/executing-interactive-shell-script-in-python
        return call_skeema(raw_args, cwd)

    def _print_info_as_table(
        self, prompt: str, output: List[List[str]], headers: List[str]
    ):
        if len(output) == 0:
            return
        logger.info(
            prompt
            + "\n"
            + tabulate(
                output,
                headers=headers,
                tablefmt="orgtbl",
            )
        )

    def info(self) -> Tuple[bool, int]:
        """
        return (is_migration_history_consistent, len_applied)
        """
        self.read_migration_plans()
        dao = self.build_dao()
        hist_list = dao.get_all_dto()

        output = [
            [
                hist.ver,
                hist.name,
                hist.type,
                hist.state.name,
                hist.created,
                hist.updated,
            ]
            for hist in hist_list
        ]
        self._print_info_as_table(
            "Applied migration history:",
            output,
            ["ver", "name", "type", "state", "created", "updated"],
        )

        return True, len(hist_list)

    # TODO get verbose info
    def versioned_info(self) -> Tuple[bool, int, int, int]:
        self.read_migration_plans()
        dao = self.build_dao()
        hist_list = dao.get_all_versioned_dto()
        is_migration_history_consistent = True
        output: List[List[str]] = []
        min_len = min(len(hist_list), self.mpm.count())
        idx = 0
        for idx in range(min_len):
            hist = hist_list[idx]
            plan = self.mpm.get_plan_by_index(idx)
            if not hist.can_match(plan.version, plan.name, plan.get_checksum()):
                is_migration_history_consistent = False
                break
            output.append(
                [
                    hist.ver,
                    hist.name,
                    hist.type,
                    hist.state.name,
                    hist.created,
                    hist.updated,
                ]
            )
        # print applied migration history
        self._print_info_as_table(
            "Applied migration history:",
            output,
            ["ver", "name", "type", "state", "created", "updated"],
        )
        len_applied = len(output)

        if is_migration_history_consistent:
            hists_to_print = hist_list[idx + 1 :]
            plans_to_print = self.mpm.get_plans()[idx + 1 :]
            if len(hists_to_print) > 0 or len(plans_to_print) > 0:
                is_migration_history_consistent = False
        else:
            hists_to_print = hist_list[idx:]
            plans_to_print = self.mpm.get_plans()[idx:]

        # print unexpected migration history
        output = [
            [
                hist.ver,
                hist.name,
                hist.type,
                hist.state.name,
                hist.created,
                hist.updated,
            ]
            for hist in hists_to_print
        ]
        self._print_info_as_table(
            "Unexpected migration history:",
            output,
            ["ver", "name", "type", "state", "created", "updated"],
        )
        len_unexpected = len(output)

        # print unapplied migration plans
        output = [
            [
                p.version,
                p.name,
                str(p.type),
            ]
            for p in plans_to_print
        ]
        self._print_info_as_table(
            "Unapplied migration plans:", output, ["ver", "name", "type"]
        )
        len_unapplied = len(output)
        return (
            is_migration_history_consistent,
            len_applied,
            len_unexpected,
            len_unapplied,
        )

    def pull(self):
        env_or_version = self.args.env_or_version
        self.read_migration_plans()
        argtype = self._get_diff_type(env_or_version)
        if argtype == mp.DiffItemType.ENVIRONMENT:
            self.skeema(["pull", env_or_version])
            return
        if argtype == mp.DiffItemType.VERSION:
            schema_dir_path = os.path.join(cli_env.MIGRATION_CWD, cli_env.SCHEMA_DIR)
            schema_dir_files = files_under_dir(schema_dir_path, ".sql")

            with tempfile.TemporaryDirectory() as temp_dir:
                self.dump_schema(env_or_version, argtype, temp_dir, mkdir=False)
                ver_files = files_under_dir(temp_dir, ".sql")

                # move file under temp_dir to schema dir
                for filename, filepath in ver_files.items():
                    shutil.move(
                        filepath,
                        os.path.join(schema_dir_path, filename),
                    )
                    logger.info("Updated %s", os.path.join(schema_dir_path, filename))

                # delete files in schema dir that are not in temp_dir
                to_delete_files = set(schema_dir_files.keys()) - set(ver_files.keys())
                for filename in to_delete_files:
                    os.remove(schema_dir_files[filename])
                    logger.info("Deleted %s", schema_dir_files[filename])

        else:
            raise Exception(
                f"invalid argument type, {env_or_version} is neither environment nor"
                " version"
            )

    def diff(self):
        left = self.args.left
        right = self.args.right
        if left == right:
            return
        self.read_migration_plans()
        left_type = self._get_diff_type(left)
        right_type = self._get_diff_type(right)

        with tempfile.TemporaryDirectory() as temp_dir:
            left_dump_dir_path = os.path.join(temp_dir, "left")
            right_dump_dir_path = os.path.join(temp_dir, "right")
            self.dump_schema(left, left_type, left_dump_dir_path)
            self.dump_schema(right, right_type, right_dump_dir_path)

            has_diff = False
            if not self.args.verbose:
                try:
                    subprocess.check_call(
                        shlex.split("diff --recursive --brief left right"),
                        cwd=temp_dir,
                    )
                except subprocess.CalledProcessError:
                    has_diff = True
            else:
                try:
                    subprocess.check_call(
                        shlex.split("diff --color -Nr -U4 left right"),
                        cwd=temp_dir,
                    )
                except subprocess.CalledProcessError:
                    has_diff = True

            if has_diff:
                raise Exception(f"difference found between {left} and {right}")

    def dump_schema(
        self,
        diff_arg: str,
        diff_type: mp.DiffItemType,
        dump_dir_path: str,
        mkdir: bool = True,
    ):
        if mkdir:
            os.makedirs(dump_dir_path, exist_ok=False)

        if diff_type == mp.DiffItemType.HEAD:
            original_path = os.path.join(cli_env.MIGRATION_CWD, cli_env.SCHEMA_DIR)
            for file in os.listdir(original_path):
                if file.endswith(".sql"):
                    shutil.copy(
                        os.path.join(original_path, file),
                        os.path.join(dump_dir_path, file),
                    )
            return
        if diff_type == mp.DiffItemType.VERSION:
            if diff_arg.isdigit():
                diff_arg = diff_arg.zfill(4)
                target_plan, _ = self.mpm.must_get_plan_by_signature(
                    mp.MigrationSignature(diff_arg, None)
                )
            else:
                split = diff_arg.split("_")
                ver = split[0]
                name = "_".join(split[1:])
                target_plan, _ = self.mpm.must_get_plan_by_signature(
                    mp.MigrationSignature(ver, name)
                )

            if target_plan.type != mp.Type.SCHEMA:
                raise Exception(f"not schema migration plan, version={diff_arg}")
            index_sha1 = target_plan.change.forward.id
            self.copy_schema_by_index(index_sha1, dump_dir_path)
            return
        if diff_type == mp.DiffItemType.ENVIRONMENT:
            env_ini = parse_env_ini()  # env.ini is just a symlink to .skeema
            env = diff_arg
            if not env_ini.has_section(env):
                raise Exception(f"environment not found, name={env}")
            skeema_file_path = os.path.join(
                cli_env.MIGRATION_CWD, cli_env.SCHEMA_DIR, ".skeema"
            )
            shutil.copy(skeema_file_path, dump_dir_path)
            call_skeema(["pull", env], cwd=dump_dir_path)
            os.remove(os.path.join(dump_dir_path, ".skeema"))
            return

    def _get_diff_type(self, name: str) -> mp.DiffItemType:
        if name == "HEAD":
            return mp.DiffItemType.HEAD
        if name.isdigit():
            return mp.DiffItemType.VERSION
        split = name.split("_")
        if len(split) > 1 and split[0].isdigit():
            return mp.DiffItemType.VERSION
        else:
            return mp.DiffItemType.ENVIRONMENT

    # TODO refactor to use this method
    def _schema_store_file_full_path(self, sha1: str) -> str:
        return os.path.join(
            cli_env.MIGRATION_CWD,
            cli_env.SCHEMA_STORE_DIR,
            sha1[:2],
            sha1[2:],
        )

    def read_schema_index(
        self, sha1: str, check_sha: bool = False
    ) -> List[Tuple[str, str]]:
        index_file = os.path.join(
            cli_env.MIGRATION_CWD, cli_env.SCHEMA_STORE_DIR, sha1[:2], sha1[2:]
        )
        with open(index_file, "r") as f:
            lines = f.readlines()
        if check_sha:
            actual_sha1 = self.sha1_encode([x.split(":")[0] for x in lines])
            if actual_sha1 != sha1:
                raise err.IntegrityError(
                    f"schema index sha1 not match, actual_sha1={actual_sha1},"
                    f" expected_sha1={sha1}"
                )
        return [
            (line.split(":")[0], line.split(":")[1].strip()) for line in lines
        ]  # sha1, filename

    def copy_schema_by_index(self, sha1: str, temp_dir: str):
        for sha1, sql_filename in self.read_schema_index(sha1):
            shutil.copy(
                os.path.join(
                    cli_env.MIGRATION_CWD,
                    cli_env.SCHEMA_STORE_DIR,
                    sha1[:2],
                    sha1[2:],
                ),  # sql_filepath
                os.path.join(temp_dir, sql_filename),
            )

    def clean_schema_store(self) -> List[str]:
        dry_run = self.args.dry_run if "dry_run" in self.args else False
        skip_integrity = (
            self.args.skip_integrity if "skip_integrity" in self.args else False
        )
        self.read_migration_plans()
        if not skip_integrity:
            self._check_integrity()
        return self._clean_schema_store(delete_unexpected=dry_run)

    def _clean_schema_store(self, delete_unexpected: bool) -> List[str]:
        schema_store_path = os.path.join(
            cli_env.MIGRATION_CWD, cli_env.SCHEMA_STORE_DIR
        )

        # get all valid paths in schema store
        schema_plans = self.mpm.get_plans_by_type(mp.Type.SCHEMA)
        valid_index_sha1s = set()
        valid_sql_sha1s = set()
        for plan in schema_plans:
            if plan.change.forward is not None:
                valid_index_sha1s.add(plan.change.forward.id)
            if plan.change.backward is not None:
                valid_index_sha1s.add(plan.change.backward.id)
        for index_sha1 in valid_index_sha1s:
            for sql_sha1, _ in self.read_schema_index(index_sha1):
                valid_sql_sha1s.add(sql_sha1)
        valid_paths = set()
        for sha1 in valid_index_sha1s.union(valid_sql_sha1s):
            valid_paths.add(
                os.path.join(
                    sha1[:2],
                    sha1[2:],
                )
            )

        # get all paths in schema store
        all_paths = set()
        for root, dirs, files in os.walk(schema_store_path):
            for file in files:
                if not file.endswith(".gitkeep"):
                    all_paths.add(
                        os.path.join(root, file).removeprefix(schema_store_path + "/")
                    )

        # log the unexpected paths
        # if not dry run delete those files
        unexpected_paths = all_paths - valid_paths
        for p in unexpected_paths:
            full_path = os.path.join(schema_store_path, p)
            if delete_unexpected:
                logger.warning("Unexpected file: %s", full_path)
            else:
                os.remove(full_path)
                logger.warning("Deleted %s", full_path)

        return list(unexpected_paths)

    # This method performs a basic check on the integrity of the migration plans.
    # It reads the migration plans and checks that:
    #   - For schema migrations, the index file and linked SQL file exist.
    #       If not in fast mode, it also checks that the SHA1 is correct.
    #   - For data migrations, check the sql is not empty or the file exist.
    # TODO: Implement advanced checks to verify the SQL syntax.
    def check_integrity(self):
        fast = self.args.fast if "fast" in self.args else False
        self.read_migration_plans()
        self._check_integrity(fast=fast)

    def _check_integrity(self, fast: bool = False):
        checked_schema_index_sha = set()
        for plan in self.mpm.get_plans():
            if plan.type == mp.Type.SCHEMA:
                self._check_schema_migration(
                    plan, fast=fast, checked_schema_index_sha=checked_schema_index_sha
                )
            elif plan.type == mp.Type.DATA:
                self._check_data_migration(plan)
            else:
                raise err.IntegrityError(f"unknown type, type={plan.type}")
        for plan in self.mpm.get_repeatable_plans():
            self._check_data_migration(plan)

    def _check_schema_migration(
        self,
        plan: mp.MigrationPlan,
        fast: bool = False,
        checked_schema_index_sha: Set[str] = None,
    ):
        if plan.change.forward is None:
            raise err.IntegrityError(f"forward is None, {plan}")

        index_sha1 = plan.change.forward.id
        self._check_schema_by_index(index_sha1, plan, check_sha=not fast)

        if plan.match(mp.InitialMigrationSignature):
            return

        if plan.change.backward is None:
            raise err.IntegrityError(f"backward is None, {plan}")
        index_sha1 = plan.change.backward.id
        if index_sha1 in checked_schema_index_sha:
            return
        self._check_schema_by_index(index_sha1, plan, check_sha=not fast)

    def _check_schema_by_index(
        self, index_sha1: str, plan: mp.MigrationPlan, check_sha: bool = True
    ):
        try:
            sql_files = self.read_schema_index(index_sha1, check_sha=check_sha)
        except FileNotFoundError:
            raise err.IntegrityError(
                f"index file not found, {plan}, missing file:"
                f" {self._schema_store_file_full_path(index_sha1)}"
            )
        # check sql file exist
        for sql_sha1, sql_filename in sql_files:
            sql_file_path = os.path.join(
                cli_env.MIGRATION_CWD,
                cli_env.SCHEMA_STORE_DIR,
                sql_sha1[:2],
                sql_sha1[2:],
            )
            if not os.path.exists(sql_file_path):
                raise err.IntegrityError(
                    f"sql file not found, {plan},"
                    f" id={sql_sha1}, original filename={sql_filename}"
                )
            if check_sha:
                with open(sql_file_path, "r") as f:
                    content = f.read()
                    actual_sha1 = self.sha1_encode([content])
                    if actual_sha1 != sql_sha1:
                        raise err.IntegrityError(
                            f"sql file SHA1 not match, {plan},"
                            f" original filename={sql_filename},"
                            f" expected_sha1={sql_sha1}, actual_sha1={actual_sha1},"
                            f" file={sql_file_path}"
                        )

    def _check_data_migration(self, plan: mp.MigrationPlan):
        if plan.match(mp.InitialMigrationSignature):
            raise err.IntegrityError(
                f"initial migration plan should not be data migration, {plan}"
            )

        if plan.change.forward is None:
            raise err.IntegrityError(f"forward is None, {plan}")

        def check_data_file(file: str):
            if file is None or file == "":
                raise err.IntegrityError(
                    f"data migration file is empty, file={file}, {plan}"
                )
            if not os.path.exists(
                os.path.join(cli_env.MIGRATION_CWD, cli_env.DATA_DIR, file)
            ):
                raise err.IntegrityError(
                    f"data migration file not found, file={file}, {plan}"
                )

        def check_forward_or_backward(
            change: Optional[mp.DataForward | mp.DataBackward],
        ):
            if change.type == mp.DataChangeType.SQL:
                if change.sql is None or change.sql == "":
                    raise err.IntegrityError(f"sql is empty, {plan}")

            if (
                change.type == mp.DataChangeType.SQL_FILE
                or change.type == mp.DataChangeType.PYTHON
                or change.type == mp.DataChangeType.SHELL
                or change.type == mp.DataChangeType.TYPESCRIPT
            ):
                check_data_file(change.file)

        check_forward_or_backward(plan.change.forward)

        if plan.change.backward is not None:
            check_forward_or_backward(plan.change.backward)
