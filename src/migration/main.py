import argparse
import logging
import os
import sys
from enum import StrEnum

from .env import log_env
from .lib import CLI

logger = logging.getLogger(__name__)


def add_mysql_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--host",
        required=False,
        default="127.0.0.1",
        help="MySQL host",
    )
    parser.add_argument(
        "-P",
        "--port",
        type=int,
        default=3306,
        help="MySQL port",
    )
    parser.add_argument(
        "-u",
        "--user",
        required=False,
        default="root",
        help="MySQL user",
    )


def parse_pull_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "env_or_version",
        help="available values: <version>, <version>_<name>, <environment>",
    )


def parse_check_args(parser: argparse.ArgumentParser):
    subparsers = parser.add_subparsers(
        title="subcommand", dest="subcommand", required=True
    )

    parser_integrity = subparsers.add_parser(
        Command.CHECK_INTEGRITY, help="check integrity"
    )
    parser_integrity.add_argument(
        "--fast",
        action="store_true",
        help="fast check",
    )
    parser_integrity.add_argument(
        "--debug",
        action="store_true",
        help="debug mode",
    )

    pass


def parse_diff_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "left",
        help=(
            "left version, available values: HEAD, <version>, <version>_<name>,"
            " <environment>"
        ),
    )
    parser.add_argument(
        "right",
        help=(
            "right version, available values: HEAD, <version>, <version>_<name>,"
            " <environment>"
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="verbose",
    )


def parse_info_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "environment",
        default="production",
        help="environment name",
    )


def parse_make_data_migration_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "name",
        help="migration plan name",
    )
    parser.add_argument(
        "type",
        help=(
            "available types:"
            f" {','.join(['sql', 'sql_file', 'python', 'shell', 'typescript'])}"
        ),
    )
    parser.add_argument(
        "--author",
        required=False,
        default="",
        help="author",
    )


def parse_make_schema_migration_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "name",
        help="migration plan name",
    )
    parser.add_argument(
        "--author",
        required=False,
        default="",
        help="author",
    )


def parse_fix_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "subcommand",
        choices=[Command.MIGRATE, Command.ROLLBACK],
        help="subcommand",
    )
    parser.add_argument(
        "environment",
        help="environment name",
    )
    parser.add_argument(
        "--fake",
        required=False,
        action="store_true",
        help="fake rollback without executing sql",
    )
    parser.add_argument(
        "-o",
        "--operator",
        required=False,
        default="",
        help="migration plan name",
    )


def parse_rollback_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "environment",
        help="environment name",
    )
    parser.add_argument(
        "-v",
        "--version",
        required=True,
        help="integer version",
    )
    parser.add_argument(
        "-n",
        "--name",
        required=False,
        help="migration plan name",
    )
    parser.add_argument(
        "--fake",
        required=False,
        action="store_true",
        help="fake rollback without executing sql",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="dry run",
    )
    parser.add_argument(
        "-o",
        "--operator",
        required=False,
        default="",
        help="migration plan name",
    )


def parse_migrate_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "environment",
        help="environment name",
    )
    parser.add_argument(
        "-v",
        "--version",
        required=False,
        help="integer version",
    )
    parser.add_argument(
        "-n",
        "--name",
        required=False,
        help="migration plan name",
    )
    parser.add_argument(
        "--fake",
        required=False,
        action="store_true",
        help="fake migrate without executing sql",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="dry run",
    )
    parser.add_argument(
        "-o",
        "--operator",
        required=False,
        default="",
        help="migration plan name",
    )


def parse_add_env_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "environment",
        help="environment name",
    )
    add_mysql_args(parser)


def parse_skeema_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "extra_args",
        nargs="*",
        help="Command reference https://www.skeema.io/docs/commands/",
    )


def parse_init_args(parser: argparse.ArgumentParser):
    add_mysql_args(parser)
    parser.add_argument(
        "-s",
        "--schema",
        required=True,
        help="Skeema schema",
    )
    parser.add_argument(
        "--author",
        required=False,
        default="",
        help="author",
    )


class Command(StrEnum):
    SKEEMA = "skeema"

    INIT = "init"

    ADD_ENV = "add-env"
    ALIAS_ADD_ENV = "e"

    MIGRATE = "migrate"
    ALIAS_MIGRATE = "m"

    ROLLBACK = "rollback"
    ALIAS_ROLLBACK = "r"

    MAKE_SCHEMA = "make-schema"
    ALIAS_MAKE_SCHEMA = "ms"

    MAKE_DATA = "make-data"
    ALIAS_MAKE_DATA = "md"

    INFO = "info"

    DIFF = "diff"

    FIX = "fix"

    PULL = "pull"

    CHECK = "check"
    CHECK_INTEGRITY = "integrity"


