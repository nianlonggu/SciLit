import subprocess
import threading
import os,sys
import json
from tqdm import tqdm
import time
import numpy as np
import shutil

import pickle

from modules.paper_database.database_managers import SqliteClient
from modules.tokenizer.tokenizer import SentenceTokenizer
from modules.ranking.rankers import Sent2vecEncoder

import argparse


ROOT_DATA_PATH = os.getenv("ROOT_DATA_PATH")
NUM_PROCESSES = int(os.getenv("NUM_PROCESSES"))
NUM_EMBEDDING_INDEX_SHARDS = int(os.getenv("NUM_EMBEDDING_INDEX_SHARDS"))

SENT2VEC_MODEL_PATH = os.getenv("SENT2VEC_MODEL_PATH")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-db_address", default = ROOT_DATA_PATH + "/sqlite_database/DB.db" )
    parser.add_argument("-embedding_file_name", default = ROOT_DATA_PATH + "/ranking_buffer/embedding_index/embedding_index.db")
    parser.add_argument("-text_encoder_model_path", default = SENT2VEC_MODEL_PATH )
    parser.add_argument("-start", type = int, default = None)
    parser.add_argument("-size", type = int, default = None)
    parser.add_argument("-n_processes", type = int, default = NUM_PROCESSES )
    parser.add_argument("-n_docs_per_process", type = int, default = None )
    
    args = parser.parse_args()
    
    sqlite_client = SqliteClient(db_address = args.db_address )
    assert len(sqlite_client.collections) == 1
    args.collection = list(sqlite_client.collections)[0]
    
    max_rowid = sqlite_client.get_max_rowid( args.collection )
    
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
    embedding_folder = os.path.dirname( args.embedding_file_name )
    try:
        shutil.rmtree(embedding_folder)
    except:
        pass
    os.makedirs( embedding_folder )
            

    print("Start multiple subprocesses ...")
    
    threads = []
    for count, offset in enumerate(range( args.start, args.start + args.size, args.n_docs_per_process )):
        t = threading.Thread( target = subprocess.run, args = ( 
                list(map( str, [
                    "python",
                    "compute_embedding.py",
                    "-db_address", args.db_address,
                    "-collection", args.collection,
                    "-embedding_file_name", args.embedding_file_name,
                    "-embedding_file_name_suffix", "_%d"%( count ),
                    "-text_encoder_model_path", args.text_encoder_model_path,
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
        
    ## adjust the number of shards for embedding index, as specified by NUM_EMBEDDING_INDEX_SHARDS
    ## This is needed because for CPU approximate nearest search, we may need more shards, but for GPU brute-force nearest neighbor search, we only need one or two shards, since too many shards will increase the GPU memory overhead.
    
    print("Adjusting number of shards for embedding index ...")
    subprocess.run( ["python", "adjust_num_shards_for_embedding_index.py",
                     "-embedding_index_folder", ROOT_DATA_PATH + "/ranking_buffer/embedding_index/",
                     "-embedding_index_name_prefix", "embedding_index.db_",
                     "-num_shards", str( NUM_EMBEDDING_INDEX_SHARDS )
                    ] )
    
    print("All Done!")

    