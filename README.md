# sdm (schema data migration)

[![build status](https://img.shields.io/github/actions/workflow/status/beim/schema-data-migration/unittest.yml?branch=main)](https://github.com/Beim/schema-data-migration/actions)
[![Coverage Status](https://coveralls.io/repos/github/Beim/schema-data-migration/badge.svg?main)](https://coveralls.io/github/Beim/schema-data-migration?branch=main)

`sdm` is a open-source tool for managing database migrations in MySQL and MariaDB. With `sdm`, you can easily manage both schema and data migration.

Schema migration is powered by [skeema](https://www.skeema.io/), which uses a [declarative approach](https://www.skeema.io/blog/2019/01/18/declarative/) to schema management: the repository reflects a desired end-state of table definitions, and the tool figures out how to convert any database into this state.

Data migration is supported by [SQLAlchemy](https://docs.sqlalchemy.org/en/20/), [TypeORM](https://typeorm.io/) and can handle SQL, Python, Typescript, and Shell scripts.

## Quickstart

### Docker

You can run `sdm` through docker:

```bash
docker run -u $(id -u):$(id -g) \
    -v $(pwd):/workspace \
    -e MYSQL_PWD="your_password" \
    -it --rm beim/schema-data-migration:latest \
    sdm -h
```

### Build from source

You can install `sdm` from source, you need to have the following software installed on your system:

- [skeema](https://www.skeema.io/cli/download/)
- Python (v3.11 or higher)
- pip (v23.1.2 or higher)
- Node.js (v18.17.0 or higher, optional)
- npm (v9.6.7 or higher, optional)


Then you can clone this repository and install `sdm`:

```bash
git clone https://github.com/Beim/schema-data-migration.git
cd schema-data-migration
pip install .
```

> If you see errors related to `mysqlclient`, please check https://pypi.org/project/mysqlclient/

## Step by step guide

[Step by step guide](./docs/step_by_step_guide.md)

## Usage

```bash
# Initialize project
sdm init [--host HOST] [-P PORT] [-u USER] -s SCHEMA [--author AUTHOR]

# Add environment
sdm add-env [--host HOST] [-P PORT] [-u USER] environment

# Make schema migration plan
sdm make-schema [--author AUTHOR] name

# Make data migration plan
# available types: sql,sql_file,python,shell,typescript
sdm make-data [--author AUTHOR] name type

# Make repeatable migration plan
sdm make-repeatable [--author AUTHOR] name type

# Migrate to a specific version or latest
sdm migrate [-v VERSION] [-n NAME] [--fake] [--dry-run] [-o OPERATOR] environment

# Rollback to a specific version
sdm rollback -v VERSION [-n NAME] [--fake] [--dry-run] [-o OPERATOR] environment

# Show migration history
sdm info environment

# Find schema differences
# available values: HEAD, <version>, <version>_<name>, <environment>
sdm diff [-v] left right

# Updates the files under schema directory to match the database or an exiting migration plan
sdm pull env_or_version

# Fix stuck migration
sdm fix [--fake] [-o OPERATOR] {migrate,rollback} environment

# Run skeema command
# Command reference https://www.skeema.io/docs/commands/
sdm skeema [extra_args...]
# e.g.
sdm skeema format dev
sdm skeema lint dev

# Generate automatic test
sdm test gen [--output OUTPUT] {simple_forward,step_forward,step_backward,monkey}
# Run automatic test
sdm test run [--input INPUT] [--clear] {simple_forward,step_forward,step_backward,monkey,custom} environment
```

## Migration plan types

All changes to the database are called **migrations** and are defined as JSON format files. The files are referred to here as "migration plan".

There're three types of migrations: `Schema`, `Data` and `Repeatable`. 
- `Schema` migrations are suitable for schema changes like: Creating/altering tables/indexes/foreign keys...
- `Data` migrations are suitable for data changes like: Inserting/updating tables...
- `Repeatable` migrations are suitable for idempotent changes like: Inserting seed data, Creating triggers/views...


`Schema` and `Data` migrations have a version, a name and a dependency (except for the initial migration). 
- The version and name are used to uniquely identify a migration. 
- The dependency is a composition of the version and name of a schema or data migration. The dependency is used to define the execution order of the migrations.


`Repeatable` migrations have a name, a dependency, a ignore_after field and a fixed version (R). 
- The name is used to uniquely identify a migration. 
- The dependency, ignore_after is a composition of the version and name of a schema or data migration. A repeatable migration will only be executed if it's dependency has been applied, and it will not be executed if it's ignore_after has been applied.
- Repeatable migrations are (re-)applied every time the checksum changes. The checksum is calculated based on the content of the migration plan and it's linked files.
- Within a single migration run, repeatable migrations are always applied last, after all pending schema and data migrations have been executed. 
- The order in which repeatable migrations are applied is not guaranteed. 
- It is your responsibility to ensure the same repeatable migration can be applied multiple times. 
- Repeatable migrations will be rolled back if they're rollbackable and their dependency has been rolled back.

## Precheck hook

You can add a precheck hook to a migration plan, which will be executed before the actual change is executed. The precheck hook is useful for repeatable migration, especially when the repeatable migration may fetch external resources that will not be included when calculating the checksum.

Here's an example of how to use the precheck hook:

```json
{
    "version": "0002",
    "name": "insert_test_data",
    "type": "data",
    "change": {
        "forward": {
            "type": "sql",
            "sql": "INSERT INTO `user` (`id`, `name`) VALUES (1, 'foo.bar');",
            "precheck": {
                "type": "sql",
                "sql": "SELECT COUNT(*) FROM `user` WHERE `id` = 1;",
                "expected": 0
            }
        }
    },
    "dependencies": [
        {
            "version": "0001",
            "name": "new_test_table"
        }
    ]
}
```

There're 5 types of precheck hook available: `sql`, `sql_file`, `python`, `shell`, `typescript`.
- For `sql` and `sql_file` types, the expected value is checked against the first returned value from the sql statement. e.g. `SELECT COUNT(*) ...`
- For `python` and `typescript` types, the expected value is checked against the return value of the `run` function.
- For `shell` type, the expected value is checked against the return code of the script.

If the precheck hook is set for the repeatable migration, the default checksum behavior will be skipped. The control is handed over to the precheck hook, and a checksum will be passed to it.
- For `python` and `typescript` types, the checksum is passed as arguments: `args['SDM_CHECKSUM_MATCH']`
- For `shell` type, the checksum is passed as environment variable: `$SDM_CHECKSUM_MATCH`
- The feature is not supported for `sql` and `sql_file` because the default behaivour is usually sufficient.

## Fake migration and rollback

You can fake run a migration using the --fake flag. This will add the migration to the migrations table without running it. This is useful for migrations created after manual changes have already been made to the database or when migrations have been run externally (e.g. by another tool or application), and you still would like to keep a consistent migration history.

```bash
# migrate
sdm migrate dev --fake

# rollback
sdm rollback dev --fake
```

## Testing is important

Testing is a crucial aspect of software development, and `sdm` can help you generate and run test scripts based on your migration plans. 

```bash
# Generate automatic test
sdm test gen [--output OUTPUT] [--walk-len WALK_LEN] [--start START] [--important IMPORTANT] [--non-important NON_IMPORTANT] {simple_forward,step_forward,step_backward,monkey}
# Run automatic test
sdm test run [--input INPUT] [--clear] [--walk-len WALK_LEN] [--start START] [--important IMPORTANT] [--non-important NON_IMPORTANT] {simple_forward,step_forward,step_backward,monkey,custom} environment
```

There are four types of built-in test scripts that `sdm` can generate for you:

- **simple_forward**: migrate from the initial version to the latest version directly.
- **step_forward**: migrate from the initial version to the latest version step by step.
- **step_backward**: migrate and rollback all possible paths step by step.
- **monkey**: randomly migrate and rollback, with options to specify the walk length, start plan, important plans, and non-important plans.

The generated test scripts will be saved into a JSON file:

e.g.
```json
[
    "0000_init",
    "0001_new_test_table",
    "0000_init",
    "0002_insert_test_data",
    "0001_new_test_table",
    "0000_init",
    "0003_add_addr_to_test_table",
    "0002_insert_test_data",
    "0001_new_test_table",
    "0000_init"
]
```

You can also run customized test script by setting the type to **custom**.


## Fix migration and rollback

Sometimes a migration fails due to incorrect SQL statements, the state in migration history will be `PROCESSING` which will prevent any new migration or rollback to be executed.

You may want to fix the SQL statements and retry using the `fix` command.

```bash
# migration
sdm fix migrate dev

# rollback
sdm fix rollback dev

# this is also possible with `--fake` flag
sdm fix migrate dev --fake
sdm fix rollback dev --fake
```

## Version control

You'll occasionally come across situations where you and another developer have both committed a migration at the same time, resulting in two migrations with the same number.

Don't worry - the numbers are just there for developers' reference, `sdm` just cares that each migration has a different `version` and `name`. Migration plans specify which other migration plan they depend on in the file, so it's possible to detect when theress two new migrations that aren't ordered.

When this happens, `sdm` will prompt you.

## Migration log

`sdm` creates two tables in the database by default: `_migration_history` and `_migration_history_log`. The `_migration_history` table stores information about applied migration plans, while the `_migration_history_log` table logs all operations. When you rollback a migration, a row will be deleted from _migration_history, and a row will be inserted into _migration_history_log to help you trace back the changes.

You can change the default database name by setting environment variable: `TABLE_MIGRATION_HISTORY` and `TABLE_MIGRATION_HISTORY`.

## Unexpected files in .schema_store directory

When you're developing a schema migration plan, you might create and delete different versions of it until you're satisfied. However, some SQL files that were changed in the process will be copied to the .schema_store directory and become useless, since they're not linked to any migration plan and will never be used.

To find and delete these unnecessary files, you can use the following command:

```bash
sdm clean store --dry-run
sdm clean store
```

The first command will show you which files would be deleted without actually deleting them (a "dry run"), while the second command will actually delete the files.

## Online schema change

To enable online schema change, add the following configuration to your `env.ini` file:

```ini
alter-wrapper=/usr/local/bin/pt-online-schema-change --execute --alter {CLAUSES} D={SCHEMA},t={TABLE},h={HOST},P={PORT},u={USER},p={PASSWORDX}
```

You can find more options in the [Skeema documentation](https://www.skeema.io/docs/faq/#how-do-i-configure-skeema-to-use-online-schema-change-tools)

## Future plans

- [ ] Support database/table sharding
