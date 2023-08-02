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
