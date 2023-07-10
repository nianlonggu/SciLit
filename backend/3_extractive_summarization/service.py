import os,sys,inspect
import argparse
import json
import logging
import requests
from datetime import datetime
from flask import Flask, jsonify, abort, make_response, request, Response
from flask_cors import CORS

from modules.MemSum.summarizers import MemSum
from modules.BertSum.BertSum_extractive_summarizer import BertSumExtractor

import numpy as np
from copy import deepcopy

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


def get_sentence_ids_and_texts_from_parsed( parsed_text, tag ):
    id_list = []
    sentence_list = []
    
    for sec in parsed_text:
        section_id = sec["section_id"]
        for para in sec["section_text"]:
            paragraph_id = para["paragraph_id"]
            for sen in para["paragraph_text"]:
                sentence_id = sen["sentence_id"]
                sentence_text = sen["sentence_text"]
                
                id_list.append({"tag":tag,
                                "section_id":section_id,
                                "paragraph_id":paragraph_id,
                                "sentence_id":sentence_id
                               })
                sentence_list.append( sentence_text )
    
    return id_list, sentence_list
    

@app.route('/get-highlights', methods=['POST'])
def get_highlights():
    global args, memsum_ext_sum, bertsum_ext_sum
    request_info = request.json
    method = request_info.get("method","memsum")
    try:
        if not request_info or "paper_id" not in request_info or not isinstance( request_info["paper_id"], dict ):
            assert False

        paper = get_papers( [request_info["paper_id"]] )[0]
        assert len(paper["Content"]["Fullbody_Parsed"]) > 0
        
        id_list, sentence_list = get_sentence_ids_and_texts_from_parsed( paper["Content"]["Fullbody_Parsed"], 
                                                                         "Fullbody_Parsed" )
        
        if method.lower() == "bertsum":
            extracted_sen, sen_pos = bertsum_ext_sum.extract([sentence_list], return_sentence_position = True)
        else:
            extracted_sen, sen_pos = memsum_ext_sum.extract([sentence_list], return_sentence_position = True)
        
        extracted_sen, sen_pos = extracted_sen[0], sen_pos[0]
        if len(extracted_sen)>0:
            extracted_sen, sen_pos = list(zip(*sorted( zip( extracted_sen, sen_pos ), key = lambda x: x[1] )))
        
        highlights = []
        for idx in range(len(extracted_sen)):
            item = deepcopy( id_list[ sen_pos[idx] ] )
            item["sentence_text"] = extracted_sen[idx]
            highlights.append(item)
    except:
        highlights = []
    
    return jsonify({"response":highlights}), 201


@app.route('/extractive-summarize', methods=['POST'])
def extractive_summarize():
    global memsum_ext_sum, bertsum_ext_sum
    request_info = request.json

    if not request_info or "sentence_list" not in request_info or not isinstance( request_info["sentence_list"], list ):
        abort(400)
    sentence_list = request_info["sentence_list"]
    method = request_info.get("method","memsum")

    if method.lower() == "bertsum":
        extracted_sen, sen_pos = bertsum_ext_sum.extract([sentence_list], return_sentence_position = True)
    else:
        extracted_sen, sen_pos = memsum_ext_sum.extract([sentence_list], return_sentence_position = True)
    
    extracted_sen, sen_pos = extracted_sen[0], sen_pos[0]
    if len(extracted_sen)>0:
        extracted_sen, sen_pos = list(zip(*sorted( zip( extracted_sen, sen_pos ), key = lambda x: x[1] )))

    results = {
        "summary": extracted_sen,
        "sentence_position":sen_pos
    }

    json_out = {"response": results}
    return json.dumps(json_out), 201


USE_GPU = int(os.getenv("USE_GPU"))
PAPER_DATABASE_SERVICE_ADDRESS = os.getenv("PAPER_DATABASE_SERVICE_ADDRESS")


if __name__ == '__main__':

    parser = argparse.ArgumentParser()    
    parser.add_argument( "-model_path_memsum", default = "/app/models/MemSum/pubmed/200dim/model.pt"
 )
    parser.add_argument( "-vocab_path_memsum", default = "/app/models/MemSum/word_embedding/vocabulary_200dim.pkl"
 )
    parser.add_argument( "-model_path_bertsum", default = "/app/models/BertSum/checkpoint-4000"
 )
    parser.add_argument( "-paper_database_service_address", default = PAPER_DATABASE_SERVICE_ADDRESS )  
    parser.add_argument( "-flask_port", type = int, default = 8060)
    
    args = parser.parse_args()
    
    if USE_GPU:
        gpu_list = [ gpu.id for gpu in GPUtil.getGPUs() ]
        if len(gpu_list) > 0:
            args.gpu = gpu_list[0]
        else:
            args.gpu = None
    else:
        args.gpu = None
    
    memsum_ext_sum = MemSum( args.model_path_memsum, 
                  args.vocab_path_memsum ,
                  embed_dim = 200,
                  max_extracted_sentences_per_document = 7,
                  max_doc_len = 200,
                  gpu = args.gpu
                )
    
    bertsum_ext_sum = BertSumExtractor( args.model_path_bertsum, args.gpu  )
    
    print("\n\n")
    logging.info("Waiting for requests...")

    # app.run(host='0.0.0.0', port=args.flask_port, debug=True)
    app.run(host='0.0.0.0', port=args.flask_port)
