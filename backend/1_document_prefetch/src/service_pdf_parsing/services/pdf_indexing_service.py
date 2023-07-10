import argparse
import json
import requests
from datetime import datetime
from flask import Flask, jsonify, abort, make_response, request, Response
from flask_cors import CORS


import uuid
import os
import subprocess
import threading
import shutil
import hashlib
import base64

from normalization_utils import DocumentNormalizer
from modules.paper_database.database_managers import SqliteClient

import time
import socket
from urllib.parse import urlparse


# Make Flask application
app = Flask(__name__)
CORS(app)

ROOT_DATA_PATH = os.getenv("ROOT_DATA_PATH")
PDF2JSON_HOME = os.getenv("PDF2JSON_HOME")
SERVICE_SUFFIX = os.getenv("SERVICE_SUFFIX")


ADDRESS_SERVICE_FAST_METADATA_SEARCH = f"http://document_prefetch_service_fast_metadata_search_{SERVICE_SUFFIX}:8060"
ADDRESS_SERVICE_BUILD_INDEX = f"http://document_prefetch_service_build_index_{SERVICE_SUFFIX}:8060"

def wait_for_service( service_url ):
    
    url = urlparse( service_url )
    host = url.hostname
    port = url.port

    while True:
        try:
            with socket.create_connection( (host, port) ):
                break
        except:
            time.sleep(1)
            
def rebuild_index():           
    requests.post(
        ADDRESS_SERVICE_BUILD_INDEX + "/build-index",
        data = json.dumps({}),
        headers = {"Content-Type":"application/json", "Connection": "close"}
    )
            
def bytes_to_base64_string(f_bytes):
    return base64.b64encode(f_bytes).decode('ASCII')

def base64_string_to_bytes(base64_string):
    return base64.b64decode(base64_string)

def get_md5( file_bytes ):
    readable_hash = hashlib.md5(file_bytes).hexdigest()
    return readable_hash

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


def parse_pdf_base( pdf_bytes ):
    
    root_dir = "root_dir_" + str(uuid.uuid4())
    pdf_dir = root_dir + "/pdf/"
    temp_dir = root_dir + "/temp_dir/"
    output_dir = root_dir + "/output_dir/"
    try:
        os.makedirs(pdf_dir)
        os.makedirs(temp_dir)
        os.makedirs(output_dir)
    except:
        print("warning: folders exist!")
        
    try:
        with open( pdf_dir + "pdf.pdf","wb" ) as f:
            f.write(pdf_bytes)
    
        pdf_name = [ pdf_dir+fname for fname in os.listdir( pdf_dir )][0]
        subprocess.run( list(map( str, [
                    "python",
                    PDF2JSON_HOME+"/doc2json/grobid2json/process_pdf.py",
                    "-i", pdf_name,
                    "-t", temp_dir,
                    "-o", output_dir
                   ] ) ) )
        print("PDF parsing done!")
    

        json_name = [ output_dir+fname for fname in os.listdir( output_dir )][0]
        
        parsed_data = json.load(open(json_name))
        shutil.rmtree(root_dir)
    
    except:
        parsed_data = {}
        try:
            shutil.rmtree(root_dir)
        except:
            print("warning: removing temporary folder failed!")
    return parsed_data
    
def convert_pdf_to_json( fbytes, count, conversion_results ):
    try:
        parsed_data =  parse_pdf_base( fbytes )
    except:
        parsed_data = {}
        
    conversion_results[count] = parsed_data
        


