import os,sys,inspect
import argparse
import json
import logging
import requests
from datetime import datetime
from flask import Flask, jsonify, abort, make_response, request, Response
from flask_cors import CORS

import os
import numpy as np
import pickle
import threading
import uuid
import multiprocessing as mp

from modules.ranking.inverted_index import OnDiskInvertedIndex
from modules.ranking.rankers import Ranker, Sent2vecEncoder

import GPUtil

import time
from modules.service_utils.utils import wait_for_service

# Make Flask application
app = Flask(__name__)
CORS(app)


ROOT_DATA_PATH = os.getenv("ROOT_DATA_PATH")
SENT2VEC_MODEL_PATH = os.getenv("SENT2VEC_MODEL_PATH")

IS_PRIVATE_SERVER = int( os.getenv("IS_PRIVATE_SERVER") )
USE_GPU = int( os.getenv("USE_GPU") )

EMBEDDING_INDEX_PRECISION = os.getenv("EMBEDDING_INDEX_PRECISION")

SERVICE_SUFFIX = os.getenv("SERVICE_SUFFIX")


ADDRESS_SERVICE_BUILD_INDEX = f"http://document_prefetch_service_build_index_{SERVICE_SUFFIX}:8060"


def get_top_n( n, query,  keyword_filtering_results = None, doc_id_list = None , require_tokenize = True, ranking_shard_id_list = None ):
    global  encoder, ranker
    query_embedding = encoder.encode( [query], require_tokenize )[0]
    return ranker.get_top_n_given_embedding( n, query_embedding, keyword_filtering_results, doc_id_list, ranking_shard_id_list )

def detach_embedding_index_shards( shards ):
    global ranker
    for shard_id in shards:
        ranker.delete_shard( shard_id )
        
def attach_embedding_index_shards( shards ):
    global ranker, args
    detach_embedding_index_shards( shards )
    base_ranker_para_list = [
        {
            "shard_id": shard_id,
            "embedding_path": args.embedding_index_folder +"/"+ shard_id, 
            "vector_dim":args.vector_dim,
            "gpu_list":args.gpu_list,
            "internal_precision" : args.internal_precision,
            "requires_precision_conversion":args.requires_precision_conversion ,
            "num_threads": args.num_threads_per_shard,
            "normalize_query_embedding" : args.normalize_query_embedding 
        }
        for shard_id in shards if os.path.exists( args.embedding_index_folder +"/"+ shard_id )
    ]
    updating_ranker = Ranker( base_ranker_para_list, ranker.num_of_processes_of_gpu )
    ranker.update_shards( updating_ranker )
        
@app.route('/document-search', methods=['POST'])
def document_search():

    """Document search API route"""
    global sem,  on_disk_inv_idx, ranker, args
    
    ## currently our search function does not support concurrent request
    sem.acquire()

    try:
        try:
            request_info = request.json
        except:
            request_info = {}
            
        ranking_source = request_info.get("ranking_source", "")
        keywords = request_info.get("keywords", "")
        n_results = request_info.get("nResults", 1000)
        
        if "paper_list" not in request_info or not isinstance(request_info["paper_list"] , list):
            paper_list = None
            
            if args.is_private_server:
                assert False
        
        else:
            paper_list = request_info["paper_list"] 
                
        tic = time.time()
        keywords = keywords.strip()
        if keywords == "":
            num_matched_documents = on_disk_inv_idx.num_matched_documents
            results = get_top_n( n_results, ranking_source, keyword_filtering_results = None, doc_id_list = paper_list )
        else:
            filtered_results = on_disk_inv_idx.get( keywords )
            num_matched_documents = 0
            for c in filtered_results:
                num_matched_documents += int(np.sum(filtered_results[c] ))
            results = get_top_n( n_results, ranking_source, keyword_filtering_results = filtered_results, doc_id_list = paper_list )  
            
        tac = time.time()
        print("doc search time:", tac - tic)
        
        
        json_out = json.dumps({"response":results, "nMatchingDocuments":num_matched_documents}) 
        logging.info("Doc search successed.") 
    except:
        json_out = json.dumps({"response":[], "nMatchingDocuments":0}) 
        logging.info("Doc search failed.") 

    sem.release()
    return json_out, 201


@app.route('/reboot', methods=['POST'])
def reboot():
    global args, ranker, on_disk_inv_idx, sem

    sem.acquire()
    try:        
        shards = list(ranker.rank_process_dict.keys())
        detach_embedding_index_shards( shards )
        
        ## reload all new shards
        shards = [ fname for fname in os.listdir( args.embedding_index_folder ) if fname.startswith("embedding_index.db")  ]
        attach_embedding_index_shards( shards )
        
        ## reload inverted index
        on_disk_inv_idx.initiate()
        
        msg = {"response":"success"}
    except:
        msg = {"response":"fail"}

    sem.release()
    return jsonify(msg), 201


@app.route('/reboot-ranking-index', methods=['POST'])
def reboot_ranking_index():
    global args, ranker, sem

    sem.acquire()
    try:        
        shards = list(ranker.rank_process_dict.keys())
        detach_embedding_index_shards( shards )
        
        ## reload all new shards
        shards = [ fname for fname in os.listdir( args.embedding_index_folder ) if fname.startswith("embedding_index.db")  ]
        attach_embedding_index_shards( shards )
        
        msg = {"response":"success"}
    except:
        msg = {"response":"fail"}

    sem.release()
    return jsonify(msg), 201

@app.route('/reboot-inverted-index', methods=['POST'])
def reboot_inverted_index():
    global args, on_disk_inv_idx, sem

    sem.acquire()

    try:
        on_disk_inv_idx.initiate()
        msg = {"response":"success"}
    except:
        msg = {"response":"fail"}

    sem.release()
    return jsonify(msg), 201


