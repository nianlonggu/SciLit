import os,sys,inspect
import argparse
import json
import requests
from datetime import datetime
from flask import Flask, jsonify, abort, make_response, request, Response
from flask_cors import CORS

from modules.paper_database.database_managers import SqliteClient

import time
from modules.service_utils.utils import wait_for_service

# Make Flask application
app = Flask(__name__)
CORS(app)

ROOT_DATA_PATH = os.getenv("ROOT_DATA_PATH")
SERVICE_SUFFIX = os.getenv("SERVICE_SUFFIX")

ADDRESS_SERVICE_BUILD_INDEX = f"http://document_prefetch_service_build_index_{SERVICE_SUFFIX}:8060"


@app.route('/reboot', methods=['POST'])
def reboot():
    global args, db_client

    try:        
        db_client = SqliteClient( args.database_path )
        msg = {"response":"success"}
    except:
        msg = {"response":"fail"}

    return jsonify(msg), 201


@app.route('/get-papers', methods=['POST'])
def get_papers():
    global args, db_client
    
    try:
        request_info = request.json
        paper_id_list =  request_info.get( "paper_list", [] )
        projection = request_info.get( "projection",None )
        paper_list = db_client.get_papers( paper_id_list, projection )
    
    except:
        paper_list = []
        
    json_out = { "response":paper_list }
    return json.dumps(json_out), 201

if __name__ == '__main__':

    parser = argparse.ArgumentParser()    
    parser.add_argument( "-flask_port", type = int, default = 8060 )
    parser.add_argument( "-database_path", default = ROOT_DATA_PATH + "/sqlite_database/DB.db" )
    args = parser.parse_args()
    
    wait_for_service(ADDRESS_SERVICE_BUILD_INDEX)
    
    db_client = SqliteClient( args.database_path )
    
    print("\n\nWaiting for requests...")

    # app.run(host='0.0.0.0', port=args.flask_port, debug=True)
    app.run(host='0.0.0.0', port=args.flask_port)
