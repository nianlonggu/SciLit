import argparse
import json
import requests
from datetime import datetime
from flask import Flask, jsonify, abort, make_response, request, Response
from flask_cors import CORS
import os
import shutil
import subprocess
import threading
from glob import glob

from modules.paper_database.database_managers import SqliteClient
import numpy as np
from tqdm import tqdm

import time
from modules.service_utils.utils import wait_for_service
            
# Make Flask application
app = Flask(__name__)
CORS(app)


ROOT_DATA_PATH = os.getenv("ROOT_DATA_PATH")
SERVICE_SUFFIX = os.getenv("SERVICE_SUFFIX")

ADDRESS_SERVICE_PAPER_DATABASE = f"http://document_prefetch_service_paper_database_{SERVICE_SUFFIX}:8060"
ADDRESS_SERVICE_RANKING = f"http://document_prefetch_service_ranking_{SERVICE_SUFFIX}:8060"
ADDRESS_SERVICE_FAST_METADATA_SEARCH = f"http://document_prefetch_service_fast_metadata_search_{SERVICE_SUFFIX}:8060"


def fast_metadata_search( paper_metadata_list, address = ADDRESS_SERVICE_FAST_METADATA_SEARCH + "/check-duplicate"):
    try:
        res = requests.post(
            address,
            data = json.dumps({"paper_list":paper_metadata_list}),
            headers = {"Content-Type":"application/json", 'Connection': 'close'}
        ).json()["response"]
    except:
        res = [ list() for _ in range(len(paper_metadata_list)) ]
    return res


def update_database():
    global args
    
    assert os.path.exists( args.sqlite_database_buffer_path ) or os.path.exists( args.sqlite_database_path )
    
    if not os.path.exists( args.sqlite_database_buffer_path ):
        print("Buffer %s does not exist!" %( args.sqlite_database_buffer_path ) )
    elif not os.path.exists( args.sqlite_database_path ):
        folder_name = os.path.dirname( args.sqlite_database_path )
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)
        shutil.move( args.sqlite_database_buffer_path, folder_name )
        print("Database file %s does not exist. Directly copy the buffered database file!"%( args.sqlite_database_buffer_path ) )
    else:
        ## Update the sqlite_database with the buffered sqlite database, this needs the duplicate checking function
    
        print("Both sqlite database and buffered sqlite database exist, updating the sqlite database with the buffered one ...")
        buffered_paper_db = SqliteClient( args.sqlite_database_buffer_path )
        paper_db = SqliteClient( args.sqlite_database_path )
                
        assert len(buffered_paper_db.collections) == 1 and buffered_paper_db.collections == paper_db.collections
        collection = list(buffered_paper_db.collections)[0]
        
        print("Before updating:")
        print("Number of recording in the current database:", paper_db.get_max_rowid( collection ) )
        print("Number of recording in the buffered database:", buffered_paper_db.get_max_rowid( collection ) )
        
        all_buffered_ids = np.arange( buffered_paper_db.get_max_rowid( collection ) ) + 1
        batch_size = 1000
        for pos in tqdm(range(0, len(all_buffered_ids), batch_size )):
            buffered_ids_batch = all_buffered_ids[pos:pos+batch_size]
            buffered_papers_batch = buffered_paper_db.get_papers(
                [ {"collection":collection, "id_field":"id_int", "id_value":id_value} for id_value in buffered_ids_batch ]
            )
            
            #### It can happen that fast_metadata_search is not running when this part of code is running.
            #### In that case, we just return a list of empty lists, which denotes "not find duplicates"
            match_res_batch = fast_metadata_search(
                [
                    {
                        "Title":paper.get("Title", ""),
                        "FirstAuthor":paper["Author"][0]["GivenName"] + " " + paper["Author"][0]["FamilyName"] if len(paper.get("Author",[])) > 0 else "",
                        "DOI":paper.get("DOI", ""),
                        "MD5":paper.get("MD5", "")
                    }for paper in buffered_papers_batch
                ]
            )
            
            new_papers = []
            for paper, match_res in zip( buffered_papers_batch, match_res_batch ):
                if len(match_res) == 0:
                    new_papers.append( paper )
                    
            paper_db.insert_papers( new_papers, collection )
            
        print("After updating:")
        print("Number of recording in the current database:", paper_db.get_max_rowid( collection ) )
        print("Number of recording in the buffered database:", buffered_paper_db.get_max_rowid( collection ) )
        
    ## delete the buffered sqlite database, since it is useless after updating the main sqlite database
    try:
        shutil.rmtree( os.path.dirname( args.sqlite_database_buffer_path ) )
    except:
        pass


