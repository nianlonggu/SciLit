import subprocess
import threading
from tqdm import tqdm
import os
import pmc_parser.pubmed_oa_parser as pp
import numpy as np
import shutil

import argparse

ROOT_DATA_PATH = os.getenv("ROOT_DATA_PATH")
NUM_PROCESSES = int(os.getenv("NUM_PROCESSES"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-xml_root_folder", default =  ROOT_DATA_PATH + "/raw/xml/" )
    parser.add_argument("-raw_jsonl_database_save_path", default = ROOT_DATA_PATH + "/raw/jsonl/DB.jsonl")
    parser.add_argument("-start", type = int, default = None )
    parser.add_argument("-size", type =int, default = None )
    parser.add_argument("-n_processes", type = int, default = NUM_PROCESSES )
    
    args = parser.parse_args()
    
    print("Building raw jsonl file ...")
    print("Number of processes:", args.n_processes)
    
    path_xml = pp.list_xml_path( args.xml_root_folder )
    path_xml.sort()
    
    if args.start is None or args.size is None:
        print("No proper start and size value are specified, processing the whole document ...")
        print("Counting the total number of examples ...")
        args.start = 0
        args.size = len(path_xml)
    else:
        try:
            assert args.start is not None and args.size is not None
            assert args.start >= 0 and args.size >= 0
        except:
            print("Error: Wrong start and size value were provided!")
            os.sys.exit(1)
    
    save_folder = os.path.dirname( args.raw_jsonl_database_save_path )
    try:
        shutil.rmtree( save_folder )
    except:
        pass
    os.makedirs( save_folder )
        
    num_of_examples_per_process = int( np.ceil( args.size / args.n_processes ) )
    print("Start multiple subprocesses ...")
    
    threads = []
    for offset in range( args.start, args.start + args.size, num_of_examples_per_process ):
        t = threading.Thread( target = subprocess.run, args = ( 
                list(map( str, [
                    "python",
                    "convert_xml_to_S2ORC_json.py",
                    "-xml_root_folder", args.xml_root_folder,
                    "-raw_jsonl_database_save_path", args.raw_jsonl_database_save_path,
                    "-save_path_suffix", "_%d"%( offset ),
                    "-start", offset,
                    "-size", min(num_of_examples_per_process, args.start + args.size -  offset )
                   ] ) ) ,
             )  )
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
        
    print("Dumping to the final sqlite database, this may take time ...")
    
    
    
    output_folder = os.path.dirname( args.raw_jsonl_database_save_path )
    output_base_name = os.path.basename( args.raw_jsonl_database_save_path )
    
    flist =[ output_folder +"/"+fname for fname in os.listdir( output_folder ) if fname.startswith(output_base_name+"_") ]
    flist.sort( key = lambda x:int(x.split("_")[-1]) )
    

    with open( args.raw_jsonl_database_save_path, "w" ) as fw:
        for fname in flist:
            print(fname)
            with open( fname ,"r" ) as f:
                for line in f:
                    fw.write(line)
            os.remove( fname )
            
            
    print("All Done!")