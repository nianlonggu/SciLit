import os,sys,inspect

import argparse
import json
import requests
from datetime import datetime
from flask import Flask, jsonify, abort, make_response, request, Response
from flask_cors import CORS

import time
import numpy as np
import threading
import uuid
import re

from modules.sent2vec_reranker import SentenceRanker


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

def get_sentence_list_from_parsed( parsed ):
    sentence_list = []
    for section in parsed:
        sentence_list.append(str(section.get( "section_title", "" )))
        for para in section.get("section_text",[]):
            for sen in para.get("paragraph_text", []):
                sentence_list.append( str(sen.get("sentence_text","")) )
    return sentence_list

"""
current version of request information.
'ranking_id_value': '', 'ranking_id_field': '', 'ranking_id_type': '', 
'ranking_collection': '', 'keywords': '', 'ranking_variable': '', 
'highlight_source': '', 'viewing_id': '', 'username': ''
"""

def parse_request_for_document_search( request_info ):
    
    """
    Get the ranking source:
    1) If the ranking varaible is provided, then use the ranking variable as the ranking source
    2) If there is no ranking variable, then check if query paper id information is provided. If so, get the paper content and use it as the ranking source; if not, set ranking source as empty string "".
    """
    ranking_variable = request_info.get("ranking_variable", "").strip()
    if ranking_variable != "":
        ranking_source = ranking_variable
    else:
        try:
            paper_record = get_papers( [ {
                "collection":request_info.get("ranking_collection", "").strip(),
                "id_field":str(request_info.get("ranking_id_field", "")).strip(),
                "id_type":"int",
                "id_value":int( str(request_info.get("ranking_id_value", "")).strip() )
            }  ], {"Title":1, "Content.Abstract_Parsed":1, "Content.Fullbody_Parsed":1} )[0]
            
            assert paper_record is not None and paper_record["Title"] != "Not Available"
            ranking_source = " ".join( [ paper_record["Title"] ] + get_sentence_list_from_parsed( paper_record["Content"]["Abstract_Parsed"] + paper_record["Content"]["Fullbody_Parsed"] ))
        except:
            ranking_source = ""
        
    """
    1) Get the keywords;
    2) Normalize the keywords into the standard format. 
    Note: This normalization code will be changed if the frontend organizes the keywords using a different syntax.
    """

    ngram_connector_matcher = re.compile("_(?![pP]arsed)")
    keywords = request_info.get("keywords", "").strip()
    keywords_list = []
    for w in keywords.split("\\t"):
        # w = " ".join( w.replace("_"," ").split())
        w = " ".join( ngram_connector_matcher.sub(" ", w).split() )
        w = w.replace("|","<OR>")
        w = w.replace("!","<NOT>")
        if w.strip() != "":
            keywords_list.append(w.strip())
    keywords = "<AND>".join( keywords_list )
    
    """
    Define the default behavior when either ranking source, keywords, or both are missing.
    """
    if ranking_source == "" and keywords == "":
        print("Warning: Neither ranking source nor keywords are provided!")
    elif ranking_source == "" and keywords != "":
        ranking_source = keywords.replace( "<OR>", " " ).replace( "<NOT>", " " ).replace( "<AND>", " " )
        print("Warning: Only keywords are provided! Using keywords also as ranking source!")
    
            
    return ranking_source, keywords


def prefetch_kernel(ranking_source, keywords, paper_list, nResults, service_address, thread_i, results, timeout):
    try:      
        res = requests.post( service_address , 
               data = json.dumps( {
                       "ranking_source" : ranking_source,
                       "keywords":keywords,
                       "paper_list":paper_list,
                       "nResults":nResults   
               } ), 
               headers = {"Content-Type": "application/json", 'Connection': 'close'},
               timeout = timeout
                           ).json()
        assert isinstance(res["response"] , list)
        res["nMatchingDocuments"] = int(res.get("nMatchingDocuments", 0))
    except:
        res = {
            "response":[],
            "nMatchingDocuments":0
        }
    results[thread_i] = res
    
