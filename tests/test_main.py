"""Tests for the journal-management features implemented so far in src/main.py.

Run with: python -m unittest discover -s tests
"""
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import main


def new_journal_with_input(dir: Path, journal_name: str, responses: list[str]):
    with patch("builtins.input", side_effect=responses):
        main.new_journal(dir, journal_name)


class TempDirTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)


class TestAddArguments(unittest.TestCase):
    def setUp(self):
        self.parser = argparse.ArgumentParser()
        main.add_arguments(self.parser)

    def test_defaults_with_no_args(self):
        args = self.parser.parse_args([])
        self.assertIsNone(args.journal_name)
        self.assertFalse(args.backup)
        self.assertFalse(args.new_entry)
        self.assertFalse(args.remove_journal)
        self.assertFalse(args.list_backups)
        self.assertFalse(args.list_entries)
        self.assertFalse(args.list_journals)
        self.assertFalse(args.print_base_directory)
        self.assertIsNone(args.new)
        self.assertIsNone(args.change_base_directory)
        self.assertIsNone(args.remove_entry)
        self.assertIsNone(args.revert_to_backup)

    def test_journal_name_positional(self):
        args = self.parser.parse_args(["myjournal"])
        self.assertEqual(args.journal_name, "myjournal")

    def test_boolean_flags(self):
        args = self.parser.parse_args([
            "myjournal", "--backup", "--new-entry", "--remove-journal",
            "--list-backups", "--list-entries", "--list-journals",
            "--print-base-directory",
        ])
        self.assertTrue(args.backup)
        self.assertTrue(args.new_entry)
        self.assertTrue(args.remove_journal)
        self.assertTrue(args.list_backups)
        self.assertTrue(args.list_entries)
        self.assertTrue(args.list_journals)
        self.assertTrue(args.print_base_directory)

    def test_field_args(self):
        args = self.parser.parse_args([
            "--new", "newjournal",
            "--change-base-directory", "/some/dir",
            "--remove-entry", "entry123",
            "--revert-to-backup", "backup456",
        ])
        self.assertEqual(args.new, "newjournal")
        self.assertEqual(args.change_base_directory, "/some/dir")
        self.assertEqual(args.remove_entry, "entry123")
        self.assertEqual(args.revert_to_backup, "backup456")


