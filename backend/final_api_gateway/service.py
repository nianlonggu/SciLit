import argparse
import json
import logging
import requests
from datetime import datetime
from flask import Flask, jsonify, abort, make_response, request, Response
from flask_cors import CORS
import os


logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)
logging.getLogger("gensim").setLevel(logging.WARNING)

# Make Flask application
app = Flask(__name__)
CORS(app)


@app.route('/ml-api/doc-search/v1.0', methods=['POST'])
def document_search():
    global args, headers 
    
    
    ReceivingTimeStamp = datetime.now().timestamp()
    try:
        results = requests.post(  args.document_search_address, data = json.dumps(request.json), headers = headers ).json()
    except:
        abort(400)
    SendingTimeStamp = datetime.now().timestamp()
        
    return json.dumps(results), 201


@app.route('/ml-api/title-generic-search/v1.0', methods=['POST'])
def title_generic_search():
    global args, headers
    
    ReceivingTimeStamp = datetime.now().timestamp()
    try:
        results = requests.post(  args.title_generic_search_address, data = json.dumps(request.json), headers = headers ).json()
    except:
        abort(400)
    SendingTimeStamp = datetime.now().timestamp()
            
    return json.dumps(results), 201


@app.route('/ml-api/citation-formatting-service/v1.0', methods=['POST'])
def citation_formatting_service():
    global args, headers
    
    ReceivingTimeStamp = datetime.now().timestamp()
    try:
        results = requests.post(  args.citation_formatting_service_address , data = json.dumps(request.json), headers = headers ).json()
    except:
        abort(400)
    SendingTimeStamp = datetime.now().timestamp()
            
    return json.dumps(results), 201


@app.route('/ml-api/extractive-summarize/v1.0', methods=['POST'])
def extractive_summarize():
    global args, headers
    
    ReceivingTimeStamp = datetime.now().timestamp()
    try:
        results = requests.post(  args.extractive_summarization_service_address, 
                                  data = json.dumps(request.json), 
                                  headers = headers
                               ).json()
    except:
        abort(400)
    SendingTimeStamp = datetime.now().timestamp()
            
    return json.dumps(results), 201

@app.route('/ml-api/generate-citation/v1.0', methods=['POST'])
def generate_citation():
    global args, headers
    
    ReceivingTimeStamp = datetime.now().timestamp()
    try:
        results = requests.post(  args.citation_generation_service_address, 
                                  data = json.dumps(request.json), 
                                  headers = headers
                               ).json()
    except:
        abort(400)
    SendingTimeStamp = datetime.now().timestamp()
        
    return json.dumps(results), 201

@app.route('/ml-api/get-papers/v1.0', methods=['POST'])
def get_papers():
    global args, headers
    ReceivingTimeStamp = datetime.now().timestamp()
    try:
        results = requests.post(  args.paper_database_service_address, 
                                  data = json.dumps(request.json), 
                                  headers = headers
                               ).json()
    except:
        abort(400)
    SendingTimeStamp = datetime.now().timestamp()
            
    return json.dumps(results), 201

@app.route('/ml-api/process/v1.0', methods=['POST'])
def process():
    global args, headers
    try:
        results = requests.post(  args.helper_functions_service_address, 
                                  data = json.dumps(request.json), 
                                  headers = headers
                               ).json()
    except:
        abort(400)
    return json.dumps(results), 201


DOCUMENT_SEARCH_ADDRESS = os.getenv("DOCUMENT_SEARCH_ADDRESS")
TITLE_GENERIC_SEARCH_ADDRESS = os.getenv("TITLE_GENERIC_SEARCH_ADDRESS")
CITATION_FORMATTING_SERVICE_ADDRESS = os.getenv("CITATION_FORMATTING_SERVICE_ADDRESS")
EXTRACTIVE_SUMMARIZATION_SERVICE_ADDRESS = os.getenv("EXTRACTIVE_SUMMARIZATION_SERVICE_ADDRESS")
CITATION_GENERATION_SERVICE_ADDRESS = os.getenv("CITATION_GENERATION_SERVICE_ADDRESS")
PAPER_DATABASE_SERVICE_ADDRESS = os.getenv("PAPER_DATABASE_SERVICE_ADDRESS")
HELPER_FUNCTIONS_SERVICE_ADDRESS = os.getenv("HELPER_FUNCTIONS_SERVICE_ADDRESS")


if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()    
    parser.add_argument( "-flask_port", type = int, default = 8060 )
    parser.add_argument( "-document_search_address", default = DOCUMENT_SEARCH_ADDRESS )
    parser.add_argument( "-title_generic_search_address", default = TITLE_GENERIC_SEARCH_ADDRESS )
    parser.add_argument( "-citation_formatting_service_address", default = CITATION_FORMATTING_SERVICE_ADDRESS )
    parser.add_argument( "-extractive_summarization_service_address", default = EXTRACTIVE_SUMMARIZATION_SERVICE_ADDRESS )
    parser.add_argument( "-citation_generation_service_address", default = CITATION_GENERATION_SERVICE_ADDRESS )
    parser.add_argument( "-paper_database_service_address", default = PAPER_DATABASE_SERVICE_ADDRESS )
    parser.add_argument( "-helper_functions_service_address", default = HELPER_FUNCTIONS_SERVICE_ADDRESS )
    
    args = parser.parse_args()

    headers = {"Content-Type": "application/json", 'Connection': 'close'}

    print("\n\n")
    logging.info("Waiting for requests...")

    app.run(host='0.0.0.0', port=args.flask_port, debug=True)


