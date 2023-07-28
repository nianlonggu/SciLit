from raw_sqlite_utils import SqliteClient as RawSqliteClient
from normalization_utils import DocumentNormalizer
import json
import time
import numpy as np
import os
from tqdm import tqdm
import argparse


def get_papers(paper_id_list, metadata_sql, pdf_parses_sql, only_metadata = False):
        
    paper_metadata_list = [None if _ is None else json.loads( _["Text"] ) for _ in metadata_sql.get_papers( paper_id_list )]
    if only_metadata:
        for pos in range(len( paper_metadata_list )):
            paper_metadata_list[pos]["pdf_parses"] = {}
            
        result = paper_metadata_list
    else:
        ## if we also want to get the pdf parses, we need to first get the real paper id and use the new id to query pdf parses sqlite!
        mapped_paper_id_list = []
        for paper_id, paper_metadata in zip( paper_id_list, paper_metadata_list ):
            try:
                mapped_paper_id = {
                    "collection":paper_id["collection"],
                    "id_field":"paper_id",  ## here the id_field must be paper_id. This is the only id there is consistent between metadata and pdf_parses!
                    "id_type":"int",
                    "id_value":int( paper_metadata["paper_id"] )
                }
            except:
                mapped_paper_id = None
            mapped_paper_id_list.append(mapped_paper_id)
                    
        paper_fullbody_list = [None if _ is None else json.loads( _["Text"] ) for _ in pdf_parses_sql.get_papers( mapped_paper_id_list )]
            
        for pos in range(len( paper_metadata_list )):
            if paper_metadata_list[pos] is None:
                continue
            if paper_fullbody_list[pos] is None:
                paper_metadata_list[pos]["pdf_parses"] = {}
            else:
                paper_metadata_list[pos]["pdf_parses"] = paper_fullbody_list[pos]
                if paper_metadata_list[pos]["abstract"] is None or paper_metadata_list[pos].get("abstract","").strip() == "":
                    paper_metadata_list[pos]["abstract"] = (" ".join([ para["text"] for para in paper_metadata_list[pos].get("pdf_parses",{}).get("abstract",[]) ])).strip()
                
                
        result = paper_metadata_list

    return result


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser()

    parser.add_argument("-metadata_raw_sql_path" )
    parser.add_argument("-pdf_parses_raw_sql_path" )
    parser.add_argument("-json_schema_path" )
    parser.add_argument("-output_file_name" )
    parser.add_argument("-output_file_name_suffix", default = "" )
    parser.add_argument("-start", type = int, default = 0 )
    parser.add_argument("-size", type =int, default = 0 )
    parser.add_argument("-collection" )
    parser.add_argument("-batch_size", type = int )
    
    args = parser.parse_args()
        
    args.output_file_name += args.output_file_name_suffix
    
    output_folder = os.path.dirname( args.output_file_name )
    if not os.path.exists( output_folder ):
        os.makedirs( output_folder )
    
    metadata_sql = RawSqliteClient( args.metadata_raw_sql_path )
    pdf_parses_sql = RawSqliteClient( args.pdf_parses_raw_sql_path )
    document_normalizer = DocumentNormalizer(args.json_schema_path)

    max_rowid = metadata_sql.get_max_rowid(args.collection)
    if args.size == 0:
        args.size = max_rowid 

    with open( args.output_file_name,"w" ) as fw:
        end = min( args.start + args.size, max_rowid)
        for pos in tqdm(range( args.start, end , args.batch_size  )):
            rowid_list = [ {"collection":args.collection,"id_field":"ROWID","id_value":int(_)+1} for _ in range( pos, min(pos +args.batch_size,  end )  ) ]
            papers = get_papers(rowid_list, metadata_sql, pdf_parses_sql )
            for paper in papers:
                if paper is None:
                    continue
                normalized_paper = document_normalizer.normalize( paper )
                if normalized_paper is None:
                    continue
                fw.write( json.dumps( normalized_paper )+"\n" )