class TestNewJournal(TempDirTestCase):
    def test_creates_expected_structure(self):
        new_journal_with_input(self.tmpdir, "myjournal", ["END"])
        jdir = self.tmpdir / "myjournal"

        self.assertTrue(jdir.is_dir())
        self.assertTrue((jdir / main.DATA_CSV_NAME).is_file())
        self.assertTrue((jdir / main.DEFINITIONS_JSON_NAME).is_file())
        self.assertTrue((jdir / main.BACKUPS_DIR_NAME).is_dir())

    def test_writes_valid_definitions_json(self):
        new_journal_with_input(self.tmpdir, "myjournal", ["END"])
        jdir = self.tmpdir / "myjournal"

        with open(jdir / main.DEFINITIONS_JSON_NAME) as f:
            defs = json.load(f)

        self.assertEqual(defs[main.DEFINITIONS_NAME_FIELDNAME], "myjournal")
        self.assertTrue(defs[main.DEFINITIONS_ID_FIELDNAME])
        self.assertEqual(defs[main.DEFINITIONS_PROMPTS_FIELDNAME], [])
        self.assertEqual(defs[main.DEFINITIONS_ENTRIES_FIELDNAME], [])
        self.assertEqual(defs[main.DEFINITIONS_BACKUPS_FIELDNAME], [])

    def test_raises_if_journal_already_exists(self):
        new_journal_with_input(self.tmpdir, "myjournal", ["END"])
        with self.assertRaises(Exception):
            new_journal_with_input(self.tmpdir, "myjournal", ["END"])

    def test_writes_csv_header_row_with_no_prompts(self):
        new_journal_with_input(self.tmpdir, "myjournal", ["END"])
        jdir = self.tmpdir / "myjournal"

        with open(jdir / main.DATA_CSV_NAME, newline="") as f:
            rows = list(csv.reader(f))
        self.assertEqual(rows, [["id", "date"]])

    def test_writes_csv_header_row_with_prompts(self):
        new_journal_with_input(
            self.tmpdir, "myjournal",
            ["how was your day", "str", "hours slept", "int", "END"],
        )
        jdir = self.tmpdir / "myjournal"

        with open(jdir / main.DATA_CSV_NAME, newline="") as f:
            rows = list(csv.reader(f))
        self.assertEqual(rows, [["id", "date", "how was your day", "hours slept"]])

    def test_new_journal_is_immediately_listable(self):
        new_journal_with_input(self.tmpdir, "myjournal", ["END"])

        journals = main.list_journals(self.tmpdir)
        self.assertEqual(len(journals), 1)
        name, jid = next(iter(journals))
        self.assertEqual(name, "myjournal")
        self.assertTrue(jid)

    def test_immediate_end_records_no_prompts(self):
        new_journal_with_input(self.tmpdir, "myjournal", ["END"])
        jdir = self.tmpdir / "myjournal"

        with open(jdir / main.DEFINITIONS_JSON_NAME) as f:
            defs = json.load(f)
        self.assertEqual(defs[main.DEFINITIONS_PROMPTS_FIELDNAME], [])

    def test_valid_prompts_are_recorded_in_order(self):
        new_journal_with_input(
            self.tmpdir, "myjournal",
            ["how was your day", "str", "hours slept", "int", "END"],
        )
        jdir = self.tmpdir / "myjournal"

        with open(jdir / main.DEFINITIONS_JSON_NAME) as f:
            defs = json.load(f)
        self.assertEqual(
            defs[main.DEFINITIONS_PROMPTS_FIELDNAME],
            [
                {"prompt": "how was your day", "dtype": "str"},
                {"prompt": "hours slept", "dtype": "int"},
            ],
        )

    def test_blank_prompt_question_is_skipped(self):
        new_journal_with_input(
            self.tmpdir, "myjournal",
            ["", "how was your day", "str", "END"],
        )
        jdir = self.tmpdir / "myjournal"

        with open(jdir / main.DEFINITIONS_JSON_NAME) as f:
            defs = json.load(f)
        self.assertEqual(
            defs[main.DEFINITIONS_PROMPTS_FIELDNAME],
            [{"prompt": "how was your day", "dtype": "str"}],
        )

    def test_blank_datatype_skips_prompt(self):
        new_journal_with_input(
            self.tmpdir, "myjournal",
            ["how was your day", "", "END"],
        )
        jdir = self.tmpdir / "myjournal"

        with open(jdir / main.DEFINITIONS_JSON_NAME) as f:
            defs = json.load(f)
        self.assertEqual(defs[main.DEFINITIONS_PROMPTS_FIELDNAME], [])

    def test_invalid_datatype_skips_prompt_and_warns(self):
        stderr = io.StringIO()
        with patch("sys.stderr", stderr):
            new_journal_with_input(
                self.tmpdir, "myjournal",
                ["how was your day", "bogus", "END"],
            )
        jdir = self.tmpdir / "myjournal"

        with open(jdir / main.DEFINITIONS_JSON_NAME) as f:
            defs = json.load(f)
        self.assertEqual(defs[main.DEFINITIONS_PROMPTS_FIELDNAME], [])
        self.assertIn("invalid", stderr.getvalue().lower())

    def test_valid_datatypes_are_accepted(self):
        responses = []
        for dtype in ("int", "float", "str", "bool"):
            responses += [f"prompt-{dtype}", dtype]
        responses.append("END")

        new_journal_with_input(self.tmpdir, "myjournal", responses)
        jdir = self.tmpdir / "myjournal"

        with open(jdir / main.DEFINITIONS_JSON_NAME) as f:
            defs = json.load(f)
        self.assertEqual(
            [p["dtype"] for p in defs[main.DEFINITIONS_PROMPTS_FIELDNAME]],
            ["int", "float", "str", "bool"],
        )

        self.assertEqual(main.list_entries(jdir), [])
        self.assertEqual(main.list_backups(jdir), [])


