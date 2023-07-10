import argparse
import json
import logging
import requests
from datetime import datetime
from flask import Flask, jsonify, abort, make_response, request, Response
from flask_cors import CORS

from rapidfuzz import fuzz

from nameparser import HumanName

import os

import nltk
nltk.download('stopwords')
from nltk.corpus import stopwords
stopwords_set = set(stopwords.words('english'))

logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)
logging.getLogger("gensim").setLevel(logging.WARNING)

# Make Flask application
app = Flask(__name__)
CORS(app)

def get_abbrev_name( name ):
    name_splitted = name.split()
    abbrev_name = " ".join([_[:1] for _ in name_splitted[:-1]] +  name_splitted[-1:] )
    return abbrev_name.lower()

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

def doc_search(**kwargs):
    global args
    res = requests.post( args.document_search_service_address , 
               data = json.dumps( kwargs ), 
               headers = {"Content-Type": "application/json", 'Connection': 'close'} ).json()["response"]
    return res


@app.route('/title-generic-search', methods=['POST'])
def title_generic_search():
    global args

    if not request.json:
        abort(400)
    request_info = request.json

    if "titles" not in request_info:
        abort(400)
    
    ## by default, using the document search api, this can make the title generic search return accurate results, but much slower!
    use_doc_search_api = request_info.get( "use_doc_search_api", True )
    
    query_list = request_info["titles"]
    paper_list = []

    
    for query in query_list:
        if isinstance( query, dict ):
            paper = query
        else:
            paper = { "Title": str(query) }
            
        if "Author" not in paper or paper["Author"] is None or not isinstance( paper["Author"], list ) or len(paper["Author"]) == 0:
            paper["Author"] = []
            paper["First_Author"] = ""
        else:
            try:
                assert isinstance(paper["Author"][0]["GivenName"], str ) and isinstance(paper["Author"][0]["FamilyName"], str )
                paper["First_Author"] = paper["Author"][0]["GivenName"] + " " + paper["Author"][0]["FamilyName"]
            except:
                paper["Author"] = []
                paper["First_Author"] = ""
            
        paper_list.append( paper )
    
    duplicate_res_list = requests.post( args.fast_metadata_search_service_address, 
                                      data = json.dumps(  {
                                          "paper_list":paper_list
                                      } ), 
                                      headers = {"Content-Type": "application/json"} ).json()["response"]

    
    for pos in range( len(paper_list) ):
        if len(duplicate_res_list[pos]) > 0:
            paper_list[pos]["found"] = True
            paper_list[pos]["collection"] = duplicate_res_list[pos][0][ "collection"]
            paper_list[pos]["id_field"] = duplicate_res_list[pos][0][ "id_field"]
            paper_list[pos]["id_type"] = duplicate_res_list[pos][0][ "id_type"]
            paper_list[pos]["id_value"] = duplicate_res_list[pos][0][ "id_value"]
        else:
            paper_list[pos]["found"] = False
        
    for paper in paper_list:
        if not paper["found"] and use_doc_search_api:
            ranking_variable = paper.get( "Title", "" )
            if ranking_variable.strip() == "":
                continue
            try:
                keywords = "Author.FamilyName:"+ paper["Author"][0]["FamilyName"]
            except:
                keywords = ""
            
            search_res = doc_search( ranking_variable = ranking_variable, keywords = keywords, nResults = 100 )[:1]
            if len(search_res) == 0:
                continue

            search_res_content = get_papers( search_res[:1], {"Title":1,"Author":1} )[0]
            if search_res_content is None:
                continue
            try:
                searched_title = search_res_content.get("Title", "")
                searched_author = search_res_content.get("Author",[])
                searched_first_author = searched_author[0]["GivenName"] + " " + searched_author[0]["FamilyName"]
            except:
                searched_title = ""
                searched_first_author = ""
            
            first_author = paper.get( "First_Author", "" )
            if fuzz.ratio( ranking_variable.lower(), searched_title.lower() ) <= args.fuzz_ratio_thres:
                continue
            if first_author != "" and fuzz.ratio( get_abbrev_name( first_author ), get_abbrev_name( searched_first_author ) ) <= args.fuzz_ratio_thres:
                continue
            
            paper["collection"] = search_res[0][ "collection"]
            paper["id_field"] = search_res[0][ "id_field"]
            paper["id_type"] = search_res[0][ "id_type"]
            paper["id_value"] = search_res[0][ "id_value"]
            paper["found"] = True
            
    
    paper_record = get_papers(paper_list,  request_info.get("projection", None  ) )

    if len(paper_record) != len(paper_list):
        abort(400)
    
    for paper_i in range(len(paper_list)):
        if paper_record[paper_i] is not None and paper_list[paper_i]["found"]:
            paper_list[paper_i].update( paper_record[paper_i] )
    
    return json.dumps({"response":paper_list}), 201


PAPER_DATABASE_SERVICE_ADDRESS = os.getenv("PAPER_DATABASE_SERVICE_ADDRESS")
FAST_METADATA_SEARCH_SERVICE_ADDRESS = os.getenv("FAST_METADATA_SEARCH_SERVICE_ADDRESS")
DOCUMENT_SEARCH_SERVICE_ADDRESS = os.getenv("DOCUMENT_SEARCH_SERVICE_ADDRESS")

if __name__ == '__main__':

    parser = argparse.ArgumentParser()    
    parser.add_argument( "-flask_port", type = int, default = 8060 )
    parser.add_argument( "-fuzz_ratio_thres", type = int, default = 90 )
    parser.add_argument( "-paper_database_service_address", default = PAPER_DATABASE_SERVICE_ADDRESS )
    parser.add_argument( "-fast_metadata_search_service_address", default = FAST_METADATA_SEARCH_SERVICE_ADDRESS )
    parser.add_argument( "-document_search_service_address", default = DOCUMENT_SEARCH_SERVICE_ADDRESS )
    args = parser.parse_args()
    
    print("\n\nWaiting for requests...")

    app.run(host='0.0.0.0', port=args.flask_port)



