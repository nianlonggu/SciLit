import os,sys,inspect
import argparse
import json
import logging
import requests
from datetime import datetime
from flask import Flask, jsonify, abort, make_response, request, Response
from flask_cors import CORS

from modules.search_substring import search_substring
from modules.highlight_text_given_keywords import TextHighlighterGivenKeywords
from modules.highlight_paper_given_ref_sentences import get_highlighted_paper_given_ref_sentences

logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)
logging.getLogger("gensim").setLevel(logging.WARNING)

# Make Flask application
app = Flask(__name__)
CORS(app)

"""
This is used for the Demo paper, please keep it unchanged.
"""


@app.route('/process', methods=['POST'])
def process():
    global args, headers, text_highlighter_given_keywords
    request_info = request.json
    try:
        mode = request_info["mode"]
        data = request_info["data"]
    except:
        return json.dumps({"response":None}), 201
    
    if mode == "search_substring":
        res = search_substring( 
                    data.get( "substring","" ),
                    data.get( "text", ""),
                              )
        return json.dumps({"response":res}), 201

    
    elif mode == "highlight_text_given_keywords":
        res = text_highlighter_given_keywords.highlight_text(
                    data.get("text",""),
                    data.get("keywords","")
        )
        return json.dumps({"response":res}), 201

    elif mode == "highlight_paper_given_ref_sentences":
        res = get_highlighted_paper_given_ref_sentences(  
                    data["paper"],
                    data["ref_sentences"]
        )
        return json.dumps({"response":res}), 201

    else:
        return json.dumps({"response":None}), 201


if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()    
    parser.add_argument( "-flask_port", type = int, default = 8060 )
    
    args = parser.parse_args()
    
    headers = {"Content-Type": "application/json", 'Connection': 'close'}
    text_highlighter_given_keywords = TextHighlighterGivenKeywords()
    
    
    logging.info("Waiting for requests...")
    app.run(host='0.0.0.0', port=args.flask_port)

