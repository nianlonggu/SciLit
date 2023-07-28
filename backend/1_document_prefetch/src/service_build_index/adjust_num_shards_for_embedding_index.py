import os
import json
from tqdm import tqdm
import time
import numpy as np
from glob import glob

import pickle
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-embedding_index_folder" )
    parser.add_argument("-embedding_index_name_prefix" )
    parser.add_argument("-num_shards", type = int )
    
    args = parser.parse_args()
    
    embedding_index_names = glob( args.embedding_index_folder + "/" + args.embedding_index_name_prefix + "*" )
    embedding_index_names.sort( key = lambda x:int(x.split("_")[-1]) )
    
    assert len(embedding_index_names) > 0 
    
    print("Start loading embeddings ...")
    
    embed_info = pickle.load(open(embedding_index_names[0],"rb"))
    if len(embedding_index_names) == 1:
        full_embedding_matrix = embed_info["embedding_matrix"]
        full_pos_to_doc_id_mapper = embed_info["pos_to_doc_id_mapper"]
    else:
        shard_size, embed_dim = embed_info["embedding_matrix"].shape
        estimated_max_num_embeddings = max( 200000000, int(shard_size * len(embedding_index_names) * 1.5) )
        
        full_embedding_matrix = np.zeros( ( estimated_max_num_embeddings, embed_dim ), dtype = np.float32 )
        full_pos_to_doc_id_mapper = []
        
        current_embed_idx = 0
        for count, fname in enumerate(embedding_index_names):
            print(count, fname)
            embed_info = pickle.load(open(fname,"rb"))
            full_embedding_matrix[current_embed_idx:current_embed_idx+embed_info["embedding_matrix"].shape[0] ] = embed_info["embedding_matrix"]
            full_pos_to_doc_id_mapper += embed_info["pos_to_doc_id_mapper"]
            current_embed_idx = current_embed_idx+embed_info["embedding_matrix"].shape[0]
        
        full_embedding_matrix = full_embedding_matrix[:current_embed_idx]
        print(full_embedding_matrix.shape)
        
    print("Removing old embeddings ...")
    for count, fname in enumerate(embedding_index_names):
        os.remove( fname )

        
    print("Start dumping embeddings ...")
    new_shard_size = int( np.ceil( full_embedding_matrix.shape[0] / args.num_shards ) )
    
    
    shard_number = 0
    for pos in range( 0,full_embedding_matrix.shape[0], new_shard_size ):
    
        print(pos)
        embedding_matrix = full_embedding_matrix[pos:pos + new_shard_size]
        pos_to_doc_id_mapper = full_pos_to_doc_id_mapper[pos:pos + new_shard_size]
        
        doc_ids_for_collection = {}
        for count, item in enumerate(pos_to_doc_id_mapper):
            if item["collection"] not in doc_ids_for_collection:
                doc_ids_for_collection[ item["collection"] ] = [ list(), list() ]
            doc_ids_for_collection[ item["collection"] ][0].append( item["id_value"] )
            doc_ids_for_collection[ item["collection"] ][1].append(  count  )
        for collection in doc_ids_for_collection:
            doc_ids_for_collection[collection][0] = np.array(doc_ids_for_collection[collection][0])
            doc_ids_for_collection[collection][1] = np.array(doc_ids_for_collection[collection][1])

        doc_id_to_pos_mapper = {}
        for collection in doc_ids_for_collection:
            max_doc_id = np.max(doc_ids_for_collection[collection][0]) 
            doc_id_to_pos_array = np.ones( int(np.ceil( (max_doc_id +1) / 8 ) * 8), dtype = np.int32 ) * (-1)
            doc_id_to_pos_array[doc_ids_for_collection[collection][0]] = doc_ids_for_collection[collection][1]
            doc_id_to_pos_mapper[collection] = doc_id_to_pos_array
            
        with open( args.embedding_index_folder + "/" + args.embedding_index_name_prefix + str(shard_number),"wb" ) as f:
            pickle.dump({
                "embedding_matrix":embedding_matrix,
                "doc_id_to_pos_mapper":doc_id_to_pos_mapper,
                "pos_to_doc_id_mapper":pos_to_doc_id_mapper   
            }, f, -1)
    
        shard_number +=1
    
