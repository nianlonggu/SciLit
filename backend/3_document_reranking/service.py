import os,sys,inspect
import argparse
import json
import requests
from datetime import datetime
from flask import Flask, jsonify, abort, make_response, request, Response
from flask_cors import CORS

from modules.sent2vec_reranker import SentenceRanker
from modules.scibert_reranker import SciBertReranker

import time
import numpy as np
import pickle
import threading
import uuid
from more_itertools import unique_everseen

import re
from nltk.tokenize import RegexpTokenizer
 
import nltk
from nltk.corpus import stopwords
nltk.download('omw-1.4')
stopwords_set = set(stopwords.words('english'))

import GPUtil

# Make Flask application
app = Flask(__name__)
CORS(app)


USE_GPU = int(os.getenv("USE_GPU"))
ADDRESS_PAPER_DATABASE_SERVICE = os.getenv( "ADDRESS_PAPER_DATABASE_SERVICE" )


def get_papers( paper_id_list, projection = None ):
    global args
    results = requests.post( 
                    args.paper_database_service_address, 
                    data = json.dumps( {
                               "paper_list" : paper_id_list,
                               "projection" : projection
                           } ), 
                    headers = {"Content-Type": "application/json", 'Connection': 'close'} ).json()["response"]
    return results



def get_section_text_list( paper, top_n_sections = None ):
    if paper is None:
        paper = {}
    title = paper.get("Title","")
    abstract_parsed = paper.get("Content",{}).get("Abstract_Parsed",[])
    fullbody_parsed = paper.get("Content",{}).get("Fullbody_Parsed",[])
    fulltext_parsed = abstract_parsed + fullbody_parsed

    section_text_list = [title]
    for section in fulltext_parsed:
        section_text = ""        
        for para in section.get("section_text",[]):
            for sen in para.get("paragraph_text",[]):
                section_text += sen.get("sentence_text", "") + " "
        section_text_list.append( section_text )
    
    if top_n_sections is not None:
        section_text_list = section_text_list[:top_n_sections]
    
    return section_text_list

def rerank_based_on_query2section_similarity( paper_id_list, ranking_source, return_similarity = False ):
    global sentence_ranker
    
    if ranking_source.strip() == "":
        return paper_id_list
    
    paper_content_list = get_papers( paper_id_list, { "Title":1, "Content.Abstract_Parsed":1, "Content.Fullbody_Parsed": 1 } )
    if len(paper_content_list) != len(paper_id_list):
        return paper_id_list
    
    try:  
        selected_papers_to_be_reranked = paper_id_list
        selected_papers_contents = paper_content_list
    
        paper_indices_of_section_text  = []
        all_section_text_list = []
                
        for count_i in range( len( selected_papers_contents ) ):
            section_text_list  =  get_section_text_list( selected_papers_contents[count_i] )
                        
            paper_indices_of_section_text += [ count_i ] * len( section_text_list )
            all_section_text_list += section_text_list
                
        assert len(all_section_text_list) > 0
        
        paper_indices_of_section_text = np.array( paper_indices_of_section_text )
        sims_of_section_text = sentence_ranker.get_scores( ranking_source, all_section_text_list )
                
        paper_id_and_sim_list = []
        for count_i in range( len( selected_papers_contents ) ):
            paper_sim = (sims_of_section_text * ( paper_indices_of_section_text == count_i )).max()
            paper_id_and_sim_list.append( ( count_i, paper_sim ) )
                
        paper_id_and_sim_list.sort( key = lambda x: -x[1] )
        sentence_indices, sorted_sims = list( zip( *paper_id_and_sim_list ))
                    
        selected_papers_to_be_reranked = [selected_papers_to_be_reranked[idx] for idx in  sentence_indices ]
        sorted_sims = list(sorted_sims)
    except:
        selected_papers_to_be_reranked = paper_id_list
        sorted_sims = [0.0 for _ in paper_id_list]
    if return_similarity:
        return selected_papers_to_be_reranked, sorted_sims
    else:
        return selected_papers_to_be_reranked