class TestListJournals(TempDirTestCase):
    def _write_definitions(self, jdir: Path, data: dict):
        jdir.mkdir(parents=True, exist_ok=True)
        with open(jdir / main.DEFINITIONS_JSON_NAME, "w") as f:
            json.dump(data, f)

    def test_empty_base_dir_returns_empty_list(self):
        result = main.list_journals(self.tmpdir)
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    def test_skips_dirs_without_definitions_file(self):
        (self.tmpdir / "not_a_journal").mkdir()
        self.assertEqual(main.list_journals(self.tmpdir), [])

    def test_skips_journals_without_id_field(self):
        self._write_definitions(self.tmpdir / "no_id", {})
        self.assertEqual(main.list_journals(self.tmpdir), [])

    def test_returns_name_id_pairs(self):
        self._write_definitions(self.tmpdir / "j1", {"id": "abc123"})
        self._write_definitions(self.tmpdir / "j2", {"id": "def456"})
        result = main.list_journals(self.tmpdir)
        self.assertIsInstance(result, list)
        self.assertCountEqual(result, [("j1", "abc123"), ("j2", "def456")])


class TestListEntries(TempDirTestCase):
    def test_raises_if_definitions_file_missing(self):
        jdir = self.tmpdir / "myjournal"
        jdir.mkdir()
        with self.assertRaises(Exception):
            main.list_entries(jdir)

    def test_returns_entries_field(self):
        jdir = self.tmpdir / "myjournal"
        jdir.mkdir()
        entries = [{"id": "1", "date": "2026-01-01"}]
        with open(jdir / main.DEFINITIONS_JSON_NAME, "w") as f:
            json.dump({main.DEFINITIONS_ENTRIES_FIELDNAME: entries}, f)
        result = main.list_entries(jdir)
        self.assertIsInstance(result, list)
        self.assertEqual(result, entries)
        for entry in result:
            self.assertIsInstance(entry, dict)
            self.assertCountEqual(entry.keys(), ["id", "date"])


class TestListBackups(TempDirTestCase):
    def test_raises_if_definitions_file_missing(self):
        jdir = self.tmpdir / "myjournal"
        jdir.mkdir()
        with self.assertRaises(Exception):
            main.list_backups(jdir)

    def test_returns_backups_field(self):
        jdir = self.tmpdir / "myjournal"
        jdir.mkdir()
        backups = [{"id": "1", "hash": "bbb", "date": "2026-01-01"}]
        with open(jdir / main.DEFINITIONS_JSON_NAME, "w") as f:
            json.dump({main.DEFINITIONS_BACKUPS_FIELDNAME: backups}, f)
        result = main.list_backups(jdir)
        self.assertIsInstance(result, list)
        self.assertEqual(result, backups)
        for entry in result:
            self.assertIsInstance(entry, dict)
            self.assertCountEqual(entry.keys(), ["id", "hash", "date"])


class TestListPrompts(TempDirTestCase):
    def test_raises_if_definitions_file_missing(self):
        jdir = self.tmpdir / "myjournal"
        jdir.mkdir()
        with self.assertRaises(Exception):
            main.list_prompts(jdir)

    def test_returns_prompts_field(self):
        jdir = self.tmpdir / "myjournal"
        jdir.mkdir()
        prompts = [{"prompt": "how was your day", "dtype": "str"}]
        with open(jdir / main.DEFINITIONS_JSON_NAME, "w") as f:
            json.dump({main.DEFINITIONS_PROMPTS_FIELDNAME: prompts}, f)
        result = main.list_prompts(jdir)
        self.assertIsInstance(result, list)
        self.assertEqual(result, prompts)
        for prompt in result:
            self.assertIsInstance(prompt, dict)
            self.assertCountEqual(prompt.keys(), ["prompt", "dtype"])

    def test_returns_empty_list_for_journal_with_no_prompts(self):
        new_journal_with_input(self.tmpdir, "myjournal", ["END"])
        jdir = self.tmpdir / "myjournal"

        result = main.list_prompts(jdir)
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    def test_returns_prompts_for_journal_with_prompts(self):
        new_journal_with_input(
            self.tmpdir, "myjournal",
            ["how was your day", "str", "hours slept", "int", "END"],
        )
        jdir = self.tmpdir / "myjournal"

        self.assertEqual(
            main.list_prompts(jdir),
            [
                {"prompt": "how was your day", "dtype": "str"},
                {"prompt": "hours slept", "dtype": "int"},
            ],
        )