def prefetch( ranking_source, keywords, paper_list, nResults, service_address_list, timeout ):
    results = {}
    threads = []
    
    for thread_i, service_address  in enumerate( service_address_list ):
        t = threading.Thread( target = prefetch_kernel, args = ( ranking_source, keywords, paper_list, nResults, service_address, thread_i, results, timeout )  )
    
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    
    prefetched_paper_id_list  = []
    nMatchingDocuments = 0
    for thread_i in results:
        prefetched_paper_id_list += results[thread_i]["response"]
        nMatchingDocuments += results[thread_i]["nMatchingDocuments"]
    return prefetched_paper_id_list, nMatchingDocuments


def remove_duplicate( paper_id_list ):
    global sentence_ranker

    tic = time.time()
    dpc_papers_info = [ 
        " ".join([item.get( "Title","" ).lower()] + [  author["FamilyName"].lower()  for author in item.get("Author",[])[:1]   ]  ) ## only use the first author
        for item in get_papers( paper_id_list, { "Title":1, "Author":1 } )]
    
    print("loading paper time:", time.time() - tic)
    
    if len(dpc_papers_info)!=len(paper_id_list):
        return paper_id_list
        
    sims, doc_indices = sentence_ranker.rank_sentences( "dummy query for duplicate checking", dpc_papers_info )
    
    doc_indices_wo_duplicates = []
    sims_wo_duplicates = []
    for pos in range(len(sims)):
        if len(sims_wo_duplicates) == 0 or sims[pos] < sims_wo_duplicates[-1]:
            doc_indices_wo_duplicates.append( doc_indices[pos] )
            sims_wo_duplicates.append( sims[pos] )
 
    return [paper_id_list[idx] for idx in  sorted(doc_indices_wo_duplicates) ]


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

def get_doc_text( paper ):
    section_text_list = get_section_text_list(paper)
    return " ".join(section_text_list)

def rank_based_on_query_to_doc_similarity( paper_id_list, ranking_source, nResults = None ):
    global sentence_ranker
    
    if ranking_source.strip() == "":
        return paper_id_list
    
    tic = time.time()
    
    paper_content_list = get_papers( paper_id_list, { "Title":1, "Content.Abstract_Parsed":1, "Content.Fullbody_Parsed": 1 } )
    if len(paper_content_list) != len(paper_id_list):
        return paper_id_list
    
    print( "load paper time:", time.time() - tic )
    
    try: 
        doc_text_list = [ get_doc_text( paper_content ) for paper_content in paper_content_list ]
        _,  doc_indices = sentence_ranker.rank_sentences( ranking_source, doc_text_list )
        
        selected_papers_to_be_reranked = [ paper_id_list[idx] for idx in doc_indices ]
        
        if nResults is not None:
            selected_papers_to_be_reranked = selected_papers_to_be_reranked[:nResults]
        
    except:
        selected_papers_to_be_reranked = paper_id_list
    
    return selected_papers_to_be_reranked



def rerank( paper_list, ranking_source, keywords, nResults, reranking_method ):
    global args
    res = requests.post( args.document_reranking_service_address , 
               data = json.dumps( {
                   "paper_list" : paper_list,
                   "ranking_source" : ranking_source,
                   "keywords" : keywords, 
                   "nResults" : nResults,
                   "reranking_method": reranking_method
               } ), 
               headers = {"Content-Type": "application/json", 'Connection': 'close'} ).json()["response"]
    return res


