## Step by step guide

### Prepare databases

Prepare a database as `production` environment: `127.0.0.1:3306/awesome_db`:

```sql
CREATE DATABASE `awesome_db`;

USE `awesome_db`;
CREATE TABLE `user` (
  `id` int(11) NOT NULL,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

Prepare another database as `dev` environment: `127.0.0.1:3307/awesome_db`:


```sql
CREATE DATABASE `awesome_db`;
```

### Initialize project

```bash
mkdir awesome_project && cd awesome_project
git init
MYSQL_PWD='your-password' sdm init --host 127.0.0.1 --port 3306 -u root --schema awesome_db
mv pre-commit .git/hooks/
```

The `init` command creates the following files and directories:

```bash
.
├── .env                # Environment variables
├── migration_plan/
│   └── 0000_init.json  # Migration plan, format <version>_<name>.json
├── data/               # Data migration script
└── schema/             # Schema model
    └── .skeema         # Database environment configuration
```

Also it generates a "schema dump" in `schema` directory: CREATE files (CREATE TABLE, CREATE PROCEDURE, CREATE FUNCTION) for all tables and routines found on a DB instance.

### Add environment

```bash
sdm add-env --host 127.0.0.1 --port 3307 -u root dev
```

The `add-env` command adds a new environment configuration into `schema/.skeema` file:

```ini
[production]
flavor=mysql:5.7
host=127.0.0.1
port=3306
user=root

