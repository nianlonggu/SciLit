import threading
import argparse
import json
import requests
from datetime import datetime
from flask import Flask, jsonify, abort, make_response, request, Response
from flask_cors import CORS
import os, uuid

# Make Flask application
app = Flask(__name__)
CORS(app)


SERVICE_ADDRESSES = [ addr.strip() for addr in os.getenv("SERVICE_ADDRESSES").split(",") ]


def get_data_given_projection( input_data, projection = None ):
    if projection is None:
        return input_data
    output_data = {}
    for nested_key in projection:
        if projection[nested_key] != 1:
            continue
        key_list = nested_key.split(".")
        ## get the value from input_data
        temp_output_data = {}
        value_found = False

        current_input_dict = input_data
        current_temp_output_dict = temp_output_data

        for pos in range(len(key_list)):
            key = key_list[pos]
            try:
                assert key in current_input_dict
            except:
                break
            if pos == len(key_list)-1:
                value = current_input_dict[key]
                current_temp_output_dict[key] = value
                value_found = True
            else:
                current_input_dict = current_input_dict[key]
                current_temp_output_dict[key] = {}
                current_temp_output_dict = current_temp_output_dict[key] 

        if value_found:
            current_output_dict = output_data
            current_temp_output_dict = temp_output_data
            for pos in range(len(key_list)):
                key = key_list[pos]

                if key not in current_output_dict:
                    current_output_dict[key] = current_temp_output_dict[key]
                    break
                if pos == len(key_list)-1:
                    current_output_dict[key] = current_temp_output_dict[key]
                else:
                    current_output_dict = current_output_dict[key]
                    current_temp_output_dict = current_temp_output_dict[key]
    return output_data


def get_papers_kernel(paper_list, projection, service_address, thread_id, results, timeout ):
    try:
        res = requests.post( service_address , 
               data = json.dumps( {
                   "paper_list":paper_list,
                   "projection":projection
               } ), 
               headers = {"Content-Type": "application/json", 'Connection': 'close'},
               timeout = timeout
                           ).json()["response"]
        assert isinstance(res, list) and len( res ) == len(paper_list)
    except:
        res = [ None for _ in range( len(paper_list) )  ]
    results[thread_id] = res
        
        
@app.route('/get-papers', methods=['POST'])
def get_papers():
    global args, sem, placeholder_paper
    
    sem.acquire()
    
    try:
        
        request_info = request.json
        if not request_info:
            assert False
        if "paper_list" not in request_info or not isinstance(request_info["paper_list"], list ):
            assert False
        paper_list = request_info["paper_list"]
        for paper_id in paper_list:
            paper_id["collection"] = paper_id.get("collection",None)
            paper_id["id_field"] = paper_id.get("id_field",None)
            paper_id["id_type"] = paper_id.get("id_type",None)
            try:
                paper_id["id_value"] = int( paper_id["id_value"] )
            except:
                paper_id["id_value"] = None
            
        projection = request_info.get("projection", None)
    
        results = {}
        threads = []

        # for thread_i, service_addr in enumerate( args.get_papers_service_address_list  ):
            
        for thread_i, service_addr in enumerate( [addr for addr in args.get_papers_service_address_list if "2300" not in addr]  + [ "https://bd3e-130-60-23-51.ngrok-free.app/get-papers" ] ):   

            
            t = threading.Thread( target=get_papers_kernel, args=( paper_list, projection, service_addr, thread_i, results, request_info.get("timeout", 10) ) )
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
    
        valid_results = [ results[thread_i] for thread_i in results if len(results[thread_i]) == len(paper_list) ]
        if len(valid_results) == 0:
            final_result = [ None for _ in range(len(paper_list)) ]
        else:
            final_result = list(map( lambda x: ([ sub_res for sub_res in x if sub_res is not None ]+[None])[0], zip( *valid_results )))
            
    except:
        try:
            paper_list = request_info.get( "paper_list", [] )
            assert isinstance(paper_list, list)
        except:
            paper_list = []
        final_result = [ None for _ in range(len(paper_list)) ]
    
    try:
        projection = request_info.get("projection", None)
    except:
        projection = None
        
    
    ## post-processing the documents to make sure it can be correctly rendered on the frontend
    
    projected_placeholder_paper = get_data_given_projection( placeholder_paper, projection )
    for pos in range(len(final_result)):
        if final_result[pos] is None or not isinstance(final_result[pos], dict ) :
            final_result[pos] = projected_placeholder_paper
        
        ## deal with the "_id" problem
        """
        update 21-02-2023: make the _id fixed for each paper
        """
        try:
            paper_id = paper_list[pos]
            _id = str( paper_id["collection"] ) + "_" + str( paper_id["id_value"] )
            final_result[pos]["_id"] = _id
        except:
            final_result[pos]["_id"] = str(uuid.uuid4())
        
        # if "_id" in final_result[pos]:
        #     final_result[pos]["_id"] = str( final_result[pos]["_id"] )
        # elif projection is None or "_id" in projection:
        #     final_result[pos]["_id"] = str(uuid.uuid4())    
        
        ## correct the Month display issue
        if "PublicationDate" in final_result[pos] and "Month" in  final_result[pos]["PublicationDate"]:
            try:
                final_result[pos]["PublicationDate"]["Month"] = str( max( int(float(final_result[pos]["PublicationDate"]["Month"])) -1, 0 ) )
            except:
                final_result[pos]["PublicationDate"]["Month"] = ""     
                    
        
    sem.release()
    return json.dumps({"response":final_result}), 201

if __name__ == '__main__':


    parser = argparse.ArgumentParser()    
    parser.add_argument( "-flask_port", type = int, default = 8060  )
    parser.add_argument( "-placeholder_paper_path", default = "./data/placeholder_paper.json" )
    parser.add_argument( "-get_papers_service_address_list", nargs = "+", default = SERVICE_ADDRESSES )
    args = parser.parse_args()
 
    sem = threading.Semaphore()
    
    ## placeholder paper is used when the paper is not available in our database, this is needed by the fontend to correctly render!
    placeholder_paper = json.load(open( args.placeholder_paper_path,"r"))
    
    print("\n\nWaiting for requests...")

    app.run(host='0.0.0.0', port=args.flask_port, threaded = True, debug=True)

