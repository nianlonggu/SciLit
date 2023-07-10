import argparse
import json
import requests
from datetime import datetime
from flask import Flask, jsonify, abort, make_response, request, Response
from flask_cors import CORS
import os 

# Make Flask application
app = Flask(__name__)
CORS(app)


@app.route('/build-index', methods=['POST'])
def build_index():
    global args, headers
    try:
        results = requests.post(  args.build_index_service_root_address +"/"+"build-index", data = json.dumps(request.json), headers = headers ).json()
    except:
        abort(400)
    return json.dumps(results), 201


@app.route('/document-search', methods=['POST'])
def document_search():
    global args, headers
    try:
        results = requests.post(  args.document_search_service_root_address +"/"+"document-search", data = json.dumps(request.json), headers = headers ).json()
    except:
        abort(400)
    return json.dumps(results), 201



@app.route('/get-papers', methods=['POST'])
def get_papers():
    global args, headers
    try:
        results = requests.post(  args.paper_database_service_root_address +"/"+"get-papers", data = json.dumps(request.json), headers = headers ).json()
    except:
        abort(400)
    return json.dumps(results), 201


@app.route('/check-duplicate', methods=['POST'])
def duplicate_checking():
    global args, headers
    try:
        results = requests.post(  args.duplicate_checking_service_root_address +"/"+"check-duplicate", data = json.dumps(request.json), headers = headers ).json()
    except:
        abort(400)
    return json.dumps(results), 201


@app.route('/index-pdfs', methods=['POST'])
def index_pdfs():

    global args, headers
    try:
        results = requests.post(  args.pdf_indexing_service_root_address + "/index-pdfs", 
                                  data = json.dumps(request.json), 
                                  headers = headers
                               ).json()
    except:
        abort(400)
    return json.dumps(results), 201


SERVICE_SUFFIX = os.getenv("SERVICE_SUFFIX")

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()    
    parser.add_argument( "-flask_port", type = int, default=8060 )
    parser.add_argument( "-build_index_service_root_address", default = f"http://document_prefetch_service_build_index_{SERVICE_SUFFIX}:8060" )    
    parser.add_argument( "-document_search_service_root_address", default = f"http://document_prefetch_service_ranking_{SERVICE_SUFFIX}:8060" )
    parser.add_argument( "-paper_database_service_root_address", default = f"http://document_prefetch_service_paper_database_{SERVICE_SUFFIX}:8060"  )
    parser.add_argument( "-duplicate_checking_service_root_address", default = f"http://document_prefetch_service_fast_metadata_search_{SERVICE_SUFFIX}:8060" )
    parser.add_argument( "-pdf_indexing_service_root_address", default = f"http://document_prefetch_service_pdf_parsing_{SERVICE_SUFFIX}:8060" )
    args = parser.parse_args()

    headers = {"Content-Type": "application/json", 'Connection': 'close'}   
    print("\n\nWaiting for requests...")

    app.run(host='0.0.0.0', port=args.flask_port)
