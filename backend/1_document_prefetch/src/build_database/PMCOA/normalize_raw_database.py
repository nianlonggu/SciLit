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

        
    with open( args.output_file_name,"w" ) as fw:
        with open( args.raw_database_path,"r" ) as f:
            for count, line in enumerate(tqdm(f)):
                if count < args.start:
                    continue
                if args.size != 0 and count >= args.start + args.size:
                    break
                
                paper = json.loads(line)
                
                normalized_paper = document_normalizer.normalize( paper )
                if normalized_paper is None:
                    continue
                fw.write( json.dumps( normalized_paper )+"\n" )
        