""" This reranking is for local citation recommendation's reranking phrase """
def rerank_by_scibert( paper_id_list, ranking_source, keywords ):
    global scibert_reranker, word_tokenizer, keywords_connector_matcher
    
    ### parsing keywords here!!!
    keywords = "; ".join( [ " ".join(word_tokenizer.tokenize(w)) for w in keywords_connector_matcher.split(keywords) if ":" not in w ])
    
    if ranking_source.strip() == "" and keywords.strip() == "":
        return paper_id_list
    
    print(ranking_source, keywords )
    
    tic = time.time()
    paper_content_list = get_papers( paper_id_list, { "Title":1, "Abstract":1 } )
    if len(paper_content_list) != len(paper_id_list):
        return paper_id_list
    
    tac = time.time()
    print("Loading paper time:", tac - tic)
    
    
    try:
        reranked_indices = scibert_reranker.rerank( ranking_source, keywords, paper_content_list  )
        selected_papers_to_be_reranked = [ paper_id_list[idx] for idx in reranked_indices ]
    except:
        selected_papers_to_be_reranked = paper_id_list
        
        
    """ handle the exact match when users use the title to search for a paper """
    try:
        sorted_paper_id_list, sorted_sims = rerank_based_on_query2section_similarity( paper_id_list, ranking_source, return_similarity = True )
        
        prefix_papers = []
        for pos in range( min( len(sorted_paper_id_list), 10 ) ):
            sorted_paper_id, sim = sorted_paper_id_list[pos], sorted_sims[pos]
            if sim > 0.9:
                prefix_papers.append( sorted_paper_id )
    except:
        prefix_papers = []
    new_selected_papers_to_be_reranked = []
    for paper_id in selected_papers_to_be_reranked:
        matched = False
        for pid in prefix_papers:
            if paper_id == pid: 
                matched = True
                break
        if not matched:
            new_selected_papers_to_be_reranked.append( paper_id )
    selected_papers_to_be_reranked = prefix_papers + new_selected_papers_to_be_reranked
    """ handle the exact match when users use the title to search for a paper """
    
    return selected_papers_to_be_reranked
    
    
@app.route('/document-rerank', methods=['POST'])
def document_rerank():
    """Document search API route"""
    global sem
    
    sem.acquire()
    
    try:
        if not request.json:
            assert False    
        request_info = request.json
        paper_id_list = request_info.get("paper_list", [])
        assert isinstance( paper_id_list, list )
        ranking_source = request_info.get("ranking_source", "")
        keywords = request_info.get("keywords", "")
        nResults = request_info.get( "nResults", 100 )
        
        ## The default reranking method is set to: scibert
        reranking_method = request_info.get("reranking_method", "scibert").lower()
        
        if reranking_method == "sent2vec":
            paper_id_list = rerank_based_on_query2section_similarity(  paper_id_list, ranking_source )
        elif reranking_method == "scibert":
            ## SciBERT reranking
            paper_id_list = rerank_by_scibert( paper_id_list, ranking_source, keywords )
        else:
            assert False, "Wrong reranking method!"
            
        paper_id_list = paper_id_list[:nResults]
        
        json_out = {"response" : paper_id_list}
        print("Doc rerank success.")
    except:
        sem.release()
        abort(400)

    sem.release()  

    return json.dumps(json_out), 201


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument( "-flask_port", type = int, default = 8060 )
    parser.add_argument( "-paper_database_service_address", default = ADDRESS_PAPER_DATABASE_SERVICE )
    parser.add_argument( "-sent2vec_reranking_model_path", default = "/app/models/sent2vec/model_256.bin" )
    parser.add_argument( "-scibert_reranking_model_path", default = "scieditor/document-reranking-scibert" )
    args = parser.parse_args()

    if USE_GPU:
        args.gpu_list = [ gpu.id for gpu in GPUtil.getGPUs() ]
        if len(args.gpu_list) == 0:
            print("Warning: no gpus are available, using CPU")
    else:
        args.gpu_list = []
    
    
    sentence_ranker = SentenceRanker( args.sent2vec_reranking_model_path)
    scibert_reranker = SciBertReranker( model_path = args.scibert_reranking_model_path,
                                        gpu_list = args.gpu_list
                                      )
    
    
    word_tokenizer = RegexpTokenizer("[A-Za-z]+")
    keywords_connector_matcher = re.compile("<.*?>")
    
    sem = threading.Semaphore()


    print("\n\nWaiting for requests...")

    app.run(host='0.0.0.0', port=args.flask_port, threaded=True, debug = True)


