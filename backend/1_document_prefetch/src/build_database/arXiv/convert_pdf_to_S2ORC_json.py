import os
from tqdm import tqdm
import re
import subprocess
import threading
import time
import numpy as np
import datetime
import argparse

import shutil
import requests, json


PDF2JSON_HOME = os.getenv("PDF2JSON_HOME")
ROOT_DATA_PATH = os.getenv("ROOT_DATA_PATH")
NUM_PROCESSES = os.getenv("NUM_PROCESSES")

def parse_pdf( pdf_name, thread_id ):
    global args, running_table
    
    pdf_dirname = os.path.dirname( pdf_name )
    json_dirname = pdf_dirname.replace("pdf","json")
    temp_xml_dirname = pdf_dirname.replace("pdf","temp_xml")
    
    # This method (calling API) is better, because it better handles the concurrent reqeusts
    res = requests.post(
        "http://localhost:8061/parse-pdf",
        files = {"pdf":open(pdf_name,"rb").read()}
    ).json()["response"]
    
    if res is not None and res != {}:
        if not os.path.exists( json_dirname ):
            os.makedirs( json_dirname, exist_ok=True )
        
        json_name = os.path.basename( pdf_name ).lower()
        if json_name.endswith(".pdf"):
            json_name = json_name[:-4]
        json_name = json_dirname + "/"+ json_name + ".json"
        json.dump( res, open(json_name, "w") )
        
    # subprocess.run( list(map( str, [
    #                     "python",
    #                     args.s2orc_pdf2json_script_path,
    #                     "-i", pdf_name,
    #                     "-t", temp_xml_dirname,
    #                     "-o", json_dirname
    #                    ] ) ) )  
    # #, stdout=subprocess.DEVNULL will trigger error!

    running_table[thread_id] = False


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser()
    parser.add_argument("-pdf_folder", default = ROOT_DATA_PATH + "/raw/pdf/" )
    parser.add_argument("-temp_xml_folder", default = ROOT_DATA_PATH + "/raw/temp_xml/" )
    parser.add_argument("-json_folder", default = ROOT_DATA_PATH + "/raw/json/" )
    parser.add_argument("-s2orc_pdf2json_script_path", default = PDF2JSON_HOME + "/doc2json/grobid2json/process_pdf.py" )
    parser.add_argument("-n_processes", type = int, default = NUM_PROCESSES)
    parser.add_argument("-max_num_pdfs", type = int, default = None)

    args = parser.parse_args()
    
    try:
        shutil.rmtree( args.temp_xml_folder )
    except:
        pass
    try:
        shutil.rmtree( args.json_folder )
    except:
        pass
        
    version_suffix = re.compile("v\d+?.pdf$")
    all_pdf_list = []
    for root, _ , files in tqdm(os.walk(args.pdf_folder)):
        for file_name in files:
            all_pdf_list.append( root + "/"+ file_name )
    all_pdf_list.sort() 

    unique_pdf_list  = []
    for fname in tqdm(all_pdf_list):
        if len(unique_pdf_list) == 0:
            unique_pdf_list.append( fname )
        elif version_suffix.sub("", os.path.basename( unique_pdf_list[-1] ) ) != version_suffix.sub("", os.path.basename( fname ) ):
            unique_pdf_list.append( fname )
        else:
            unique_pdf_list[-1] = fname
            
    running_table = { tid:False  for tid in range( args.n_processes )}
    current_pos = 0
    
    if args.max_num_pdfs is not None:
        max_num_pdfs = args.max_num_pdfs
    else:
        max_num_pdfs = len(unique_pdf_list)
    
    start_time = time.time()
    while True:
        for thread_id in running_table:
            if not running_table[thread_id]:
                if current_pos < max_num_pdfs:
                    running_table[thread_id] = True
                    threading.Thread( target = parse_pdf, args =( unique_pdf_list[current_pos], thread_id ) ).start()
                    current_pos += 1
                    
                    if current_pos % 100 == 0:
                        progress = 100 * current_pos / max_num_pdfs
                        current_time = time.time()
                        
                        eta_time = ( current_time - start_time ) / ( progress / 100 ) * ( 1 - progress / 100 )
                        eta_time_string = str(datetime.timedelta(seconds = int(eta_time)))
                        
                        print("\r%.2f%%|%s%s| ETA: %s"%(progress, "█"*( int( np.ceil(progress) ) ), " "*(100 - int(np.ceil(progress)) ), eta_time_string ), end = "", flush = True)
        
        if np.all([ not running_table[thread_id] for thread_id in running_table ]) and current_pos >= max_num_pdfs:
            break
        
        time.sleep(0.1) 

    print("All Done!")

