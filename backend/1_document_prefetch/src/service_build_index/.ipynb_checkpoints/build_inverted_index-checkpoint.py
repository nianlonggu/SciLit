import subprocess
import threading
import os,sys
from modules.paper_database.database_managers import SqliteClient
import json
from tqdm import tqdm
import dateparser
from nameparser import HumanName
import time
import threading 

import shutil

import array
import numpy as np
from more_itertools import unique_everseen

from modules.tokenizer.tokenizer import SentenceTokenizer
from sqlitedict import SqliteDict
import argparse


ROOT_DATA_PATH = os.getenv("ROOT_DATA_PATH")
NUM_INVERTED_INDEX_SHARDS = int(os.getenv("NUM_INVERTED_INDEX_SHARDS"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-db_address", default = ROOT_DATA_PATH + "/sqlite_database/DB.db")
    parser.add_argument("-inv_idx_file_name", default = ROOT_DATA_PATH + "/ranking_buffer/inverted_index/inverted_index.db")
    parser.add_argument("-commit_per_num_of_keys", type = int, default = 10000000)
    parser.add_argument("-overwrite", type = int, default = 1)
    parser.add_argument("-start", type = int, default = None)
    parser.add_argument("-size", type = int, default = None)
    parser.add_argument("-n_processes", type = int, default = NUM_INVERTED_INDEX_SHARDS )
    parser.add_argument("-n_docs_per_process", type = int, default = None )
    
    args = parser.parse_args()

    sqlite_client = SqliteClient(db_address= args.db_address )
    assert len(sqlite_client.collections) == 1
    args.collection = list(sqlite_client.collections)[0]
    
    max_rowid = sqlite_client.get_max_rowid(args.collection)
    
    if args.start is None or args.size is None:
        print("No proper start and size value are specified, processing the whole document ...")
        print("Counting the total number of examples ...")
        args.start = 0
        args.size = max_rowid
    else:
        try:
            assert args.start is not None and args.size is not None
            assert args.start >= 0 and args.size >= 0
        except:
            print("Error: Wrong start and size value were provided!")
            os.sys.exit(1)
    args.size = min( args.size, max_rowid - args.start )
    
    ## determining the n_docs per process
    if args.n_docs_per_process is None:
        args.n_docs_per_process = int(np.ceil( args.size / args.n_processes))
    
    ## deal with missing folders
    inv_idx_folder = os.path.dirname( args.inv_idx_file_name )
    try:
        shutil.rmtree(inv_idx_folder)
    except:
        pass
    os.makedirs( inv_idx_folder )
    
        
    print("Start multiple subprocesses ...")
    
    threads = []
    for count, offset in enumerate(range( args.start, args.start + args.size, args.n_docs_per_process )):
        t = threading.Thread( target = subprocess.run, args = ( 
                list(map( str, [
                    "python",
                    "compute_inverted_index.py",
                    "-db_address", args.db_address,
                    "-collection", args.collection,
                    "-inv_idx_file_name", args.inv_idx_file_name,
                    "-inv_idx_file_name_suffix", "_%d"%( count ),
                    "-commit_per_num_of_keys", args.commit_per_num_of_keys,
                    "-overwrite", args.overwrite,
                    "-start", offset,
                    "-size", min(args.n_docs_per_process, args.start + args.size -  offset )
                   ] ) ) ,
             )  )
        threads.append(t)
        t.start()
        if len( threads ) >= args.n_processes:
            for t in threads:
                t.join()
            threads = []
    
    ## make sure all processes have been finished!
    for t in threads:
        t.join()
    
    print("All Done!")