[dev]
flavor=mysql:5.7
host=127.0.0.1
port=3307
user=root
```

### Migrate

Run the following command, the `user` table will be created in `dev` environment:

```bash
sdm migrate dev
```


### Make schema migration plan

Migrations are stored as JSON format, referred to here as "migration plan".

Now let's add a new column to `user` table, edit `./schema/user.sql`:

```sql
CREATE TABLE `user` (
  `id` int(11) NOT NULL,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `address` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

Run the following command:

```bash
sdm make-schema add_address_to_user_tab
```

A schema migration plan is saved to `./migration_plan/0001_add_address_to_user_tab.json` :
- The "change.forward" object defines the desired version of schema.
- The "change.backward" object defines the last version of schema.
- The "id" is an unique "SHA-1" hash that's created when make new schema migration plan. Usually you don't want to edit it.

```json
{
    "version": "0001",
    "name": "add_address_to_user_tab",
    "author": "",
    "type": "schema",
    "change": {
        "forward": {
            "id": "edbd584f553368eaeda952147da211801e553528"
        },
        "backward": {
            "id": "a4833f8f3e50dd47032bd7a970ac74fcbd6fcaf8"
        }
    },
    "dependencies": [
        {
            "version": "0000",
            "name": "init"
        }
    ]
}
```

Run migrate command:

```bash
sdm migrate dev
```

The following SQL statements will be executed:

```sql
ALTER TABLE `user` ADD COLUMN `address` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL;
```

### Show migration history

Run the following command:

```bash
sdm info dev

# output
|   ver | name                    | type   | state      | created             | updated             |
|-------+-------------------------+--------+------------+---------------------+---------------------|
|  0000 | init                    | schema | SUCCESSFUL | 2023-07-30 00:09:22 | 2023-07-30 00:09:22 |
|  0001 | add_address_to_user_tab | schema | SUCCESSFUL | 2023-07-30 00:09:22 | 2023-07-30 00:09:22 |
```


### Make data migration plan

Run the following command:

```bash
sdm make-data seed_user_table sql
```

A data migration plan is saved to `./migration_plan/0002_seed_user_table.json`:

Edit the data migration plan file, add forward and backward script:

> Backward is optional, but it's usually good to have a way to rollback.

```json
{
    "version": "0002",
    "name": "seed_user_table",
    "author": "",
    "type": "data",
    "change": {
        "forward": {
            "type": "sql",
            "sql": "INSERT INTO `user` (`id`, `name`, `address`) VALUES (1, 'foo', 'bar');"
        },
        "backward": {
            "type": "sql",
            "sql": "DELETE FROM `user` WHERE `id`=1;"
        }
    },
    "dependencies": [
        {
            "version": "0001",
            "name": "add_address_to_user_tab"
        }
    ]
}
```

You can use `--dry-run` to preview the changes to be made:

```bash
sdm migrate dev --dry-run
# output
|   ver | name            | type   | forward                                  | backward                         |
|-------+-----------------+--------+------------------------------------------+----------------------------------|
|  0002 | seed_user_table | data   | INSERT INTO `user` (`id`, `name`, `ad... | DELETE FROM `user` WHERE `id`=1; |
```

Run migrate again and check migration history:

```bash
sdm migrate dev
sdm info dev

# output
|   ver | name                    | type   | state      | created             | updated             |
|-------+-------------------------+--------+------------+---------------------+---------------------|
|  0000 | init                    | schema | SUCCESSFUL | 2023-07-30 00:09:22 | 2023-07-30 00:09:22 |
|  0001 | add_address_to_user_tab | schema | SUCCESSFUL | 2023-07-30 00:09:22 | 2023-07-30 00:09:22 |
|  0002 | seed_user_table         | data   | SUCCESSFUL | 2023-07-30 00:18:32 | 2023-07-30 00:18:32 |
```


### Rollback

Run the following command to rollback to version 0000:

```bash
sdm rollback --version 0000 dev
```

`Migration` will execute the following SQL statements:

```sql
DELETE FROM `user` WHERE `id`=1;

ALTER TABLE `user` DROP COLUMN `address`;
```

Check the migration history again:

```bash
|   ver | name   | type   | state      | created             | updated             |
|-------+--------+--------+------------+---------------------+---------------------|
|  0000 | init   | schema | SUCCESSFUL | 2023-07-30 00:09:22 | 2023-07-30 00:09:22 |
```

### Detect schema drift

Run the following command to find difference between version `0001` and `dev` environment:

```
sdm diff 1 dev -v
```

It outputs:

```
diff --color -Nr -U4 left/user.sql right/user.sql
--- left/user.sql       2023-07-30 12:22:26.880472042 +1200
+++ right/user.sql      2023-07-30 12:22:26.888472018 +1200
@@ -1,6 +1,5 @@
 CREATE TABLE `user` (
   `id` int(11) NOT NULL,
   `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
-  `address` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
   PRIMARY KEY (`id`)
 ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
2023-07-30 12:22:26 [ERROR]  difference found between 1 and dev
```

What's more:

```bash
# Find difference between production and dev environment
sdm diff production dev -v

# Find difference between version 0000 and 0001
sdm diff 0 1 -v

# Find difference between version 0001 and schema model
sdm diff 1 HEAD -v

# Find difference between version dev environment and schema model
sdm diff dev HEAD -v
```

### More about dava migration

Run `migration make-data -h` to see the options.

#### SQL file

```bash
sdm make-data seed_by_sql_file sql_file
```

Saved migration plan to `./migration_plan/0003_seed_by_sql_file.json`

Now let's create two SQL files:

```
# ./data/seed_by_sql_file.sql
INSERT INTO `user` (`id`, `name`, `address`) VALUES (2, 'foo', 'bar');

# ./data/seed_by_sql_file_rollback.sql
DELETE FROM `user` WHERE `id`=2;
```

And add them to the migration plan, now you can migrate!

```json
{
    "version": "0003",
    "name": "seed_by_sql_file",
    "author": "",
    "type": "data",
    "change": {
        "forward": {
            "type": "sql_file",
            "sql_file": "seed_by_sql_file.sql"
        },
        "backward": {
            "type": "sql_file",
            "sql_file": "seed_by_sql_file_rollback.sql"
        }
    },
    "dependencies": [
        {
            "version": "0002",
            "name": "seed_user_table"
        }
    ]
}
```

#### Python file

```bash
sdm make-data seed_by_python python
```

Saved migration plan to `./migration_plan/0004_seed_by_python.json`

Now let's create two Python files:

```python
# ./data/seed_by_python.py
from sqlalchemy.orm import Session
from sqlalchemy import text

def run(session: Session):
    with session.begin():
        session.execute(text("INSERT INTO `user` (`id`, `name`, `address`) VALUES (3, 'foo', 'bar');"))

# ./data/seed_by_python_rollback.py
from sqlalchemy.orm import Session
from sqlalchemy import text

def run(session: Session, args: dict) -> int:
    with session.begin():
        session.execute(text("DELETE FROM `user` WHERE `id`=3"))
    return 0
```

And add them to the migration plan, now you can migrate!

```json
{
    "version": "0004",
    "name": "seed_by_python",
    "author": "",
    "type": "data",
    "change": {
        "forward": {
            "type": "python",
            "python_file": "seed_by_python.py"
        },
        "backward": {
            "type": "python",
            "python_file": "seed_by_python_rollback.py"
        }
    },
    "dependencies": [
        {
            "version": "0003",
            "name": "seed_by_sql_file"
        }
    ]
}
```

#### Typescript file

```bash
# install dependencies, only need to run once
npm install

# you may also need to edit the variables `NODE_CMD_PATH` and `NPM_CMD_PATH` in the `.env` file
NODE_CMD_PATH="node"
NPM_CMD_PATH="npm"

# create migration plan with typescript
sdm make-data seed_by_typescript typescript
```

Saved migration plan to `./migration_plan/0005_seed_by_typescript.json`

Now let's add two Typescript files:

```ts
// ./data/seed_by_typescript.ts
import { Column, PrimaryColumn, Entity, DataSource } from "typeorm"

@Entity()
class User {
  @PrimaryColumn()
  id: number

  @Column()
  name: string

  @Column()
  address: string
}

export const Entities = [User]

export const Run = async (datasource: DataSource, args: { [key: string]: string }): Promise<number> => {
  const user = new User()
  user.id = 4
  user.name = "foo"
  user.address = "bar"
  await datasource.manager.save(user)
  return 0
}

// ./data/seed_by_typescript_rollback.ts
import { Column, PrimaryColumn, Entity, DataSource } from "typeorm"

@Entity()
class User {
  @PrimaryColumn()
  id: number

  @Column()
  name: string

  @Column()
  address: string
}

export const Entities = [User]

export const Run = async (datasource: DataSource, args: { [key: string]: string }): Promise<number> => {
  const userRepository = datasource.manager.getRepository(User)
  const user = await userRepository.findOneBy({id: 4})
  await userRepository.remove(user)
  return 0
}
```

And add them to the migration plan, now you can migrate!

```json
{
    "version": "0005",
    "name": "seed_by_typescript",
    "author": "",
    "type": "data",
    "change": {
        "forward": {
            "type": "typescript",
            "typescript_file": "seed_by_typescript.ts"
        },
        "backward": {
            "type": "typescript",
            "typescript_file": "seed_by_typescript_rollback.ts"
        }
    },
    "dependencies": [
        {
            "version": "0004",
            "name": "seed_by_python"
        }
    ]
}
```

#### Shell file

```bash
sdm make-data seed_by_shell shell
```

Saved migration plan to `./migration_plan/0006_seed_by_shell.json`

Now let's create two Shell files:

> The database related environment variables are available in the shell script.

```bash
# ./data/seed_by_shell.sh
#!/bin/sh
mysql -u$USER -p$MYSQL_PWD -h$HOST -P$PORT -D$SCHEMA -e "INSERT INTO user (id, name, address) VALUES (5, 'foo', 'bar');"

# ./data/seed_by_shell_rollback.sh
#!/bin/sh
mysql -u$USER -p$MYSQL_PWD -h$HOST -P$PORT -D$SCHEMA -e "DELETE FROM user WHERE id=5;"
```

And add them to the migration plan, now you can migrate!

```json
{
    "version": "0006",
    "name": "seed_by_shell",
    "author": "",
    "type": "data",
    "change": {
        "forward": {
            "type": "shell",
            "shell_file": "seed_by_shell.sh"
        },
        "backward": {
            "type": "shell",
            "shell_file": "seed_by_shell_rollback.sh"
        }
    },
    "dependencies": [
        {
            "version": "0005",
            "name": "seed_by_typescript"
        }
    ]
}
```
