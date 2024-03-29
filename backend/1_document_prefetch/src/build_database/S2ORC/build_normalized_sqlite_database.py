import subprocess
import threading
from tqdm import tqdm
import os
import numpy as np
from raw_sqlite_utils import SqliteClient as RawSqliteClient
import time
import json
from modules.paper_database.database_managers import SqliteClient
import shutil


# import os,sys,inspect
# current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
# root_dir = os.path.dirname(os.path.dirname(current_dir))
# sys.path.insert(0, root_dir)
# sys.path.insert(0, current_dir)


import argparse


### get all needed environment variables
ROOT_DATA_PATH = os.getenv("ROOT_DATA_PATH")
COLLECTION = os.getenv("COLLECTION")
NUM_PROCESSES = int(os.getenv("NUM_PROCESSES"))


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("-metadata_raw_sql_path", default = ROOT_DATA_PATH + "/raw/sqliteDB/metadata.db" )
    parser.add_argument("-pdf_parses_raw_sql_path", default = ROOT_DATA_PATH + "/raw/sqliteDB/pdf_parses.db" )
    parser.add_argument("-json_schema_path", default = "json_schema.json" )
    parser.add_argument("-output_file_name", default = ROOT_DATA_PATH + "/sqlite_database_buffer/normalized_data.jsonl" )
    parser.add_argument("-start", type = int, default = None )
    parser.add_argument("-size", type =int, default = None )
    parser.add_argument("-collection", default = COLLECTION )
    parser.add_argument("-batch_size", type = int, default = 5000 )
    parser.add_argument("-n_processes", type = int, default = NUM_PROCESSES )
    parser.add_argument("-output_sqlite_database_name", default = ROOT_DATA_PATH + "/sqlite_database_buffer/DB.db" )
    
    args = parser.parse_args()
    
    metadata_sql = RawSqliteClient( args.metadata_raw_sql_path )
    if args.start is None or args.size is None:
        print("No proper start and size value are specified, processing the whole document ...")
        print("Counting the total number of examples ...")
        args.start = 0
        args.size = metadata_sql.get_max_rowid(args.collection)
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
                    "normalize_raw_sqlite.py",
                    "-metadata_raw_sql_path", args.metadata_raw_sql_path,
                    "-pdf_parses_raw_sql_path", args.pdf_parses_raw_sql_path,
                    "-json_schema_path", args.json_schema_path ,
                    "-output_file_name", args.output_file_name,
                    "-output_file_name_suffix", "_%d"%( offset ),
                    "-start", offset,
                    "-size", min(num_of_examples_per_process, args.start + args.size -  offset ),
                    "-collection", args.collection,
                    "-batch_size", args.batch_size
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