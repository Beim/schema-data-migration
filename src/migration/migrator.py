import importlib.util
import logging
import os
import shlex
import shutil
import subprocess
import tempfile
from argparse import Namespace
from typing import Optional

from sqlalchemy import text

from . import consts, err, helper
from . import migration_plan as mp
from .env import cli_env

logger = logging.getLogger(__name__)


class Migrator:
    def check_condition(
        self,
        condition: mp.ConditionCheck,
        args: Namespace,
        checksum_match: Optional[bool] = None,
    ) -> bool:
        match condition.type:
            case mp.DataChangeType.SQL:
                return self.check_condition_sql(condition.sql, condition.expected, args)
            case mp.DataChangeType.SQL_FILE:
                return self.check_condition_sql_file(
                    condition.file, condition.expected, args
                )
            case mp.DataChangeType.PYTHON:
                return self.check_condition_python(
                    condition.file,
                    condition.expected,
                    args,
                    checksum_match=checksum_match,
                )
            case mp.DataChangeType.SHELL:
                return self.check_condition_shell(
                    condition.file,
                    condition.expected,
                    args,
                    checksum_match=checksum_match,
                )
            case mp.DataChangeType.TYPESCRIPT:
                return self.check_condition_typescript(
                    condition.file,
                    condition.expected,
                    args,
                    checksum_match=checksum_match,
                )

    def forward(self, migration_plan: mp.MigrationPlan, args: Namespace):
        logger.info(f"Executing {migration_plan}")
        forward = migration_plan.change.forward

        # precheck
        if forward.precheck is not None:
            if not self.check_condition(
                forward.precheck,
                args,
                checksum_match=migration_plan.get_checksum_match(),
            ):
                raise err.ConditionCheckFailedError(
                    f"precheck failed for {migration_plan}"
                )

        if migration_plan.type == mp.Type.SCHEMA:
            sha1 = forward.id
            self.move_schema_to(sha1, args)
        if migration_plan.type in [mp.Type.DATA, mp.Type.REPEATABLE]:
            if forward.type == mp.DataChangeType.SQL:
                self.migrate_data_sql(forward.sql, args)
            if forward.type == mp.DataChangeType.SQL_FILE:
                self.migrate_data_sql_file(forward.file, args)
            if forward.type == mp.DataChangeType.PYTHON:
                self.migrate_data_python(forward.file, args)
            if forward.type == mp.DataChangeType.SHELL:
                self.migrate_data_shell(forward.file, args)
            if forward.type == mp.DataChangeType.TYPESCRIPT:
                self.migrate_data_typescript(forward.file, args)

        # postcheck
        if forward.postcheck is not None:
            if not self.check_condition(forward.postcheck, args):
                raise err.ConditionCheckFailedError(
                    f"postcheck failed for {migration_plan}"
                )

    def backward(self, migration_plan: mp.MigrationPlan, args: Namespace):
        logger.info(f"Rollbacking {migration_plan}")
        backward = migration_plan.change.backward
        if backward is None:
            logger.info(f"No backward change for {migration_plan}")
            return

        # precheck
        if backward.precheck is not None:
            if not self.check_condition(backward.precheck, args):
                raise err.ConditionCheckFailedError(
                    f"precheck failed for {migration_plan}"
                )

        if migration_plan.type == mp.Type.SCHEMA:
            sha1 = backward.id
            self.move_schema_to(sha1, args, allow_unsafe=True)
        if migration_plan.type in [mp.Type.DATA, mp.Type.REPEATABLE]:
            if backward.type == mp.DataChangeType.SQL:
                self.migrate_data_sql(backward.sql, args)
            if backward.type == mp.DataChangeType.SQL_FILE:
                self.migrate_data_sql_file(backward.file, args)
            if backward.type == mp.DataChangeType.PYTHON:
                self.migrate_data_python(backward.file, args)
            if backward.type == mp.DataChangeType.SHELL:
                self.migrate_data_shell(backward.file, args)
            if backward.type == mp.DataChangeType.TYPESCRIPT:
                self.migrate_data_typescript(backward.file, args)

        # postcheck
        if backward.postcheck is not None:
            if not self.check_condition(backward.postcheck, args):
                raise err.ConditionCheckFailedError(
                    f"postcheck failed for {migration_plan}"
                )

    def check_condition_shell(
        self,
        shell_file: str,
        expected: int,
        args: Namespace,
        checksum_match: Optional[bool] = None,
    ):
        try:
            self.migrate_data_shell(
                shell_file, args, expected, checksum_match=checksum_match
            )
        except Exception:
            return False
        return True

    def migrate_data_shell(
        self,
        shell_file: str,
        args: Namespace,
        expected: Optional[int] = None,
        checksum_match: Optional[bool] = None,
    ):
        shell_file_path = os.path.join(
            cli_env.MIGRATION_CWD, cli_env.DATA_DIR, shell_file
        )
        section = helper.get_env_ini_section(args.environment)
        cmd = f"sh {shell_file_path}"
        env = helper.get_env_with_update(
            {
                "MYSQL_PWD": cli_env.MYSQL_PWD,
                "HOST": section["host"],
                "PORT": section["port"],
                "USER": section["user"],
                "SCHEMA": section["schema"],
                consts.ENV_SDM_DATA_DIR: cli_env.SDM_DATA_DIR,
            }
        )
        if expected is not None:
            env[consts.ENV_SDM_EXPECTED] = str(expected)
        if checksum_match is not None:
            env[consts.ENV_SDM_CHECKSUM_MATCH] = "1" if checksum_match else "0"
        subprocess.check_call(
            shlex.split(cmd),
            cwd=cli_env.MIGRATION_CWD,
            env=env,
        )

    def check_condition_typescript(
        self,
        ts_file: str,
        expected: int,
        args: Namespace,
        checksum_match: Optional[bool] = None,
    ):
        try:
            self.migrate_data_typescript(
                ts_file, args, expected, checksum_match=checksum_match
            )
        except Exception:
            return False
        return True

    def migrate_data_typescript(
        self,
        ts_file: str,
        args: Namespace,
        expected: Optional[int] = None,
        checksum_match: Optional[bool] = None,
    ) -> int:
        section = helper.get_env_ini_section(args.environment)
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
            env = helper.get_env_with_update(
                {
                    "MYSQL_PWD": cli_env.MYSQL_PWD,
                    "HOST": section["host"],
                    "PORT": section["port"],
                    "USER": section["user"],
                    "SCHEMA": section["schema"],
                    consts.ENV_SDM_DATA_DIR: cli_env.SDM_DATA_DIR,
                }
            )
            if expected is not None:
                env[consts.ENV_SDM_EXPECTED] = str(expected)
            if checksum_match is not None:
                env[consts.ENV_SDM_CHECKSUM_MATCH] = "1" if checksum_match else "0"

            # run js file
            subprocess.check_call(
                [cli_env.NODE_CMD_PATH, "src/index.js"],
                cwd=temp_dir,
                env=env,
            )
            return 0

    def check_condition_python(
        self,
        python_file: str,
        expected: int,
        args: Namespace,
        checksum_match: Optional[bool] = None,
    ):
        result = self.migrate_data_python(
            python_file, args, checksum_match=checksum_match
        )
        return result == expected

    def migrate_data_python(
        self, python_file: str, args: Namespace, checksum_match: Optional[bool] = None
    ) -> int:
        python_file_path = os.path.join(
            cli_env.MIGRATION_CWD, cli_env.DATA_DIR, python_file
        )
        spec = importlib.util.spec_from_file_location("run_python", python_file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        session = helper.build_session_from_env(
            args.environment, echo=cli_env.ALLOW_ECHO_SQL
        )
        obj = {
            consts.ENV_SDM_DATA_DIR: cli_env.SDM_DATA_DIR,
        }
        if checksum_match is not None:
            obj[consts.ENV_SDM_CHECKSUM_MATCH] = "1" if checksum_match else "0"
        return module.run(session, args=obj)

    def migrate_data_sql_file(self, sql_file: str, args: Namespace):
        with open(os.path.join(cli_env.MIGRATION_CWD, cli_env.DATA_DIR, sql_file)) as f:
            sql = f.read()
        self.migrate_data_sql(sql, args)

    def migrate_data_sql(self, sql: str, args: Namespace):
        session = helper.build_session_from_env(
            args.environment, echo=cli_env.ALLOW_ECHO_SQL
        )
        with session.begin():
            result = session.execute(text(sql))
            logger.info(
                f"Migrated SQL={helper.truncate_str(sql, max_len=200)},"
                f" result.rowcount={result.rowcount}"
            )

    def check_condition_sql_file(
        self, sql_file: str, expected: int, args: Namespace
    ) -> bool:
        with open(os.path.join(cli_env.MIGRATION_CWD, cli_env.DATA_DIR, sql_file)) as f:
            sql = f.read()
        return self.check_condition_sql(sql, expected, args)

    def check_condition_sql(self, sql: str, expected: int, args: Namespace) -> bool:
        session = helper.build_session_from_env(
            args.environment, echo=cli_env.ALLOW_ECHO_SQL
        )
        with session.begin():
            result = session.execute(text(sql)).one_or_none()
            logger.info(
                f"Check condition, SQL={helper.truncate_str(sql, max_len=200)},"
                f" result={result}"
            )
            return result[0] == expected

    def move_schema_to(self, sha1: str, args: Namespace, allow_unsafe: bool = False):
        index_file = helper.sha1_to_path(sha1)
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
                sql_filepath = helper.sha1_to_path(sha1)
                shutil.copy(
                    sql_filepath,
                    os.path.join(temp_dir, cli_env.SCHEMA_DIR, sql_filename.strip()),
                )
            skeema_args = [
                "push",
                args.environment,
            ]
            if cli_env.ALLOW_UNSAFE or allow_unsafe:
                skeema_args.extend(["--allow-unsafe"])
            helper.call_skeema(raw_args=skeema_args, cwd=temp_dir)
        pass
