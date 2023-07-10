import threading
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

def check_duplicate_kernel(paper_list, service_address, thread_id, results, timeout ):
    try:
        res = requests.post( service_address , 
               data = json.dumps( {
                   "paper_list":paper_list
               } ), 
               headers = {"Content-Type": "application/json", 'Connection': 'close'},
               timeout = timeout
                           ).json()["response"]
        assert isinstance(res, list) and len( res ) == len(paper_list)
    except:
        res = [ list() for _ in range( len(paper_list) )  ]
    results[thread_id] = res

@app.route('/check-duplicate', methods=['POST'])
def check_duplicate():
    global args, sem
    
    sem.acquire()
    try:
        request_info = request.json
        if not request_info:
            assert False
        if "paper_list" not in request_info or not isinstance(request_info["paper_list"], list ):
            assert False
            
        paper_list = request_info["paper_list"]
    
        results = {}
        threads = []
        for thread_i, service_addr in enumerate( args.duplicate_checking_service_address_list ):
                
            t = threading.Thread( target=check_duplicate_kernel, args=( paper_list,service_addr, thread_i, results, request_info.get("timeout", 10)  ) )
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
    
        valid_results = [ results[thread_i] for thread_i in results if len(results[thread_i]) == len(paper_list) ]
        if len(valid_results) == 0:
            final_result = [ list() for _ in range(len(paper_list)) ]
        else:
            final_result = list(map( lambda x: [ sub_item for sub_res in x for sub_item in sub_res ][:1],zip( *valid_results )))
    except:
        try:
            paper_list = request_info.get("paper_list", [])
            assert isinstance(paper_list, list)
        except:
            paper_list = []
        final_result = [ list() for _ in range(len(paper_list)) ]
    sem.release()
    return json.dumps({"response":final_result}), 201


DUPLICATE_CHECKING_SERVICE_ADDRESS_LIST = [ addr.strip() for addr in os.getenv("DUPLICATE_CHECKING_SERVICE_ADDRESS_LIST").split(",") ]

if __name__ == '__main__':

    parser = argparse.ArgumentParser()    
    parser.add_argument( "-flask_port", type = int, default = 8060  )
    parser.add_argument( "-duplicate_checking_service_address_list", nargs = "+", default = DUPLICATE_CHECKING_SERVICE_ADDRESS_LIST )
    args = parser.parse_args()
 
    sem = threading.Semaphore()

    print("\n\nWaiting for requests...")

    app.run(host='0.0.0.0', port=args.flask_port, threaded = True, debug=True)