class TestRemoveJournal(TempDirTestCase):
    def test_removes_empty_journal_dir(self):
        jdir = self.tmpdir / "myjournal"
        jdir.mkdir()
        main.remove_journal(jdir)
        self.assertFalse(jdir.exists())

    def test_raises_if_journal_dir_not_empty(self):
        jdir = self.tmpdir / "myjournal"
        jdir.mkdir()
        (jdir / "data.csv").touch()
        with self.assertRaises(OSError):
            main.remove_journal(jdir)


class TestBackup(TempDirTestCase):
    def setUp(self):
        super().setUp()
        new_journal_with_input(self.tmpdir, "myjournal", ["END"])
        self.jdir = self.tmpdir / "myjournal"
        (self.jdir / main.DATA_CSV_NAME).write_text("a,b,c\n1,2,3\n")

    def _backup_csv_files(self):
        return [p for p in (self.jdir / main.BACKUPS_DIR_NAME).iterdir() if p.suffix == ".csv"]

    def _set_entries(self, entries):
        defs_path = self.jdir / main.DEFINITIONS_JSON_NAME
        with open(defs_path) as f:
            defs = json.load(f)
        defs[main.DEFINITIONS_ENTRIES_FIELDNAME] = entries
        with open(defs_path, "w") as f:
            json.dump(defs, f)

    def _set_prompts(self, prompts):
        defs_path = self.jdir / main.DEFINITIONS_JSON_NAME
        with open(defs_path) as f:
            defs = json.load(f)
        defs[main.DEFINITIONS_PROMPTS_FIELDNAME] = prompts
        with open(defs_path, "w") as f:
            json.dump(defs, f)

    @staticmethod
    def _strip_snapshot_fields(details):
        return {
            k: v for k, v in details.items()
            if k not in (main.DEFINITIONS_ENTRIES_FIELDNAME, main.DEFINITIONS_PROMPTS_FIELDNAME)
        }

    def test_creates_backup_file_with_matching_hash(self):
        result = main.backup(self.jdir)

        backup_files = self._backup_csv_files()
        self.assertEqual(len(backup_files), 1)
        backup_file = backup_files[0]
        self.assertEqual(backup_file.name, f"{result['id']}.csv")
        self.assertEqual(backup_file.read_text(), "a,b,c\n1,2,3\n")

        expected_hash = hashlib.sha256(backup_file.read_bytes()).hexdigest()
        self.assertEqual(result["hash"], expected_hash)

    def test_returns_id_hash_date_entries_and_prompts(self):
        result = main.backup(self.jdir)
        self.assertCountEqual(result.keys(), ["id", "hash", "date", "entries", "prompts"])
        self.assertTrue(result["id"])
        self.assertTrue(result["hash"])
        dt.datetime.fromisoformat(result["date"])
        self.assertEqual(result["entries"], [])
        self.assertEqual(result["prompts"], [])

    def test_backup_is_recorded_in_journal_definitions_json(self):
        result = main.backup(self.jdir)
        expected = self._strip_snapshot_fields(result)
        self.assertEqual(main.list_backups(self.jdir), [expected])

    def test_multiple_backups_accumulate_with_unique_ids(self):
        first = main.backup(self.jdir)
        second = main.backup(self.jdir)

        self.assertNotEqual(first["id"], second["id"])
        expected = [
            self._strip_snapshot_fields(first),
            self._strip_snapshot_fields(second),
        ]
        self.assertEqual(main.list_backups(self.jdir), expected)

        backup_names = {p.name for p in self._backup_csv_files()}
        self.assertEqual(backup_names, {f"{first['id']}.csv", f"{second['id']}.csv"})

    def _backup_defs_path(self, backup_id: str) -> Path:
        return self.jdir / main.BACKUPS_DIR_NAME / f"{backup_id}.json"

    def test_writes_a_definitions_json_per_backup(self):
        result = main.backup(self.jdir)

        backup_defs_path = self._backup_defs_path(result["id"])
        self.assertTrue(backup_defs_path.is_file())
        with open(backup_defs_path) as f:
            backup_defs = json.load(f)
        self.assertEqual(backup_defs, result)

    def test_backup_definitions_snapshot_reflects_current_entries(self):
        entries = [{"id": "e1", "date": "2026-01-01"}]
        self._set_entries(entries)

        result = main.backup(self.jdir)
        self.assertEqual(result["entries"], entries)

        with open(self._backup_defs_path(result["id"])) as f:
            backup_defs = json.load(f)
        self.assertEqual(backup_defs["entries"], entries)

    def test_backup_definitions_snapshot_reflects_current_prompts(self):
        prompts = [{"prompt": "how was your day", "dtype": "str"}]
        self._set_prompts(prompts)

        result = main.backup(self.jdir)
        self.assertEqual(result["prompts"], prompts)

        with open(self._backup_defs_path(result["id"])) as f:
            backup_defs = json.load(f)
        self.assertEqual(backup_defs["prompts"], prompts)

    def test_journal_definitions_json_prompts_untouched_by_backup(self):
        prompts = [{"prompt": "how was your day", "dtype": "str"}]
        self._set_prompts(prompts)

        main.backup(self.jdir)

        with open(self.jdir / main.DEFINITIONS_JSON_NAME) as f:
            journal_defs = json.load(f)
        self.assertEqual(journal_defs[main.DEFINITIONS_PROMPTS_FIELDNAME], prompts)

    def test_each_backup_gets_its_own_definitions_json(self):
        first = main.backup(self.jdir)
        second = main.backup(self.jdir)

        self.assertNotEqual(first["id"], second["id"])

        with open(self._backup_defs_path(first["id"])) as f:
            first_defs = json.load(f)
        with open(self._backup_defs_path(second["id"])) as f:
            second_defs = json.load(f)

        self.assertEqual(first_defs, first)
        self.assertEqual(second_defs, second)