def build_index_pipeline( reboot_services_after_building = True ):
    update_database()
    subprocess.run( ["python", "build_inverted_index.py"] )
    subprocess.run( ["python", "build_embedding_index.py"] )
    subprocess.run( ["python", "build_duplicate_checking_database.py"] )
    
    ## replace the old index with the new index
    try:
        shutil.rmtree( ROOT_DATA_PATH + "/ranking" )
    except:
        pass
    shutil.move( ROOT_DATA_PATH + "/ranking_buffer", ROOT_DATA_PATH + "/ranking" )
    
    try:
        shutil.rmtree( ROOT_DATA_PATH + "/duplicate_checking" )
    except:
        pass
    shutil.move( ROOT_DATA_PATH + "/duplicate_checking_buffer", ROOT_DATA_PATH + "/duplicate_checking" )
    
    if reboot_services_after_building:
        wait_for_service( ADDRESS_SERVICE_PAPER_DATABASE )
        print("Rebooting paper database service ...")
        try:
            print(requests.post( ADDRESS_SERVICE_PAPER_DATABASE + "/reboot", 
                   data = json.dumps({}), 
                   headers = {"Content-Type":"application/json"} ).json()["response"])
        except:
            print("fail")
    
        wait_for_service( ADDRESS_SERVICE_RANKING )
        print("Rebooting ranking service ...")
        try:
            print(requests.post( ADDRESS_SERVICE_RANKING + "/reboot", 
                   data = json.dumps({}), 
                   headers = {"Content-Type":"application/json"} ).json()["response"])
        except:
            print("fail")
    
        wait_for_service( ADDRESS_SERVICE_FAST_METADATA_SEARCH )
        print("Rebooting fast metadata search service ...")
        try:
            print(requests.post( ADDRESS_SERVICE_FAST_METADATA_SEARCH + "/reboot", 
                   data = json.dumps({}), 
                   headers = {"Content-Type":"application/json"} ).json()["response"])
        except:
            print("fail")
            

@app.route('/build-index', methods=['POST'])
def build_index():
    global sem
    
    sem.acquire()
    
    try:
        build_index_pipeline(reboot_services_after_building = True)
        results = {"response":"success"}
    except:
        results = {"response":"fail"}
    
    sem.release()
    
    return json.dumps(results), 201
    
    
    
if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()    
    parser.add_argument( "-flask_port", type = int, default = 8060 )
    parser.add_argument( "-sqlite_database_buffer_path", default = ROOT_DATA_PATH + "/sqlite_database_buffer/DB.db" )
    parser.add_argument( "-sqlite_database_path", default = ROOT_DATA_PATH + "/sqlite_database/DB.db" )
    args = parser.parse_args()

    headers = {"Content-Type": "application/json", 'Connection': 'close'}
    
    ## If the files required for paper database, inverted index, embedding index, and duplicate checking are missing, then initialize the system by running build_index_pipeline()
    if not os.path.exists( args.sqlite_database_path ) or \
        len( glob( ROOT_DATA_PATH + "/ranking/inverted_index/inverted_index.db*" ) ) == 0 or \
        len( glob( ROOT_DATA_PATH + "/ranking/embedding_index/embedding_index.db*" ) ) == 0 or \
        not os.path.exists( ROOT_DATA_PATH + "/duplicate_checking/data.db" ):
    
        print("Index system has not been built. Initializing the index ...")
        
        ## In this case, the service for paper database, ranking and duplicate checking cannot be running, so we cannot signal them to reboot by sending http requests. Therefore, we set reboot_services_after_building to False
        build_index_pipeline(reboot_services_after_building = False)
    
    
    print("\n\nWaiting for requests...")
    sem = threading.Semaphore()

    app.run(host='0.0.0.0', port=args.flask_port, threaded = True)

