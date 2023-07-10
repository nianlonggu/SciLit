import argparse
import json
import logging
import requests
from datetime import datetime
from flask import Flask, jsonify, abort, make_response, request, Response
import subprocess

import re

import os, uuid
import time
import timeout_decorator

from urllib.parse import urlparse, quote

from flask_cors import CORS

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

def encode_url( url ):
    url_scheme = urlparse(url).scheme
    url = url.split(url_scheme + "://")[-1]
    url = quote(url)
    return url_scheme + "://" + url

@timeout_decorator.timeout(3, use_signals=False)
def get_citation_from_crossref( url, style ):
    try:
        res = subprocess.check_output(['curl', '-LH','Accept: text/bibliography; style=%s'%(style), url,])
        res = res.decode("utf-8").strip()
    except:
        res = ""

    if res.lower().strip().endswith("</html>"):
        ## wrong match
        res = ""
    res = res.replace("Crossref. Web.","")
    return res.strip()

def get_citation_from_paper_metadata(  paper, style ):
    ## we treat the bibtex type as inproceedings by default
    try:
        author = paper.get("Author",[])
        title = paper.get("Title","")
        venue = paper.get("Venue","")
        year = paper.get("PublicationDate",{}).get("Year","")   

        if style.lower() == "bibtex":
            if len(author) >0:
                cite_name = author[0].get("FamilyName","") + year
            else:
                cite_name = year
            if cite_name.strip() == "":
                cite_name = str(uuid.uuid4()).replace("-","")[:10]  

            title_info = """title={%s}"""%( title )
            journal_info =  """journal={%s}"""%( venue )        
            author_info = """author={%s}"""%(" and ".join([  "%s, %s"%( author_item.get("FamilyName",""), author_item.get("GivenName","") )   for author_item in author ]))
            year_info = """year={%s}"""%(year)  

            citation_text = "@inproceedings{" + ", ".join( [cite_name, title_info, journal_info,author_info, year_info] )+"}"
        
        elif style.lower() == "mla":
            author_list = []
            for pos,author_item in enumerate(author):
                if pos == 0:
                    author_list.append( "%s, %s"%(  author_item.get("FamilyName",""), author_item.get("GivenName","") ) )
                else:
                    author_list.append( "%s %s"%(  author_item.get("GivenName",""), author_item.get("FamilyName","") ) )    

            if len(author_list)>3:
                author_info = author_list[0] + "et al"
            elif len(author_list)>1:
                author_info = ", ".join( author_list[:-1] ) + ", and " + author_list[-1]
            elif len(author_list)==1:
                author_info = author_list[0]
            else:
                author_info = ""
            author_info += "."  

            title_info = "“"+title.rstrip(".")+".”"
            journal_info = venue
            if year.strip() != "":
                year_info = "(%s)"%(year)
            else:
                year_info = ""  

            citation_text = " ".join(" ".join( [author_info, title_info, journal_info, year_info  ] ).split()) +"."
    except:
        citation_text = ""
    return citation_text

def get_citation( paper, style ):
    if paper.get("DOI","").strip() != "":
        print("calling crossref ...")
        try:
            citation_text = get_citation_from_crossref( "http://dx.doi.org/" + quote( paper.get("DOI","") ), style )
        except:
            print("calling crossref timeout! switch to local database!")
            citation_text = ""
    else:
        citation_text = ""
    if citation_text.strip() == "":
        citation_text = get_citation_from_paper_metadata( paper, style )
    return citation_text

@app.route('/citation-formatting-service', methods=['POST'])
def citation_formatting_service():
    request_info = request.json


    if not request_info or "paper_list" not in request_info or not isinstance( request_info["paper_list"], list ):
        abort(400)

    paper_list = request_info["paper_list"]

    ## return an empty list if the paper_list parameter is an empty list
    if len( paper_list )==0:
        return jsonify({"response":[]}), 201

    paper_content_list = get_papers( paper_list )
    
    results = []
    for count, current_paper in enumerate(paper_content_list):
        
        paper_id_info = paper_list[count]
        
        citation_info = {}
        citation_info["bibtex"] = get_citation(current_paper, "bibtex")
        
        ### add the paper id info to the bib entry
        
        bib_head_matcher = re.compile("(@.+?\{.+?,)")
        citation_info["bibtex"] = bib_head_matcher.sub(lambda m:m.group(0)+""" paperIDInfo={collection:%s, id_value:%s, id_type:%s},"""%( paper_id_info["collection"], str(paper_id_info["id_value"]),  paper_id_info.get("id_type","int")  ),citation_info["bibtex"])
        
        
        time.sleep(0.3)
        citation_info["mla"] = get_citation(current_paper, "mla")

        results.append( citation_info )
    
    json_out = { "response":results }

    return json.dumps(json_out), 201


PAPER_DATABASE_SERVICE_ADDRESS = os.getenv("PAPER_DATABASE_SERVICE_ADDRESS")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()    
    parser.add_argument( "-flask_port", type = int, default = 8060 )
    parser.add_argument( "-paper_database_service_address", default = PAPER_DATABASE_SERVICE_ADDRESS )
    args = parser.parse_args()

    print("\n\nWaiting for requests...")

    app.run(host='0.0.0.0', port=args.flask_port)