class TestRevertToBackup(TempDirTestCase):
    def setUp(self):
        super().setUp()
        new_journal_with_input(self.tmpdir, "myjournal", ["how was your day", "str", "END"])
        self.jdir = self.tmpdir / "myjournal"
        (self.jdir / main.DATA_CSV_NAME).write_text("original\n")

        defs_path = self.jdir / main.DEFINITIONS_JSON_NAME
        with open(defs_path) as f:
            defs = json.load(f)
        defs[main.DEFINITIONS_ENTRIES_FIELDNAME] = [{"id": "e1", "date": "2026-01-01"}]
        with open(defs_path, "w") as f:
            json.dump(defs, f)

        self.backup_result = main.backup(self.jdir)

    def _mutate_journal(self):
        (self.jdir / main.DATA_CSV_NAME).write_text("mutated\n")
        defs_path = self.jdir / main.DEFINITIONS_JSON_NAME
        with open(defs_path) as f:
            defs = json.load(f)
        defs[main.DEFINITIONS_PROMPTS_FIELDNAME] = []
        defs[main.DEFINITIONS_ENTRIES_FIELDNAME] = []
        with open(defs_path, "w") as f:
            json.dump(defs, f)

    def test_raises_if_backup_does_not_exist(self):
        with self.assertRaises(Exception):
            main.revert_to_backup("doesnotexist", self.jdir)

    def test_raises_if_backup_csv_missing(self):
        (self.jdir / main.BACKUPS_DIR_NAME / f"{self.backup_result['id']}.csv").unlink()
        with self.assertRaises(Exception):
            main.revert_to_backup(self.backup_result["id"], self.jdir)

    def test_reverts_successfully_when_backup_csv_is_intact(self):
        self._mutate_journal()
        main.revert_to_backup(self.backup_result["id"], self.jdir)
        self.assertEqual((self.jdir / main.DATA_CSV_NAME).read_text(), "original\n")

    def test_raises_if_backup_csv_is_corrupted(self):
        (self.jdir / main.BACKUPS_DIR_NAME / f"{self.backup_result['id']}.csv").write_text("tampered\n")
        with self.assertRaises(Exception):
            main.revert_to_backup(self.backup_result["id"], self.jdir)

    def test_does_not_mutate_journal_when_backup_csv_is_corrupted(self):
        self._mutate_journal()
        (self.jdir / main.BACKUPS_DIR_NAME / f"{self.backup_result['id']}.csv").write_text("tampered\n")

        with self.assertRaises(Exception):
            main.revert_to_backup(self.backup_result["id"], self.jdir)

        self.assertEqual((self.jdir / main.DATA_CSV_NAME).read_text(), "mutated\n")
        with open(self.jdir / main.DEFINITIONS_JSON_NAME) as f:
            defs = json.load(f)
        self.assertEqual(defs[main.DEFINITIONS_PROMPTS_FIELDNAME], [])
        self.assertEqual(defs[main.DEFINITIONS_ENTRIES_FIELDNAME], [])

    def test_raises_if_backup_json_missing(self):
        (self.jdir / main.BACKUPS_DIR_NAME / f"{self.backup_result['id']}.json").unlink()
        with self.assertRaises(Exception):
            main.revert_to_backup(self.backup_result["id"], self.jdir)

    def test_restores_data_csv(self):
        self._mutate_journal()
        main.revert_to_backup(self.backup_result["id"], self.jdir)
        self.assertEqual((self.jdir / main.DATA_CSV_NAME).read_text(), "original\n")

    def test_restores_prompts_and_entries(self):
        self._mutate_journal()
        main.revert_to_backup(self.backup_result["id"], self.jdir)

        with open(self.jdir / main.DEFINITIONS_JSON_NAME) as f:
            defs = json.load(f)
        self.assertEqual(defs[main.DEFINITIONS_PROMPTS_FIELDNAME], self.backup_result["prompts"])
        self.assertEqual(defs[main.DEFINITIONS_ENTRIES_FIELDNAME], self.backup_result["entries"])

    def test_leaves_name_id_and_backups_list_untouched(self):
        defs_path = self.jdir / main.DEFINITIONS_JSON_NAME
        with open(defs_path) as f:
            before = json.load(f)

        self._mutate_journal()
        main.revert_to_backup(self.backup_result["id"], self.jdir)

        with open(defs_path) as f:
            after = json.load(f)

        self.assertEqual(after[main.DEFINITIONS_NAME_FIELDNAME], before[main.DEFINITIONS_NAME_FIELDNAME])
        self.assertEqual(after[main.DEFINITIONS_ID_FIELDNAME], before[main.DEFINITIONS_ID_FIELDNAME])
        self.assertEqual(after[main.DEFINITIONS_BACKUPS_FIELDNAME], before[main.DEFINITIONS_BACKUPS_FIELDNAME])


