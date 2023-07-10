import json
import time
import numpy as np
from normalization_utils import DocumentNormalizer
import os
from tqdm import tqdm
import argparse




if __name__ == "__main__":
    
    parser = argparse.ArgumentParser()

    parser.add_argument("-raw_database_path" )
    parser.add_argument("-json_schema_path" )
    parser.add_argument("-output_file_name" )
    parser.add_argument("-output_file_name_suffix", default = "" )
    parser.add_argument("-start", type = int, default = 0 )
    parser.add_argument("-size", type =int, default = 0 )
    
    
    args = parser.parse_args()
    
    args.output_file_name += args.output_file_name_suffix
    
    output_folder = os.path.dirname( args.output_file_name )
    if not os.path.exists( output_folder ):
        os.makedirs( output_folder )
    
    document_normalizer = DocumentNormalizer(args.json_schema_path)
    
    all_json_files = []
    for root , _, files in os.walk(args.raw_database_path):
        for file_name in files:
            if file_name.endswith(".json"):
                all_json_files.append( root + "/" + file_name )
    all_json_files.sort()
    
    if args.size == 0:
        args.size = len(all_json_files)
    
    fw = open( args.output_file_name,"w" )
    for json_file in tqdm(all_json_files[ args.start : args.start + args.size  ]):
        paper =  json.load( open( json_file,"r" ) )
        try:
            pub_date =  os.path.basename(json_file).split(".")[0]
            pub_year = int(pub_date[:2])
            if pub_year < 50:
                pub_year = 2000 + pub_year
            else:
                pub_year = 1900 + pub_year
            pub_year = str( pub_year )
            pub_month = str(int(pub_date[2:]))
        except:
            pub_year = ""
            pub_month = ""
            
        normalized_paper = document_normalizer.normalize( paper )
        if normalized_paper is None:
            continue
        
        normalized_paper["PublicationDate"] = { "Year":pub_year, "Month":pub_month }
        
        fw.write( json.dumps( normalized_paper )+"\n" )
        
    fw.close()
    


# In[ ]:




