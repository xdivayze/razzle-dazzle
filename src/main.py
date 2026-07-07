import argparse
import os 
from pathlib import Path



def add_arguments(parser: argparse.ArgumentParser):
    parser.add_argument("journal_name",nargs="?", default=None, help = "journal name")
 
    parser.add_argument("--backup", action="store_true", help="create a back up of the provided journal")
    parser.add_argument("--new-entry", action="store_true", help="insert a new entry to the journal")
    parser.add_argument("--list-journals", action="store_true", help="lists the journals in the current base directory")
    parser.add_argument("--base-directory", action="store_true", help="print the current base directory")
    parser.add_argument("--remove-journal", action="store_true", help="remove the specified journal and delete its contents")
    parser.add_argument("--list-backups", action="store_true", help="list the backups for journal")
    parser.add_argument("--list-entries", action="store_true", help="list entries for journal")

    parser.add_argument("--new", type=str,metavar="JOURNAL NAME", help="create a new journal" )
    parser.add_argument("--change-base-directory",metavar="DIRECTORY", type=str, help="change the base directory")
    parser.add_argument("--remove-entry", metavar="ENTRY IDENTIFIER", type=str, help="remove the specified entry from the chosen journal")
    parser.add_argument("--revert-to-backup", metavar="BACKUP IDENTIFIER", type=str, help="revert to specified backup")


def new_journal(dir: Path, journal_name: str):
    dir = dir.resolve();
    
    if (os.listdir(dir).count(journal_name)):
        raise Exception( "Journal already exists. Aborting...")
    
    dir = dir / journal_name
    os.mkdir(dir)
    open(dir/"data.csv" , "a").close()
    open(dir/"prompts.json", "a").close()
    
    os.mkdir(dir/"backups")


def argument_handler(args)->str:
    pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    
    add_arguments(parser)    
    args = parser.parse_args()
    
    base_dir:str = argument_handler(args)
        

    



    