def new_entry_with_input(jdir: Path, responses: list[str]):
    with patch("builtins.input", side_effect=responses):
        main.new_entry(jdir)


class TestNewEntry(TempDirTestCase):
    def setUp(self):
        super().setUp()
        new_journal_with_input(
            self.tmpdir, "myjournal",
            ["how was your day", "str", "hours slept", "int", "END"],
        )
        self.jdir = self.tmpdir / "myjournal"

    def _csv_rows(self):
        with open(self.jdir / main.DATA_CSV_NAME, newline="") as f:
            return list(csv.reader(f))

    def test_appends_a_row_with_a_generated_id_date_and_answers(self):
        new_entry_with_input(self.jdir, ["good day", "8"])

        rows = self._csv_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], ["id", "date", "how was your day", "hours slept"])
        self.assertEqual(rows[1][2:], ["good day", "8"])
        self.assertTrue(rows[1][0])
        dt.datetime.fromisoformat(rows[1][1])

    def test_records_entry_in_definitions_json(self):
        new_entry_with_input(self.jdir, ["good day", "8"])

        entries = main.list_entries(self.jdir)
        self.assertEqual(len(entries), 1)
        self.assertCountEqual(entries[0].keys(), ["id", "date"])
        dt.datetime.fromisoformat(entries[0]["date"])

        rows = self._csv_rows()
        self.assertEqual(entries[0]["id"], rows[1][0])
        self.assertEqual(entries[0]["date"], rows[1][1])

    def test_multiple_entries_accumulate_with_unique_ids(self):
        new_entry_with_input(self.jdir, ["good day", "8"])
        new_entry_with_input(self.jdir, ["bad day", "3"])

        rows = self._csv_rows()
        self.assertEqual(len(rows), 3)
        self.assertNotEqual(rows[1][0], rows[2][0])

        entries = main.list_entries(self.jdir)
        self.assertEqual([e["id"] for e in entries], [rows[1][0], rows[2][0]])

    def test_raises_on_invalid_int_answer(self):
        with self.assertRaises(TypeError):
            new_entry_with_input(self.jdir, ["good day", "not-a-number"])

    def test_does_not_write_row_or_entry_on_invalid_answer(self):
        with self.assertRaises(TypeError):
            new_entry_with_input(self.jdir, ["good day", "not-a-number"])

        rows = self._csv_rows()
        self.assertEqual(rows, [["id", "date", "how was your day", "hours slept"]])
        self.assertEqual(main.list_entries(self.jdir), [])

    def test_journal_with_no_prompts_records_id_only_row(self):
        new_journal_with_input(self.tmpdir, "noprompts", ["END"])
        jdir = self.tmpdir / "noprompts"

        new_entry_with_input(jdir, [])

        with open(jdir / main.DATA_CSV_NAME, newline="") as f:
            rows = list(csv.reader(f))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], main.list_entries(jdir)[0]["id"])