def parse_args(args):
    parent_parser = argparse.ArgumentParser(
        description=(
            "Schema-data-migration is a database migration tool that supports MySQL and"
            " MariaDB.\nIt can manage both schema and data migration."
        )
    )
    subparsers = parent_parser.add_subparsers(
        title="command", dest="command", required=True
    )

    # skeema
    parser_skeema = subparsers.add_parser(Command.SKEEMA, help="call skeema")
    parse_skeema_args(parser_skeema)

    # init
    parser_init = subparsers.add_parser(Command.INIT, help="initialize  project")
    parse_init_args(parser_init)

    # add env
    parser_add_env = subparsers.add_parser(
        Command.ADD_ENV, help="add environment", aliases=[Command.ALIAS_ADD_ENV]
    )
    parse_add_env_args(parser_add_env)

    # migrate
    parser_migrate = subparsers.add_parser(
        Command.MIGRATE, help="migrate schema and data", aliases=[Command.ALIAS_MIGRATE]
    )
    parse_migrate_args(parser_migrate)

    # rollback
    parser_migrate = subparsers.add_parser(
        Command.ROLLBACK,
        help="rollback schema and data",
        aliases=[Command.ALIAS_ROLLBACK],
    )
    parse_rollback_args(parser_migrate)

    # fix migrate/rollback
    parser_fix = subparsers.add_parser(Command.FIX, help="fix migration history")
    parse_fix_args(parser_fix)

    # make schema
    parser_make_schema_migration = subparsers.add_parser(
        Command.MAKE_SCHEMA,
        help="generate schema migration plan",
        aliases=[Command.ALIAS_MAKE_SCHEMA],
    )
    parse_make_schema_migration_args(parser_make_schema_migration)

    # make data
    parser_make_data_migration = subparsers.add_parser(
        Command.MAKE_DATA,
        help="generate data migration plan",
        aliases=[Command.ALIAS_MAKE_DATA],
    )
    parse_make_data_migration_args(parser_make_data_migration)

    # info
    parser_info = subparsers.add_parser(
        Command.INFO, help="show migration history information in the environment"
    )
    parse_info_args(parser_info)

    # diff
    parser_diff = subparsers.add_parser(
        Command.DIFF,
        help=(
            "show the schema difference between schema models, versions, or"
            " environments"
        ),
    )
    parse_diff_args(parser_diff)

    # check
    parser_check = subparsers.add_parser(
        Command.CHECK, help="check the integrity of the migration plan"
    )
    parse_check_args(parser_check)

    # pull
    parser_pull = subparsers.add_parser(
        Command.PULL, help="pull schema from remote or migration plan"
    )
    parse_pull_args(parser_pull)

    return parent_parser.parse_args(args)


def main(raw_args):
    args = parse_args(raw_args)
    cli = CLI(args)

    match args.command:
        case Command.SKEEMA:
            cli.skeema(raw_args[1:])
        case Command.INIT:
            cli.init()
        case Command.ADD_ENV | Command.ALIAS_ADD_ENV:
            cli.add_environment()
        case Command.MIGRATE | Command.ALIAS_MIGRATE:
            cli.migrate()
        case Command.ROLLBACK | Command.ALIAS_ROLLBACK:
            cli.rollback()
        case Command.FIX:
            match args.subcommand:
                case Command.MIGRATE:
                    cli.fix_migrate()
                case Command.ROLLBACK:
                    cli.fix_rollback()
        case Command.MAKE_SCHEMA | Command.ALIAS_MAKE_SCHEMA:
            cli.make_schema_migration()
        case Command.MAKE_DATA | Command.ALIAS_MAKE_DATA:
            cli.make_data_migration()
        case Command.INFO:
            cli.info()
        case Command.DIFF:
            cli.diff()
        case Command.PULL:
            cli.pull()
        case Command.CHECK:
            match args.subcommand:
                case Command.CHECK_INTEGRITY:
                    cli.check_integrity()


def run():
    try:
        main(sys.argv[1:])
    except Exception as e:
        if log_env.LOG_LEVEL == log_env.LEVEL_DEBUG:
            raise e
        else:
            logger.error(e)
            os._exit(1)


if __name__ == "__main__":
    run()