@app.route('/update-ranking-index', methods=['POST'])
def update_ranking_index():
    global args, ranker, sem

    sem.acquire()

    try:
        if not request.json:
            assert False
        request_info = request.json 
        
        shards = request_info.get("shards", [])
        if not isinstance( shards, list ):
            shards = []

        shards = [ shard_id for shard_id in shards if os.path.exists( args.embedding_index_folder + "/" + shard_id )  ]
        action = request_info.get("action", "attach").lower()
        
        if action == "detach":
            detach_embedding_index_shards( shards )
            msg = {"response":{ 
                        "info":"%d embedding index shards detached:\n\t"%(len(shards))+"\n\t".join( shards ),
                        "success":1
                              }  
                  }
        elif action == "attach":
            attach_embedding_index_shards( shards )
            msg = {"response":{
                        "info":"%d embedding index shards attached:\n\t"%(len(shards))+"\n\t".join( shards ),
                        "success":1
                            }
            
                  }
    except:
        msg = {"response":{
                        "info":"Embedding index deletion/updating failed! Make sure the shards to be detached/attached are all within folder %s !"%( args.embedding_index_folder ),
                        "success":0
                         }
        
              }
    print(msg)
    sem.release()
    return jsonify(msg), 201


@app.route('/update-inverted-index', methods=['POST'])
def update_inverted_index():
    global args, on_disk_inv_idx, sem

    sem.acquire()

    try:
        if not request.json:
            assert False
        request_info = request.json 
            
        shards = request_info.get("shards", [])
        if not isinstance( shards, list ):
            shards = []
        shards = [ shard_id for shard_id in shards if os.path.exists( args.inverted_index_folder + "/" + shard_id )  ]
        action = request_info.get("action", "attach").lower()
        
        if action == "detach":
            on_disk_inv_idx.pause_shards( shards )
            msg = {"response":{
                       "info": "%d inverted index shards detached:\n\t"%(len(shards))+"\n\t".join( shards ),
                       "success":1
                       }
                  }
        elif action == "attach":
            on_disk_inv_idx.initiate()   
            msg = {"response":{
                        "info":"%d inverted index shards attached:\n\t"%(len(shards))+"\n\t".join( shards ),
                        "success":1
                       }
            
                  }
    except:
        msg = {"response":{
                    "info":"Inverted index deletion/updating failed! Make sure the shards to be detached/attached are all within folder %s !"%( args.inverted_index_folder ),
                    "success":0
                  }
              }

    print(msg)
    sem.release()

    return jsonify(msg), 201



if __name__ == "__main__":
    parser = argparse.ArgumentParser()    
    parser.add_argument( "-flask_port", type = int, default = 8060 )
    parser.add_argument( "-inverted_index_folder", default = ROOT_DATA_PATH + "/ranking/inverted_index/" )
    parser.add_argument( "-embedding_index_folder", default = ROOT_DATA_PATH + "/ranking/embedding_index/"  )
    parser.add_argument( "-encoding_model_path", default = SENT2VEC_MODEL_PATH )
    
    parser.add_argument( "-is_private_server", type = int, default = IS_PRIVATE_SERVER )
    
    parser.add_argument( "-internal_precision", default = EMBEDDING_INDEX_PRECISION )
    parser.add_argument( "-requires_precision_conversion", type = int, default = 1 )
    parser.add_argument( "-num_threads_per_shard", type = int, default = 1 )
    parser.add_argument( "-normalize_query_embedding", type = int, default = 1 )
    
    args = parser.parse_args()
    
    wait_for_service(ADDRESS_SERVICE_BUILD_INDEX)
    
    #Convert folders to absolute path
    args.inverted_index_folder = os.path.abspath( args.inverted_index_folder  )
    args.embedding_index_folder = os.path.abspath( args.embedding_index_folder )
    args.encoding_model_path = os.path.abspath(  args.encoding_model_path  )
    
    on_disk_inv_idx = OnDiskInvertedIndex( args.inverted_index_folder )
    encoder = Sent2vecEncoder( args.encoding_model_path )
    
    args.vector_dim = encoder.model.get_emb_size()

    if USE_GPU:
        args.gpu_list = [ gpu.id for gpu in GPUtil.getGPUs() ]
        if len(args.gpu_list) == 0:
            print("Warning: no gpus are available, using the ANN on CPU")
        else:
            print( "Using GPU brute-force NN on devices:", args.gpu_list )
    else:
        args.gpu_list = []
        
    if len(args.gpu_list) == 0:
        args.internal_precision = "float32"
        
    mp.set_start_method('spawn')
    
    shard_list = os.listdir(args.embedding_index_folder)
    base_ranker_para_list = []
    for shard_name in shard_list:
        base_ranker_para_list.append( {
                    ## By default, we use the base name of the embedding path as the shard_id
                    "shard_id": shard_name,
                    "embedding_path": args.embedding_index_folder +"/"+ shard_name, 
                    "vector_dim":args.vector_dim,
                    "gpu_list":args.gpu_list,
                    "internal_precision" : args.internal_precision,
                    "requires_precision_conversion":args.requires_precision_conversion ,
                    "num_threads": args.num_threads_per_shard,
                    "normalize_query_embedding" : args.normalize_query_embedding })

    ranker = Ranker(base_ranker_para_list )

    get_top_n( 10, "warm-up query" )
    
    sem = threading.Semaphore()

    print("\n\nWaiting for requests...")
    app.run(host='0.0.0.0', port=args.flask_port, threaded = True)