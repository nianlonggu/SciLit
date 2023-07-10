import os,sys
import json
from tqdm import tqdm
import time
import numpy as np

import pickle

from modules.paper_database.database_managers import SqliteClient
from modules.tokenizer.tokenizer import SentenceTokenizer
from modules.ranking.rankers import Sent2vecEncoder

import argparse

def get_sentence_list_from_parsed( parsed ):
    sentence_list = []
    for section in parsed:
        sentence_list.append(str(section.get( "section_title", "" )))
        for para in section.get("section_text",[]):
            for sen in para.get("paragraph_text", []):
                sentence_list.append( str(sen.get("sentence_text","")) )
    return sentence_list

def parse_document( doc_data, sent_tokenizer ):
    ngram_set = set()
        
    ## Title
    title =  str(doc_data.get("Title", "")).strip()          
    ## Abstract
    abstract_sen_list = get_sentence_list_from_parsed(doc_data.get( "Content", {} ).get( "Abstract_Parsed", [] ))
    ## Fullbody
    fullbody_sen_list = get_sentence_list_from_parsed(doc_data.get( "Content", {} ).get( "Fullbody_Parsed", [] ))
    
    sen_list = [ title ] + abstract_sen_list + fullbody_sen_list
    doc_text = sent_tokenizer.tokenize( " ".join( sen_list ) )
    
    return doc_text


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-db_address" )
    parser.add_argument("-collection" )
    parser.add_argument("-embedding_file_name" )
    parser.add_argument("-embedding_file_name_suffix", default = "")
    parser.add_argument("-text_encoder_model_path" )
    parser.add_argument("-start", type = int, default = 0)
    parser.add_argument("-size", type = int, default = 1000000)
    args = parser.parse_args()
    
    
    args.embedding_file_name += args.embedding_file_name_suffix
    
    embedding_folder = os.path.dirname( args.embedding_file_name )
    if not os.path.exists( embedding_folder ):
        os.makedirs( embedding_folder )
    
    text_encoder = Sent2vecEncoder( args.text_encoder_model_path )
    sent_tokenizer = SentenceTokenizer()
    sqlite_client = SqliteClient(db_address = args.db_address )
    
    max_rowid = sqlite_client.get_max_rowid( args.collection )
    
    if args.size == 0:
        args.size = max_rowid 
    end = min( args.start + args.size, max_rowid)
    
    embedding_matrix = []
    doc_id_to_pos_array = -np.ones( max_rowid+1000, dtype = np.int32  )  
    ## make sure 1000 is just a number > 1+8, so that the final len of doc_id_to_pos_array can be a multiple of 8
    pos_to_doc_id_mapper = []
    
    doc_id_list = []
            
    for count in tqdm(range( args.start, end )):
        
        doc_id = count+1
        paper_info = sqlite_client.get_papers( [{"collection":args.collection,"id_field":"id_int", "id_value":doc_id }] )[0]
        
        if paper_info is None or not paper_info.get("RequireIndexing", True):
            continue
            
        pos_to_doc_id_mapper.append( { "collection":args.collection,"id_field": "id_int", "id_type":"int", "id_value": doc_id } )
        doc_id_to_pos_array[ doc_id ] = len( pos_to_doc_id_mapper ) - 1
        doc_id_list.append( doc_id )
            
            
        ## Key part: get the text from document to encode. This may vary over different collections, e.g. for GeneralIndex  
        text_to_encode = parse_document( paper_info, sent_tokenizer )
        embed = text_encoder.encode( [ text_to_encode]  )[0]
        embedding_matrix.append( embed )
    
    embedding_matrix = np.asarray( embedding_matrix ).astype(np.float32)
        
    ## update the actual max_rowid in the current shard    
    if len(doc_id_list) > 0:
        max_rowid = np.max( doc_id_list )
        doc_id_to_pos_array =  doc_id_to_pos_array[ : int(np.ceil( (max_rowid +1) / 8 ) * 8)]    
    
        with open( args.embedding_file_name, "wb" ) as f:
            pickle.dump(  
                {
                    "embedding_matrix":embedding_matrix,
                    "doc_id_to_pos_mapper":{  args.collection : doc_id_to_pos_array  },
                    "pos_to_doc_id_mapper":pos_to_doc_id_mapper
                }, f, -1
            )