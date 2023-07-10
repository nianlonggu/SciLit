import subprocess
import threading
import os
import numpy as np
import time
import json
from tqdm import tqdm

import os,sys,inspect
from modules.paper_database.database_managers import SqliteClient

import shutil

import argparse


ROOT_DATA_PATH = os.getenv("ROOT_DATA_PATH")
COLLECTION = os.getenv("COLLECTION")
NUM_PROCESSES = int(os.getenv("NUM_PROCESSES"))


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("-raw_database_path", default = ROOT_DATA_PATH + "/raw/json/" )
    parser.add_argument("-json_schema_path", default = "./json_schema.json" )
    parser.add_argument("-output_file_name", default =  ROOT_DATA_PATH + "/sqlite_database_buffer/normalized_data.jsonl" )
    parser.add_argument("-start", type = int, default = None )
    parser.add_argument("-size", type =int, default = None )
    parser.add_argument("-collection", default = COLLECTION )
    parser.add_argument("-batch_size", type = int, default = 5000 )
    parser.add_argument("-n_processes", type = int, default = NUM_PROCESSES )
    parser.add_argument("-output_sqlite_database_name", default = ROOT_DATA_PATH + "/sqlite_database_buffer/DB.db")
    
    args = parser.parse_args()

    
    if args.start is None or args.size is None:
        print("No proper start and size value are specified, processing the whole document ...")
        print("Counting the total number of examples ...")
        
        all_json_files = []
        for root , _, files in os.walk(args.raw_database_path):
            for file_name in files:
                if file_name.endswith(".json"):
                    all_json_files.append( root + "/" + file_name )
        max_rowid = len(all_json_files)
                        
        print("max_rowid:", max_rowid)
        
        args.start = 0
        args.size = max_rowid
    else:
        try:
            assert args.start is not None and args.size is not None
            assert args.start >= 0 and args.size >= 0
        except:
            print("Error: Wrong start and size value were provided!")
            os.sys.exit(1)
            
    output_folder = os.path.dirname( args.output_file_name )
    try:
        shutil.rmtree( output_folder )
    except:
        pass
    os.makedirs( output_folder )
        
    
    output_sqlite_database_folder = os.path.dirname( args.output_sqlite_database_name )
    try:
        shutil.rmtree( output_sqlite_database_folder )
    except:
        pass
    os.makedirs( output_sqlite_database_folder )
        
    
    num_of_examples_per_process = int( np.ceil( args.size / args.n_processes ) )
    print("Start multiple subprocesses ...")
    
    threads = []
    for offset in range( args.start, args.start + args.size, num_of_examples_per_process ):
        t = threading.Thread( target = subprocess.run, args = ( 
                list(map( str, [
                    "python",
                    "normalize_raw_database.py",
                    "-raw_database_path", args.raw_database_path,
                    "-json_schema_path", args.json_schema_path,
                    "-output_file_name", args.output_file_name,
                    "-output_file_name_suffix", "_%d"%( offset ),
                    "-start", offset,
                    "-size", min(num_of_examples_per_process, args.start + args.size -  offset )
                   ] ) ) ,
             )  )
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    
    
    print("Dumping to the final sqlite database, this may take time ...")
    
    final_sql = SqliteClient( args.output_sqlite_database_name )
    
    output_base_name = os.path.basename( args.output_file_name )
    flist =[ output_folder +"/"+fname for fname in os.listdir( output_folder ) if fname.startswith(output_base_name+"_") ]
    flist.sort( key = lambda x:int(x.split("_")[-1]) )
    
    paper_buffer = []
    for fname in flist:
        print(fname)
        with open( fname ,"r" ) as f:
            for line in f:
                line_data = json.loads(line)
                paper_buffer.append(line_data)
                
                if len(paper_buffer) >= args.batch_size:
                    final_sql.insert_papers( paper_buffer, args.collection )
                    paper_buffer = []
        os.remove( fname )
            
    if len(paper_buffer)>0:
        final_sql.insert_papers( paper_buffer, args.collection )
        paper_buffer = []
                
    print("All Done!")