@app.route('/document-search', methods=['POST'])
def document_search():
    """Document search API route"""
    global args, sem
        
    sem.acquire()

    try:
        if not request.json:
            assert False    
        request_info = request.json
        
        ## Start querying
        query_start_time = time.time()
        ranking_source, keywords = parse_request_for_document_search( request_info )
        if "paper_list" not in request_info or not isinstance(request_info["paper_list"] , list):
            paper_list = None
        else:
            paper_list = request_info["paper_list"] 
            
        nResults =  request_info.get( "nResults", 100 )
        prefetch_nResults_per_collection = request_info.get( "prefetch_nResults_per_collection", nResults )
        timeout = request_info.get( "timeout", 10 )
        requires_removing_duplicates = request_info.get( "requires_removing_duplicates", True )
        ## rank again based on embedding-based NN search, to get globally closest nResults prefetched candidates
        requires_additional_prefetching = request_info.get( "requires_additional_prefetching", True )
        requires_reranking = request_info.get( "requires_reranking", True )
        reranking_method = request_info.get( "reranking_method", "scibert" )
        
        ## prefetch results from a list of prefetching document search servers        
        prefetched_paper_id_list, nMatchingDocuments = prefetch(
                    ranking_source + " " + keywords.replace( "<OR>", " " ).replace( "<NOT>", " " ).replace( "<AND>", " " ),
                    keywords, paper_list, prefetch_nResults_per_collection, 
                    args.prefetch_service_address_list, 
                    timeout 
            )
        if requires_removing_duplicates:
            ## remove duplicate
            prefetched_paper_id_list = remove_duplicate( prefetched_paper_id_list )
                        
        if requires_additional_prefetching:
            ## rank again based on embedding-based NN search, to get globally closest nResults prefetched candidates
            prefetched_paper_id_list = rank_based_on_query_to_doc_similarity( prefetched_paper_id_list, ranking_source, nResults )
            
        if requires_reranking:
            ## reranking the results gathered from different servers
            selected_papers = rerank( prefetched_paper_id_list, ranking_source, keywords, nResults, reranking_method )
        else:
            selected_papers = prefetched_paper_id_list
            
        stats={
            "DurationTotalSearch":int((time.time() - query_start_time) * 1000),
            "nMatchingDocuments": nMatchingDocuments
        }       
        json_out = { "query_id": str( uuid.uuid4() ), "response" : selected_papers, "search_stats":stats}
        print("Doc search success.")
    except:
        sem.release()
        abort(400)

    sem.release()
    return json.dumps(json_out), 201


@app.route('/click_feedback', methods=['POST'])
def click_feedback():

    startTime = datetime.now()
    if not request.json:
        print("no request.json")
        abort(400)

    if "query_id" not in request.json:
        print("no query_id provided!")
        abort(400)
    else:
        query_id = request.json['query_id']
        print("query_id: " + query_id)

    if "paper_id" not in request.json:
        print("no paper_id provided!")
        abort(400)
    else:
        paper_id = request.json['paper_id']
        print("paper_id: " + json.dumps(paper_id))

    return json.dumps({"response":"Feedback Received!"}), 201


PAPER_DATABASE_SERVICE_ADDRESS = os.getenv("PAPER_DATABASE_SERVICE_ADDRESS")
PREFETCH_SERVICE_ADDRESSES = [ addr.strip() for addr in os.getenv("PREFETCH_SERVICE_ADDRESSES").split(",") ]
RERANK_SERVICE_ADDRESS = os.getenv("RERANK_SERVICE_ADDRESS")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument( "-flask_port", type = int, default = 8060 )
    parser.add_argument( "-paper_database_service_address", default = PAPER_DATABASE_SERVICE_ADDRESS )
    parser.add_argument( "-prefetch_service_address_list", nargs = "+", default = PREFETCH_SERVICE_ADDRESSES )
    parser.add_argument( "-document_reranking_service_address", default = RERANK_SERVICE_ADDRESS )
    parser.add_argument( "-embedding_based_ranking_model_path", default = "/app/models/sent2vec/model_256.bin" )
    args = parser.parse_args()

    
    sentence_ranker = SentenceRanker( args.embedding_based_ranking_model_path)
    
    sem = threading.Semaphore()

    print("\n\nWaiting for requests...")

    app.run(host='0.0.0.0', port=args.flask_port, threaded=True, debug=True)


