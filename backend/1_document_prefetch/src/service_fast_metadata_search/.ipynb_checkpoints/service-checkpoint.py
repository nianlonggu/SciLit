import os,sys,inspect
import argparse
import json
import requests
from flask import Flask, jsonify, abort, make_response, request, Response
import threading
from flask_cors import CORS

import time
from modules.service_utils.utils import wait_for_service
from modules.duplicate_checking.duplicate_checker import DuplicateChecker

# Make Flask application
app = Flask(__name__)
CORS(app)


ROOT_DATA_PATH = os.getenv("ROOT_DATA_PATH")
SERVICE_SUFFIX = os.getenv("SERVICE_SUFFIX")

ADDRESS_SERVICE_BUILD_INDEX = f"http://document_prefetch_service_build_index_{SERVICE_SUFFIX}:8060"

    
@app.route('/reboot', methods=['POST'])
def reboot():
    global duplicate_checker, sem, args

    sem.acquire()
    try:        
        duplicate_checker = DuplicateChecker( args.duplicate_checking_database_path )
        msg = {"response":"success"}
    except:
        msg = {"response":"fail"}

    sem.release()
    return jsonify(msg), 201


@app.route('/check-duplicate', methods=['POST'])
def check_duplicate():
    global duplicate_checker, sem

    sem.acquire()
    
    try:
        request_info = request.json
        if not request_info:
            assert False
        if "paper_list" not in request_info or not isinstance(request_info["paper_list"], list ):
            assert False

        res_list = []
        for paper in request_info["paper_list"]:
            try:
                md5 = paper.get("MD5","")
                doi = paper.get("DOI","")
                title = paper.get("Title","")
                first_author = paper.get("First_Author","")
                res = duplicate_checker.check( md5 = md5, doi = doi, title = title, first_author = first_author )
            except:
                res = []
            res_list.append(res)
    except:
        res_list = []
    json_out = { "response":res_list }

    sem.release()
    return json.dumps(json_out), 201


@app.route('/update-duplicate-checking-database', methods=['POST'])
def update():
    global duplicate_checker, sem
    ## sem, sem.acquire(), sem.release()

    sem.acquire()
    try:
        request_info = request.json
        if not request_info:
            assert False
        if "paper_list" not in request_info or not isinstance(request_info["paper_list"], list ):
            assert False

        paper_list = [ [ paper["collection"], paper["id_int"], 
                         paper.get("MD5",""),
                         paper.get("DOI",""),
                         paper.get("Title",""), 
                         paper.get( "First_Author", "") ]  
                       for paper in request_info["paper_list"] ]
        duplicate_checker.update( paper_list )
        msg = { "response":"Update successed!" }
    except:
        msg = { "response":"Update failed! Make sure each paper in the paper_list is a dictionary containing keys: 1) collection; 2) id_int; 3) MD5; 4) DOI; 5) Title; 6) First_Author" }
        
    json_out = msg
    sem.release()
    return json.dumps(json_out), 201


if __name__ == '__main__':


    parser = argparse.ArgumentParser()    
    parser.add_argument( "-flask_port", type = int, default = 8060 )
    parser.add_argument( "-duplicate_checking_database_path", default = ROOT_DATA_PATH + "/duplicate_checking/data.db" )
    args = parser.parse_args()
 
    
    wait_for_service(ADDRESS_SERVICE_BUILD_INDEX)
    

    sem = threading.Semaphore()

    duplicate_checker = DuplicateChecker( args.duplicate_checking_database_path )

    print("\n\nWaiting for requests...")

    app.run(host='0.0.0.0', port=args.flask_port, threaded = True)
