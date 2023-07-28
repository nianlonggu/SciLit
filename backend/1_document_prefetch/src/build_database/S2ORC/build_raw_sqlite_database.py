from raw_sqlite_utils import SqliteClient
import numpy as np
import json
import time
import os
from tqdm import tqdm
import re
import argparse

def dump_to_sqlite( folder, db_path, buffer_size, paper_id_matcher, collection ):
    db_path_dir_name = os.path.dirname(db_path)
    if not os.path.exists( db_path_dir_name ):
        os.makedirs( db_path_dir_name )

    flist = [folder + "/" + _ for _ in  os.listdir(folder) if _.endswith(".jsonl") ]
    flist.sort( key = lambda x:int( x.split("_")[-1].split(".")[0] ) )

    sql_client = SqliteClient(db_path)

    paper_list_buffer = []
    for fname in flist:
        print(fname)
        with open( fname,"r" ) as f:
            for line in tqdm(f):                
                paper_id = int(paper_id_matcher.findall(line[:50])[0])
                paper_list_buffer.append( { "paper_id":paper_id,"Text":line } )
                if len(paper_list_buffer) >= buffer_size:
                    sql_client.insert_papers( collection, paper_list_buffer )
                    paper_list_buffer = []
    if len( paper_list_buffer ) > 0:
        sql_client.insert_papers( collection, paper_list_buffer )
        paper_list_buffer = []
        
ROOT_DATA_PATH = os.getenv("ROOT_DATA_PATH")
COLLECTION = os.getenv("COLLECTION")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-metadata_jsonl_folder", default = ROOT_DATA_PATH + "/raw/metadata/" )
    parser.add_argument("-metadata_db_path", default = ROOT_DATA_PATH + "/raw/sqliteDB/metadata.db")
    parser.add_argument("-pdf_parses_jsonl_folder", default = ROOT_DATA_PATH + "/raw/pdf_parses/")
    parser.add_argument("-pdf_parses_db_path", default = ROOT_DATA_PATH + "/raw/sqliteDB/pdf_parses.db")
    parser.add_argument("-buffer_size", type = int, default = 1000 )
    parser.add_argument("-collection", default = COLLECTION)
    args = parser.parse_args()


    paper_id_matcher = re.compile('(?<="paper_id": ")\d*(?=")') 

    print("Converting metadata raw jsonl files to a single metadata sqlite ...")
    dump_to_sqlite( args.metadata_jsonl_folder, args.metadata_db_path, args.buffer_size, paper_id_matcher, args.collection )

    print("Converting pdf_parses raw jsonl files to a single metadata sqlite ...")
    dump_to_sqlite( args.pdf_parses_jsonl_folder, args.pdf_parses_db_path, args.buffer_size, paper_id_matcher, args.collection )
        
    print("All Done!")
        