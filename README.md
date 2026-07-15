# razzle dazzle

A configurable, CLI-driven journal. You define a set of prompts once per
journal, then answer them repeatedly to append rows to a CSV. Journals
support point-in-time backups and revert, and everything is namespaced
under a single configurable base directory.

## Contents

- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Directory & file layout](#directory--file-layout)
- [`definitions.json` schema](#definitionsjson-schema)
- [`data.csv` schema](#datacsv-schema)
- [CLI reference](#cli-reference)
- [Extending: adding a new CLI arg or field](#extending-adding-a-new-cli-arg-or-field)
- [Running tests](#running-tests)
- [Known issues](#known-issues)

## Requirements

- Python 3.10+ (uses `X | Y` union type hints and `hashlib.file_digest`)
- [`pandas`](https://pandas.pydata.org/) — used by `remove_entry`, `get_entry`, and `add_prompt` to
  edit `data.csv` in place

```sh
pip install -r requirements.txt
```

## Quick start

```sh
# Create a journal (interactively prompts for questions + answer types)
python src/main.py --new my_journal

# Add an entry (prompts once per question defined on the journal)
python src/main.py my_journal --new-entry

# See what's in it
python src/main.py my_journal --list-entries
python src/main.py my_journal --list-prompts

# Back it up, then revert to that backup later
python src/main.py my_journal --backup
python src/main.py my_journal --revert-to-backup <backup id>

# See every journal in the base directory
python src/main.py --list-journals
```

## Directory & file layout

All journals live under one **base directory**, tracked in a small config
file next to the script:

```
src/config.json                    # {"base_directory": "<path>"}
<base_directory>/
  <journal_name>/
    data.csv                       # header + one row per entry
    definitions.json               # journal metadata (see below)
    backups/
      <backup_id>.csv              # snapshot of data.csv at backup time
      <backup_id>.json             # {id, hash, date, entries, prompts} snapshot
```

`src/config.json` is created automatically on first run, defaulting the
base directory to `src/.data`. `--change-base-directory DIRECTORY` points
the config at a new (must not already exist) directory going forward; it
doesn't move existing journals.

## `definitions.json` schema

```jsonc
{
  "name": "<journal name>",
  "id": "<uuid4 hex>",
  "prompts": [
    {"prompt": "<question text>", "dtype": "int|float|str|bool"}
  ],
  "entries": [
    {"id": "<uuid4 hex>", "date": "<ISO 8601 timestamp>"}
  ],
  "backups": [
    {"id": "<uuid4 hex>", "hash": "<sha256 hex of the backup csv>", "date": "<ISO 8601 timestamp>"}
  ]
}
```

A `backups/<backup_id>.json` file has the same shape as one `backups[]`
entry, plus a snapshot of `entries` and `prompts` as they were at backup
time (used by `--revert-to-backup` to restore them).

Every field name above is a named constant in `src/main.py`, not a string
literal — see [Extending](#extending-adding-a-new-cli-arg-or-field) for why
that matters when you add a new one.

| Constant                                    | Value       | Used for                                    |
|----------------------------------------------|-------------|-----------------------------------------------|
| `DEFINITIONS_NAME_FIELDNAME`                  | `"name"`    | journal name                                   |
| `ID_FIELDNAME` (aliased by `DEFINITIONS_ID_FIELDNAME`) | `"id"` | journal / entry / backup / CSV id column |
| `DATE_FIELDNAME`                              | `"date"`    | entry / backup timestamp, CSV date column      |
| `HASH_FIELDNAME`                              | `"hash"`    | backup CSV integrity hash                      |
| `DEFINITIONS_PROMPTS_FIELDNAME`               | `"prompts"` | list of prompt definitions                     |
| `PROMPT_QUESTION_FIELDNAME`                   | `"prompt"`  | a prompt's question text                       |
| `PROMPT_DTYPE_FIELDNAME`                      | `"dtype"`   | a prompt's expected answer type                |
| `DEFINITIONS_ENTRIES_FIELDNAME`               | `"entries"` | list of recorded entries                       |
| `DEFINITIONS_BACKUPS_FIELDNAME`               | `"backups"` | list of recorded backups                       |

Supported prompt data types live in `TYPES` (`src/main.py`): `int`, `float`,
`str`, `bool`. Add a new one there to make it selectable when defining
prompts.

## `data.csv` schema

```
id,date,<prompt 1 question>,<prompt 2 question>,...
<uuid4 hex>,<ISO 8601 timestamp>,<answer 1>,<answer 2>,...
```

Columns after `id`/`date` are added in prompt order and named after the
prompt's question text. `--add-prompt` appends a new column to every
existing row (backfilled blank) and to future entries.

## CLI reference

Positional argument:

| Argument       | Description                                                                     |
|----------------|-----------------------------------------------------------------------------------|
| `journal_name` | Optional. Required by every flag in the two "Journal-scoped" tables below.        |

No journal name required:

| Flag                          | Value          | Description |
|-------------------------------|----------------|--------------|
| `--print-base-directory`      | —              | Print the currently configured base directory. |
| `--list-journals`             | —              | List `(name, id)` pairs for every journal in the base directory. |
| `--new NAME`                  | journal name   | Create a new journal named `NAME`; interactively prompts for its question/type pairs. |
| `--change-base-directory DIR` | directory path | Point the config at a new (nonexistent) base directory. |

Journal-scoped action flags (mutate state):

| Flag                     | Value        | Description |
|---------------------------|--------------|--------------|
| `--new-entry`              | —            | Walk through the journal's prompts and append an answer row. |
| `--add-prompt`             | —            | Interactively add one or more new prompts; existing rows get a blank value for each new column. |
| `--remove-entry ID`        | entry id     | Remove the entry `ID` from both `data.csv` and `definitions.json`. |
| `--backup`                 | —            | Snapshot `data.csv` + current prompts/entries into `backups/`. |
| `--revert-to-backup ID`    | backup id    | Restore `data.csv`, prompts, and entries from backup `ID` (verifies the backup's hash first). |
| `--remove-journal`         | —            | Delete the journal directory and everything in it. |

Journal-scoped read-only flags:

| Flag                | Value      | Description |
|----------------------|------------|--------------|
| `--list-entries`     | —          | List the journal's recorded entries. |
| `--list-prompts`     | —          | List the journal's configured prompts. |
| `--list-backups`     | —          | List the journal's recorded backups. |
| `--get-entry ID`     | entry id   | Print one entry's full row data (from `data.csv`, cross-checked against `definitions.json`). |

## Extending: adding a new CLI arg or field

This was written to make both of these additions mechanical:

**New CLI flag:**
1. Add it in `add_arguments()` (`src/main.py`), grouped with similar flags
   (mutating "does stuff" vs read-only "prints stuff" vs no-journal "field
   args").
2. Implement the behavior as its own function taking `jdir: Path` (plus
   whatever else it needs) — follow the existing functions' shape: raise on
   a missing/invalid target rather than silently no-op'ing, and use the
   `*_FIELDNAME` constants for any JSON key access.
3. Wire it into `argument_handler()` — inside the `if jname:` block if it
   operates on a specific journal, above it (alongside
   `--print-base-directory`/`--list-journals`) if it doesn't.
4. Add a test class in `tests/test_main.py` mirroring the sibling tests
   (e.g. `TestRemoveEntry`, `TestGetEntry`) — cover the happy path, the
   missing-target error, and that unrelated state is left untouched.

**New `definitions.json` / `data.csv` field:**
1. Add a `*_FIELDNAME` constant near the top of `src/main.py` instead of
   using a string literal — this is the single source of truth every
   read/write should go through, so a rename only touches one line.
2. Update the schema comment block above `list_journals()`.
3. If it's per-row CSV data, extend the header-writing in `new_journal()`
   and the row-writing in `new_entry()`.
4. Update this README's schema tables.

## Running tests

```sh
python -m unittest discover -s tests
```

Requires `pandas` to be importable (see [Requirements](#requirements)) —
without it, `import main` fails and no tests can run. A few tests
(`TestMainBootstrap`) spawn `python src/main.py` as a subprocess to exercise
the `__main__` startup block, so they run a little slower than the rest.

## Known issues

- `#TODO add show backup details` — there's no `get_backup`-style function
  analogous to `get_entry`; `--list-backups` only shows the summary list.
- `get_entry`/`remove_entry`/`add_prompt` pin the CSV `id` column to `str`,
  but other columns keep pandas' auto-inferred types (e.g. an `int`-typed
  prompt answer comes back as a Python `int`, not a string) — worth knowing
  if you're consuming `get_entry`'s output programmatically.
- `requirements.txt` was generated from a `pip freeze` of a shared virtual
  environment and includes packages (`matplotlib`, `numpy`, `pillow`, etc.)
  that `src/main.py` doesn't actually import — only `pandas` is used.
