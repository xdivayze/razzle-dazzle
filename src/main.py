import argparse
from typing import IO, cast 
import json
import os 
from pathlib import Path

CONFIG_BASE_DIR_NAME = "base_directory"

DEFINITIONS_JSON_NAME = "definitions.json"
DEFINITIONS_ENTRIES_FIELDNAME = "entries"

DATA_CSV_NAME = "data.csv"
BACKUPS_DIR_NAME = "backups"
#TODO get specific entry
#TODO add show backup details
def add_arguments(parser: argparse.ArgumentParser):
    #positional args
    parser.add_argument("journal_name",nargs="?", default=None, help = "journal name")
    #true/false args
    
    #does stuff
    parser.add_argument("--backup", action="store_true", help="create a back up of the provided journal")
    parser.add_argument("--new-entry", action="store_true", help="insert a new entry to the journal")
    parser.add_argument("--remove-journal", action="store_true", help="remove the specified journal and delete its contents")
    
    #prints stuff
    parser.add_argument("--list-backups", action="store_true", help="list the backups for journal")
    parser.add_argument("--list-entries", action="store_true", help="list entries for journal")
    parser.add_argument("--list-journals", action="store_true", help="lists the journals in the current base directory")
    parser.add_argument("--print-base-directory", action="store_true", help="print the current base directory")

    #field args
    #no journal name required
    parser.add_argument("--new", type=str,metavar="JOURNAL NAME", help="create a new journal" )
    parser.add_argument("--change-base-directory",metavar="DIRECTORY", type=str, help="change the base directory")
    
    #journal name required
    parser.add_argument("--remove-entry", metavar="ENTRY IDENTIFIER", type=str, help="remove the specified entry from the chosen journal")
    parser.add_argument("--revert-to-backup", metavar="BACKUP IDENTIFIER", type=str, help="revert to specified backup")


def new_journal(dir: Path, journal_name: str):
    dir = dir.resolve();
    
    if (os.listdir(dir).count(journal_name)):
        raise Exception( "Journal already exists. Aborting...")
    
    dir = dir / journal_name
    os.mkdir(dir)
    open(dir/DATA_CSV_NAME , "a").close()
    open(dir/DEFINITIONS_JSON_NAME, "a").close()
    os.mkdir(dir/BACKUPS_DIR_NAME)

#definitions.json
#journal name
#id: str
#prompts: [{str, datatype}]
#entries: [{id, hash, date}]
#backups: [{id, hash, date}]

#returns journal name, journal id pair
def list_journals(base_dir: Path)->set[tuple[str, str]]:
    jpairs: set[tuple[str, str]] = set()
    for i in base_dir.iterdir():
        definitions_file = i/DEFINITIONS_JSON_NAME
        if not definitions_file.exists:
            continue
        with open(definitions_file, "r") as f:
            journal_cfg = json.load(f)
        jid = journal_cfg.get("id")
        if not jid:
            continue
        jpairs.add((i.name, jid))
    return jpairs

#returns id, hash, date
def list_entries(journal_name: str, base_dir: Path)-> set[tuple[str, str, str]]:
    jdir =base_dir/journal_name
    if not jdir.exists():
        raise Exception("journal doesn't exist in the base directory")
    
    jdir_definitions = jdir/DEFINITIONS_JSON_NAME
    if not jdir_definitions.exists():
        raise Exception("journal directory doesn't have definitions file")
    
    with open(jdir_definitions, "r") as f:
        defs = json.load(f)
    return defs.get(DEFINITIONS_ENTRIES_FIELDNAME);
    
def argument_handler( args, config_handle: IO[str], config: dict[str, object]| None ):
    if config is None:
            config = cast(dict[str, object],json.load(config_handle))
    
    ndir = Path(args.change_base_directory).resolve()
    if ndir:
        os.mkdir(ndir)
        config[CONFIG_BASE_DIR_NAME] = ndir
    
    base_dir = Path(str(config[CONFIG_BASE_DIR_NAME])).resolve()
    
    if args.print_base_directory:
        print(f"BASE DIRECTORY: {base_dir}")

    jname = args.journal_name
    if jname:
        if args.revert_to_backup:
            pass
        if args.remove_entry:
            pass
        if args.backup:
            pass
        if args.new_entry:
            pass
        if args.remove_journal:
            pass
        if args.list_backups:
            pass
        if args.list_entries:
            print(f"LISTING ENTRIES ON JOURNAL: {jname}...\n{list_entries(jname, base_dir)}")
        if args.list_journals:
            print(f"LISTING JOURNALS...\n{list_journals(base_dir)}");
    if args.new:
        pass

    json.dump(config, config_handle)
    return str(base_dir)

#config.json
#base_directory: str

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    
    add_arguments(parser)    
    args = parser.parse_args()
    
    fdir = Path(__file__).resolve().parent
    config_path = fdir/"config.json"
    fallback_base_dir = config_path/".data"

    config = None
    with open(config_path, "w") as f:
        if not config_path.exists():
            f.write(f"""
                    {{
                        {CONFIG_BASE_DIR_NAME}: {fallback_base_dir},
                    }}
                    """)
            os.mkdir(fallback_base_dir)
        else:
            config = json.load(f)
            if not config[CONFIG_BASE_DIR_NAME]:
                f.write(f"""
                    {{
                        {CONFIG_BASE_DIR_NAME}: {fallback_base_dir},
                    }}
                    """)
                os.mkdir(fallback_base_dir)   
    
    base_dir:str = argument_handler(args, f, config)
    f.close()

    



    