class TestRemoveEntry(TempDirTestCase):
    def setUp(self):
        super().setUp()
        new_journal_with_input(
            self.tmpdir, "myjournal",
            ["how was your day", "str", "END"],
        )
        self.jdir = self.tmpdir / "myjournal"
        new_entry_with_input(self.jdir, ["good day"])
        new_entry_with_input(self.jdir, ["bad day"])

        entries = main.list_entries(self.jdir)
        self.first_id = entries[0]["id"]
        self.second_id = entries[1]["id"]

    def _csv_rows(self):
        with open(self.jdir / main.DATA_CSV_NAME, newline="") as f:
            return list(csv.reader(f))

    def test_raises_if_entry_does_not_exist(self):
        with self.assertRaises(Exception):
            main.remove_entry(self.jdir, "doesnotexist")

    def test_does_not_mutate_anything_if_entry_does_not_exist(self):
        rows_before = self._csv_rows()
        entries_before = main.list_entries(self.jdir)

        with self.assertRaises(Exception):
            main.remove_entry(self.jdir, "doesnotexist")

        self.assertEqual(self._csv_rows(), rows_before)
        self.assertEqual(main.list_entries(self.jdir), entries_before)

    def test_removes_row_from_csv(self):
        main.remove_entry(self.jdir, self.first_id)

        rows = self._csv_rows()
        ids = [row[0] for row in rows[1:]]
        self.assertEqual(ids, [self.second_id])

    def test_removes_entry_from_definitions_json(self):
        main.remove_entry(self.jdir, self.first_id)

        entries = main.list_entries(self.jdir)
        self.assertEqual([e["id"] for e in entries], [self.second_id])

    def test_leaves_other_entries_untouched(self):
        main.remove_entry(self.jdir, self.first_id)

        rows = self._csv_rows()
        self.assertEqual(rows[0], ["id", "date", "how was your day"])
        self.assertEqual(rows[1][2], "bad day")

    def test_removing_last_entry_leaves_header_only_csv(self):
        main.remove_entry(self.jdir, self.first_id)
        main.remove_entry(self.jdir, self.second_id)

        self.assertEqual(self._csv_rows(), [["id", "date", "how was your day"]])
        self.assertEqual(main.list_entries(self.jdir), [])

    def test_removes_row_with_purely_numeric_id(self):
        # Regression: pandas infers an all-digit id column as int64, so
        # comparing against a string id would silently match nothing
        # unless the id column is explicitly read back as strings.
        jdir = self.tmpdir / "numeric_ids"
        jdir.mkdir()
        (jdir / main.BACKUPS_DIR_NAME).mkdir()
        with open(jdir / main.DATA_CSV_NAME, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "note"])
            writer.writerow(["1234567890", "first"])
            writer.writerow(["9876543210", "second"])
        with open(jdir / main.DEFINITIONS_JSON_NAME, "w") as f:
            json.dump({
                main.DEFINITIONS_NAME_FIELDNAME: "numeric_ids",
                main.DEFINITIONS_ID_FIELDNAME: "jid",
                main.DEFINITIONS_PROMPTS_FIELDNAME: [],
                main.DEFINITIONS_ENTRIES_FIELDNAME: [
                    {"id": "1234567890", "date": "2026-01-01"},
                    {"id": "9876543210", "date": "2026-01-02"},
                ],
                main.DEFINITIONS_BACKUPS_FIELDNAME: [],
            }, f)

        main.remove_entry(jdir, "1234567890")

        with open(jdir / main.DATA_CSV_NAME, newline="") as f:
            rows = list(csv.reader(f))
        self.assertEqual(rows, [["id", "note"], ["9876543210", "second"]])
        self.assertEqual([e["id"] for e in main.list_entries(jdir)], ["9876543210"])