@app.route('/index-pdfs', methods=['POST'])
def index_pdfs():
    global paper_db, doc_normalizer, args, sem

    sem.acquire()

    try:
        request_info = request.json
    
        uploader = request_info.get("username","")
        pdf_base64_string_list = request_info.get( "PDF_Base64_String_List", [] )
        ## This can take a lot of time, so use it rarely!
        update_index_immediately = request_info.get("update_index_immediately",0)
        
        assert len(pdf_base64_string_list) > 0
        
        fbytes_list = []
        for pdf_base64_string in pdf_base64_string_list:
            fbytes_list.append( base64_string_to_bytes( pdf_base64_string ) )
        
        existing_paper_ids = [] 
        fbytes_list_for_parsing = []
        md5_list_for_parsing = []
            
        md5_history = set()
            
        for fbytes in fbytes_list:
            md5 = get_md5( fbytes )
            if md5 in md5_history:
                continue
            md5_history.add( md5 )
            
            paper_ids = fast_metadata_search( [ { "MD5":md5 } ] )[0]
            
            paper_uploaders = [ paper.get("Uploader", "") for paper in paper_db.get_papers( paper_ids, projection = {"Uploader":1} )]
            
            uploader_matched = False
            for pos in range(len(paper_uploaders)):
                if paper_uploaders[pos] == uploader:
                    existing_paper_ids.append( paper_ids[pos] )
                    uploader_matched = True
                    break
            if not uploader_matched and md5 not in md5_list_for_parsing:
                fbytes_list_for_parsing.append( fbytes )
                md5_list_for_parsing.append( md5 )
        
        
        threads = []
        conversion_results = {}
        for count, fbytes in enumerate(fbytes_list_for_parsing):
            t = threading.Thread( target = convert_pdf_to_json , args = ( fbytes, count, conversion_results ) )
            t.start()
            threads.append(t)
        
            if len(threads) >= args.max_num_parsed_pdfs_in_parallel:
                for t in threads:
                    t.join()
                threads = []
        
        for t in threads:
            t.join()
        
        
        paper_info_list = []
        for count in range(len(fbytes_list_for_parsing)):
            if conversion_results[count] != {}:
                paper_info = doc_normalizer.normalize( conversion_results[count] )
                paper_info["PDF_Base64_String"] = bytes_to_base64_string( fbytes_list_for_parsing[count] )
                paper_info["MD5"] = md5_list_for_parsing[count]
                paper_info["Uploader"] = uploader
                paper_info_list.append( paper_info )    

        assert len( paper_db.collections ) == 1
        collection = list( paper_db.collections )[0]
        
        prev_max_row_id = paper_db.get_max_rowid(collection)
        if len(paper_info_list) > 0:
            paper_db.insert_papers( paper_info_list, collection )
        post_max_row_id = paper_db.get_max_rowid(collection)
                
        newly_parsed_paper_ids = [ { "collection":collection,
                                 "id_field":"id_int",
                                 "id_type":"int",
                                 "id_value":id_value
            } for id_value in range( prev_max_row_id+1, post_max_row_id+1 ) ]
                
        results_paper_ids = existing_paper_ids + newly_parsed_paper_ids

        if len(newly_parsed_paper_ids) > 0 and update_index_immediately:
            rebuild_index()
            
    except:
        results_paper_ids = []
        
    sem.release()
    
    return {"response": results_paper_ids }, 201


@app.route('/parse-pdf', methods=['POST'])
def parse_pdf():
    try:
        pdf_bytes = request.files.get('pdf').read()
        parsed_data =  parse_pdf_base( pdf_bytes )
    except:
        parsed_data = {}
        
    return {"response":parsed_data}, 201


@app.route('/parse-and-normalize-pdf', methods=['POST'])
def parse_and_normalize_pdf():
    global doc_normalizer
    try:
        pdf_bytes = request.files.get('pdf').read()
        parsed_data = parse_pdf_base( pdf_bytes )
        parsed_data = doc_normalizer.normalize( parsed_data )
    except:
        parsed_data = {}
        
    return {"response":parsed_data}, 201
    

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()    
    parser.add_argument( "-flask_port", type = int, default = 8060 )
    parser.add_argument( "-json_schema_path", default = "./json_schema.json" )
    parser.add_argument( "-sqlite_database_path", default = ROOT_DATA_PATH + "/sqlite_database/DB.db" )
    parser.add_argument( "-max_num_parsed_pdfs_in_parallel", type = int, default = 50 )
        
    args = parser.parse_args()
    
    wait_for_service(ADDRESS_SERVICE_BUILD_INDEX)
    wait_for_service(ADDRESS_SERVICE_FAST_METADATA_SEARCH)

    paper_db = SqliteClient( args.sqlite_database_path )
    
    doc_normalizer = DocumentNormalizer( args.json_schema_path )
    
    print("\n\nWaiting for requests...")
    sem = threading.Semaphore()

    app.run(host='0.0.0.0', port=args.flask_port, threaded = True)