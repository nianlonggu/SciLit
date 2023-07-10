import os,sys,inspect
import argparse
import json
import logging
import requests
from datetime import datetime
from flask import Flask, jsonify, abort, make_response, request, Response
from flask_cors import CORS

import re
from nltk.tokenize import RegexpTokenizer

from modules.t5_citation_generator import CitationGenerator

import numpy as np
import GPUtil

logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)
logging.getLogger("gensim").setLevel(logging.WARNING)

# Make Flask application
app = Flask(__name__)
CORS(app)


def get_papers( paper_list, projection = None ):
    global args
    results = requests.post( 
                    args.paper_database_service_address, 
                    data = json.dumps( {
                               "paper_list" : paper_list,
                               "projection" : projection
                           } ), 
                    headers = {"Content-Type": "application/json", 'Connection': 'close'} ).json()["response"]
    return results

def parse_keywords( keywords ):
    global word_tokenizer, keywords_connector_matcher
    
    ngram_connector_matcher = re.compile("_(?![pP]arsed)")
    keywords = keywords.strip()
    keywords_list = []
    for w in keywords.split("\\t"):
        # w = " ".join( w.replace("_"," ").split())
        w = " ".join( ngram_connector_matcher.sub(" ", w).split() )
        w = w.replace("|","<OR>")
        w = w.replace("!","<NOT>")
        if w.strip() != "":
            keywords_list.append(w.strip())
    keywords = "<AND>".join( keywords_list )
    
    
    return  "; ".join( [ " ".join(word_tokenizer.tokenize(w)) for w in keywords_connector_matcher.split(keywords) if ":" not in w ])


@app.route('/generate-citation', methods=['POST'])
def generate_citation():
    global citation_generator
    
    request_info = request.json
    if not request_info:
        abort(400)
    
    context_list = request_info.get( "context_list", [] )
    keywords_list = request_info.get( "keywords_list", [] )
    papers = request_info.get( "papers", [] )
    
    ## parse keywords list
    keywords_list = [ parse_keywords(kwd) for kwd in keywords_list ]
    
    print(keywords_list)
        
    gen_text_list = citation_generator.generate_citation(  context_list, keywords_list, papers)

    json_out = {"response": gen_text_list}
    return json.dumps(json_out), 201


USE_GPU = int(os.getenv("USE_GPU"))
PAPER_DATABASE_SERVICE_ADDRESS = os.getenv("PAPER_DATABASE_SERVICE_ADDRESS")

if __name__ == '__main__':

    parser = argparse.ArgumentParser()    
    parser.add_argument( "-model_path", default = "scieditor/citation-generation-t5" )
    parser.add_argument( "-paper_database_service_address", default = PAPER_DATABASE_SERVICE_ADDRESS ) 
    parser.add_argument( "-flask_port", type = int, default = 8060 )
    
    args = parser.parse_args()
    
    
    if USE_GPU:
        args.gpu_list = [ gpu.id for gpu in GPUtil.getGPUs() ]
        if len(args.gpu_list) == 0:
            print("Warning: no gpus are available, using CPU")
    else:
        args.gpu_list = []
    
    
    word_tokenizer = RegexpTokenizer("[A-Za-z]+")
    keywords_connector_matcher = re.compile("<.*?>")

    citation_generator = CitationGenerator( model_path = args.model_path, 
                                            gpu_list = args.gpu_list )

    print("\n\n")
    logging.info("Waiting for requests...")

    app.run(host='0.0.0.0', port=args.flask_port, debug=True)
