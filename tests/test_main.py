"""Tests for the journal-management features implemented so far in src/main.py.

Run with: python -m unittest discover -s tests
"""
import argparse
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

    def test_new_journal_is_immediately_listable(self):
        new_journal_with_input(self.tmpdir, "myjournal", ["END"])
        jdir = self.tmpdir / "myjournal"

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

    def test_empty_base_dir_returns_empty_set(self):
        self.assertEqual(main.list_journals(self.tmpdir), set())

    def test_skips_dirs_without_definitions_file(self):
        (self.tmpdir / "not_a_journal").mkdir()
        self.assertEqual(main.list_journals(self.tmpdir), set())

    def test_skips_journals_without_id_field(self):
        self._write_definitions(self.tmpdir / "no_id", {})
        self.assertEqual(main.list_journals(self.tmpdir), set())

    def test_returns_name_id_pairs(self):
        self._write_definitions(self.tmpdir / "j1", {"id": "abc123"})
        self._write_definitions(self.tmpdir / "j2", {"id": "def456"})
        self.assertEqual(
            main.list_journals(self.tmpdir),
            {("j1", "abc123"), ("j2", "def456")},
        )


class TestListEntries(TempDirTestCase):
    def test_raises_if_definitions_file_missing(self):
        jdir = self.tmpdir / "myjournal"
        jdir.mkdir()
        with self.assertRaises(Exception):
            main.list_entries(jdir)

    def test_returns_entries_field(self):
        jdir = self.tmpdir / "myjournal"
        jdir.mkdir()
        entries = [{"id": "1", "hash": "aaa", "date": "2026-01-01"}]
        with open(jdir / main.DEFINITIONS_JSON_NAME, "w") as f:
            json.dump({main.DEFINITIONS_ENTRIES_FIELDNAME: entries}, f)
        self.assertEqual(main.list_entries(jdir), entries)


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
        self.assertEqual(main.list_backups(jdir), backups)


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

    def test_creates_backup_file_with_matching_hash(self):
        result = main.backup(self.jdir)

        backup_files = list((self.jdir / main.BACKUPS_DIR_NAME).iterdir())
        self.assertEqual(len(backup_files), 1)
        backup_file = backup_files[0]
        self.assertEqual(backup_file.name, f"{result['id']}.csv")
        self.assertEqual(backup_file.read_text(), "a,b,c\n1,2,3\n")

        expected_hash = hashlib.sha256(backup_file.read_bytes()).hexdigest()
        self.assertEqual(result["hash"], expected_hash)

    def test_returns_id_hash_and_date(self):
        result = main.backup(self.jdir)
        self.assertCountEqual(result.keys(), ["id", "hash", "date"])
        self.assertTrue(result["id"])
        self.assertTrue(result["hash"])
        dt.datetime.fromisoformat(result["date"])

    def test_backup_is_recorded_in_definitions_json(self):
        result = main.backup(self.jdir)
        self.assertEqual(main.list_backups(self.jdir), [result])

    def test_multiple_backups_accumulate_with_unique_ids(self):
        first = main.backup(self.jdir)
        second = main.backup(self.jdir)

        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(main.list_backups(self.jdir), [first, second])

        backup_names = {p.name for p in (self.jdir / main.BACKUPS_DIR_NAME).iterdir()}
        self.assertEqual(backup_names, {f"{first['id']}.csv", f"{second['id']}.csv"})


if __name__ == "__main__":
    unittest.main()
