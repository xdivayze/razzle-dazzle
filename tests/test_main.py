"""Tests for the journal-management features implemented so far in src/main.py.

Run with: python -m unittest discover -s tests
"""
import argparse
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import main


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
        main.new_journal(self.tmpdir, "myjournal")
        jdir = self.tmpdir / "myjournal"

        self.assertTrue(jdir.is_dir())
        self.assertTrue((jdir / main.DATA_CSV_NAME).is_file())
        self.assertTrue((jdir / main.DEFINITIONS_JSON_NAME).is_file())
        self.assertTrue((jdir / main.BACKUPS_DIR_NAME).is_dir())

    def test_writes_valid_definitions_json(self):
        main.new_journal(self.tmpdir, "myjournal")
        jdir = self.tmpdir / "myjournal"

        with open(jdir / main.DEFINITIONS_JSON_NAME) as f:
            defs = json.load(f)

        self.assertEqual(defs[main.DEFINITIONS_NAME_FIELDNAME], "myjournal")
        self.assertTrue(defs[main.DEFINITIONS_ID_FIELDNAME])
        self.assertEqual(defs[main.DEFINITIONS_PROMPTS_FIELDNAME], [])
        self.assertEqual(defs[main.DEFINITIONS_ENTRIES_FIELDNAME], [])
        self.assertEqual(defs[main.DEFINITIONS_BACKUPS_FIELDNAME], [])

    def test_raises_if_journal_already_exists(self):
        main.new_journal(self.tmpdir, "myjournal")
        with self.assertRaises(Exception):
            main.new_journal(self.tmpdir, "myjournal")

    def test_new_journal_is_immediately_listable(self):
        main.new_journal(self.tmpdir, "myjournal")
        jdir = self.tmpdir / "myjournal"

        journals = main.list_journals(self.tmpdir)
        self.assertEqual(len(journals), 1)
        name, jid = next(iter(journals))
        self.assertEqual(name, "myjournal")
        self.assertTrue(jid)

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


if __name__ == "__main__":
    unittest.main()
