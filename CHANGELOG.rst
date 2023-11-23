=========
Changelog
=========

Version 0.0.1
=============

- Added `init` command
- Added `add-ent` command
- Added `make-schema` command
- Added `make-data` command
- Added `migrate` command
- Added `rollback` command
- Added `info` command
- Added `diff` command
- Added `pull` command
- Added `fix` command

Version 0.1.0
=============

- Added support for online schema migration
- Enhanced `info` command to display unmigrated migration plans
- Added `pull` command
- Fix: access env.ini file from docker container

Version 0.1.1
=============

- Fix: reduce docker image size

Version 0.2.0
=============

- Add `clean` command to clean up out of source control files in .schema_store
- Add shortcut for `fix migrate/rollback` command
- Log --fake flag in _migration_history_log table
- Fix: `info` command print unxpected migration history instead of throw error
- Fix: Add .gitkeep to directories in .schema_store to make sure they are tracked by git 

Version 0.3.0
=============

- Add `make-repeatable` command to generate repeatable migration
- Add `checksum` and `type` to migration history table

Version 0.4.0
=============

- Add `test` command to test migration

Version 0.4.1
=============

- Fix: repeatable migration is not executed when ignore_after is set

Version 0.5.0
=============

- Add `precheck` hook to migration plan

Version 0.5.1
=============

- Add dependency check for repeatable migration

Version 0.5.2
=============

- Add "--version" flag to print version
- Pass "SDM_DATA_DIR" as argument to migration script

Version 0.5.3
=============

- Refactor code

Version 0.5.4
=============

- Repeatable migration will not be executed if fake flag is set

Version 0.5.5
=============

- Add docker base image

Version 0.5.6
=============

- Add unittest github action

Version 0.5.7
=============

- Add `rollbackable` column in `info` command output
- Enable ALLOW_UNSAFE by default when rollback schema migration

Version 0.5.8
=============

- Use `.skeema` to replace `env.ini` for configuration

Version 0.5.9
=============

- Fix `test` command fail due to foreign key check

Version 0.5.10
=============

- Fix `skeema` command current working directory

Version 0.5.11
=============

- Enable python virtual env in docker file

Version 0.6.0
=============

- Add new configuration `envs` field to migration plan for calculating checksum

Version 0.6.1
=============

- Make MYSQL_PWD optional, if not set, use empty string as password

Version 0.6.2
=============

- enable pool_pre_ping for sqlalchemy