class TestGetEntry(TempDirTestCase):
    def setUp(self):
        super().setUp()
        new_journal_with_input(
            self.tmpdir, "myjournal",
            ["how was your day", "str", "hours slept", "int", "END"],
        )
        self.jdir = self.tmpdir / "myjournal"
        new_entry_with_input(self.jdir, ["good day", "8"])
        new_entry_with_input(self.jdir, ["bad day", "3"])

        entries = main.list_entries(self.jdir)
        self.first = entries[0]
        self.second = entries[1]

    def test_returns_matching_entry_data(self):
        result = main.get_entry(self.jdir, self.first["id"])

        self.assertEqual(result["id"], self.first["id"])
        self.assertEqual(result["date"], self.first["date"])
        self.assertEqual(result["how was your day"], "good day")
        self.assertEqual(result["hours slept"], 8)

    def test_returns_correct_entry_among_multiple(self):
        result = main.get_entry(self.jdir, self.second["id"])

        self.assertEqual(result["id"], self.second["id"])
        self.assertEqual(result["how was your day"], "bad day")
        self.assertEqual(result["hours slept"], 3)

    def test_raises_if_entry_does_not_exist(self):
        with self.assertRaises(Exception):
            main.get_entry(self.jdir, "doesnotexist")

    def test_does_not_mutate_csv_or_definitions_json(self):
        with open(self.jdir / main.DATA_CSV_NAME, newline="") as f:
            csv_before = f.read()
        entries_before = main.list_entries(self.jdir)

        main.get_entry(self.jdir, self.first["id"])

        with open(self.jdir / main.DATA_CSV_NAME, newline="") as f:
            csv_after = f.read()
        self.assertEqual(csv_after, csv_before)
        self.assertEqual(main.list_entries(self.jdir), entries_before)

    def test_raises_on_definitions_csv_mismatch(self):
        main.remove_entry(self.jdir, self.first["id"])

        with open(self.jdir / main.DEFINITIONS_JSON_NAME) as f:
            defs = json.load(f)
        defs[main.DEFINITIONS_ENTRIES_FIELDNAME].append(self.first)
        with open(self.jdir / main.DEFINITIONS_JSON_NAME, "w") as f:
            json.dump(defs, f)

        with self.assertRaises(ValueError):
            main.get_entry(self.jdir, self.first["id"])


if __name__ == "__main__":
    unittest.main()
