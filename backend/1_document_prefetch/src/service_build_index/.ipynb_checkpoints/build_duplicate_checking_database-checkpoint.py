import os,sys
from tqdm import tqdm

from modules.paper_database.database_managers import SqliteClient
from modules.duplicate_checking.duplicate_checker import DuplicateChecker

import shutil

import argparse


ROOT_DATA_PATH = os.getenv("ROOT_DATA_PATH")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()    
    parser.add_argument( "-db_address", default = ROOT_DATA_PATH + "/sqlite_database/DB.db" )
    parser.add_argument( "-duplicate_checking_database_path", default = ROOT_DATA_PATH + "/duplicate_checking_buffer/data.db" )
    parser.add_argument( "-batch_size", type = int, default = 500000 )
    args = parser.parse_args()
    
    
    ## deal with missing folders
    data_folder = os.path.dirname( args.duplicate_checking_database_path )
    try:
        shutil.rmtree(data_folder)
    except:
        pass
    os.makedirs( data_folder )
    
    
    duplicate_checker = DuplicateChecker( args.duplicate_checking_database_path )
    sql = SqliteClient( args.db_address )
    
    assert len(sql.collections) == 1
    args.collection = list(sql.collections)[0]
    
    max_row_id = sql.get_max_rowid( args.collection )
    data_buffer = []
    for count in tqdm(range(0,max_row_id)):
        idx = count +1
        paper_info = sql.get_papers( [ { "collection":args.collection, "id_field":"id_int", "id_type":"int","id_value":idx } ],
                                     {"Title":1, "Author":1, "MD5":1, "DOI":1, "RequireIndexing":1}
                                   )[0]
        if paper_info is None or not paper_info.get("RequireIndexing", True):
            continue
        
        collection = args.collection
        id_int = idx
        md5 = paper_info.get( "MD5", "" )
        doi = paper_info["DOI"]
        title = paper_info["Title"]
        if len( paper_info["Author"] ) >0:
            first_author = paper_info["Author"][0]["GivenName"] + " " + paper_info["Author"][0]["FamilyName"] 
        else:
            first_author = ""
            
        data_buffer.append( [collection, id_int, md5, doi, title, first_author] )
        
        if len(data_buffer) >= args.batch_size:
            duplicate_checker.update(data_buffer)
            data_buffer = []

    if len(data_buffer)> 0:
        duplicate_checker.update(data_buffer)
        data_buffer = []
    
    print("All Done!")
    