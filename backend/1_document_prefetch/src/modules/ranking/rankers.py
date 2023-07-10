import os,sys,inspect
# current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
# parent_dir = os.path.dirname(current_dir)
# sys.path.insert(0, parent_dir)
# sys.path.insert(0, current_dir)  
import numpy as np
try:
    import pickle5 as pickle
except:
    import pickle

import GPUtil

## cupy library can only be used when GPUs are available
if GPUtil.getGPUs():
    from .nearest_neighbor_search.modules import BFIndexIP

import multiprocessing, threading
from multiprocessing import Process,JoinableQueue, Pipe
import sent2vec
from modules.tokenizer.tokenizer import SentenceTokenizer

import time
import scann

class Sent2vecEncoder:
    def __init__( self, model_path ):
        self.model = sent2vec.Sent2vecModel()
        self.model.load_model(  model_path )
        self.tokenizer = SentenceTokenizer()

    def tokenize_sentences( self, sentences  ):
        tokenized_sentences = []
        for sen in sentences:
            tokenized_sentences.append( self.tokenizer.tokenize( sen ) )
        return tokenized_sentences

    def encode( self, sentences, tokenize = True ):
        if tokenize:
            sentences = self.tokenize_sentences( sentences )
        return self.model.embed_sentences( sentences )

    def normalize_embeddings(self, embeddings ):
        assert len( embeddings.shape ) == 2
        normalized_embeddings = embeddings /(np.linalg.norm( embeddings, axis =1, keepdims=True )+1e-12)
        return normalized_embeddings

class BaseRanker:
    def __init__( self, embedding_path, 
                    vector_dim,
                    gpu_list = [],
                    internal_precision = "float32",
                    requires_precision_conversion = True,
                    num_threads = 1,
                    normalize_query_embedding = True,
                    **kwargs
                ):
        print("loading embedding!",time.time())
        with open(embedding_path, "rb") as f:
            embedding_info = pickle.load(f)
        print("embeding loaded", time.time())
        doc_embeddings = embedding_info["embedding_matrix"]
        self.doc_id_to_pos_mapper = embedding_info["doc_id_to_pos_mapper"]
        self.pos_to_doc_id_mapper = embedding_info["pos_to_doc_id_mapper"]
        
        print("normalization....", time.time())
        if requires_precision_conversion or internal_precision=="float32":
            self.doc_embeddings = self.normalize_embeddings( doc_embeddings )
        else:
            self.doc_embeddings = doc_embeddings
        
        print("Loading into the ranking module", time.time())
        
        ## check if GPU is available. If not, then overwrite the gpu_list to empty list [], and do not use BFIndexIP that replies on cupy
        if not GPUtil.getGPUs():
            gpu_list = []
        
        if len(gpu_list) == 0:
            # use scann.scann_ops.build() to instead create a TensorFlow-compatible searcher
            # scann searcher can only return up to 100 approximate nearest neighbors        
            self.searcher = scann.scann_ops_pybind.builder(self.doc_embeddings, 10, "dot_product").tree(
                num_leaves = min(2000, self.doc_embeddings.shape[0]), num_leaves_to_search=100, training_sample_size=250000).score_ah(
                2, anisotropic_quantization_threshold=0.2).reorder(100).build()
        else:
            self.index_ip = BFIndexIP( self.doc_embeddings, vector_dim, gpu_list, internal_precision, requires_precision_conversion, num_threads )
        self.gpu_list = gpu_list
        
        self.normalize_query_embedding = normalize_query_embedding
        
        self.vector_dim = vector_dim
        print("warming up ...", time.time())
        self.warmup()
        print("warming up done", time.time())

    def normalize_embeddings(self, embeddings ):
        assert len( embeddings.shape ) == 2
        normalized_embeddings = embeddings /(np.linalg.norm( embeddings, axis =1, keepdims=True )+1e-12)
        return normalized_embeddings
    
    def bfnn( self, query_embedding, normalized_doc_embeddings  ):
        sims = np.matmul(query_embedding, normalized_doc_embeddings.T)[0]
        I = np.argsort( -sims )
        D = sims[I]
        return I, D

    def get_top_n_given_embedding( self, n, query_embedding, indices_range = None ):
        
        assert len( query_embedding.shape ) <= 2
        if len( query_embedding.shape ) == 1:
            query_embedding = query_embedding[ np.newaxis,: ]
        assert len( query_embedding.shape ) == 2 and query_embedding.shape[0] == 1
        if self.normalize_query_embedding:
            query_embedding = self.normalize_embeddings( query_embedding )
                
        if len( self.gpu_list ) == 0:
            if indices_range is None:
                top_n_indices, top_n_similarities = self.searcher.search_batched(query_embedding, final_num_neighbors = 100 )
                top_n_similarities = top_n_similarities[0]
                top_n_indices = top_n_indices[0]
                
                non_nan_indices = ~np.isnan( top_n_indices )
                top_n_similarities = top_n_similarities[ non_nan_indices ][:n]
                top_n_indices = top_n_indices[ non_nan_indices ][:n]
            
            elif len(indices_range) == 0:
                return np.array([]).astype(np.float32), []
            else:
                if len(indices_range) < max( self.doc_embeddings.shape[0] * 0.01, 10000  ):
                    doc_embeddings_subset = self.doc_embeddings[ indices_range ]
                    I, D = self.bfnn( query_embedding, doc_embeddings_subset )    
                    I = indices_range[I]
                    top_n_similarities = D[:n]
                    top_n_indices = I[:n]                    
                else:                
                    top_n_indices, top_n_similarities = self.searcher.search_batched(query_embedding, final_num_neighbors = 100 )
                    top_n_similarities = top_n_similarities[0]
                    top_n_indices = top_n_indices[0]
                
                    non_nan_indices = ~np.isnan( top_n_indices )
                    top_n_similarities = top_n_similarities[ non_nan_indices ]
                    top_n_indices = top_n_indices[ non_nan_indices ]
                    
                    intersect_indices = np.any( top_n_indices[:,np.newaxis] == indices_range[ np.newaxis,: ], axis =1)
                    top_n_similarities = top_n_similarities[intersect_indices][:n]
                    top_n_indices = top_n_indices[intersect_indices][:n]
                            
            return top_n_similarities.astype(np.float32), [ self.pos_to_doc_id_mapper[idx] for idx in top_n_indices ]
        
        else:
            top_n_similarities, top_n_indices = self.index_ip.search( query_embedding , n, indices_range )
            top_n_similarities = top_n_similarities[0]
            top_n_indices = top_n_indices[0]
            
            return top_n_similarities.astype(np.float32), [ self.pos_to_doc_id_mapper[idx] for idx in top_n_indices ]
            
    
    def warmup( self ):
        self.get_top_n_given_embedding( 10, np.random.randn( self.vector_dim ).astype(np.float32) )


class LocalIndexParser:
    def __init__( self, embedding_path ):
        with open(embedding_path, "rb") as f:
            embedding_info = pickle.load(f)
        self.doc_id_to_pos_mapper = embedding_info["doc_id_to_pos_mapper"]
        self.pos_to_doc_id_mapper = embedding_info["pos_to_doc_id_mapper"]
        self.num_docs = embedding_info["embedding_matrix"].shape[0]
        del embedding_info["embedding_matrix"]
        
        self.pre_converted_doc_id_info = {}
        for collection in self.doc_id_to_pos_mapper:
            valid_indices = np.argwhere( self.doc_id_to_pos_mapper.get(collection,np.array([])) >= 0)
            min_idx = np.min(valid_indices)
            max_idx = np.max(valid_indices)
            indices_mask = np.zeros(max_idx - min_idx +1, dtype = np.bool  )
            indices_mask[valid_indices - min_idx] = True
            valid_doc_id_to_pos_mapper = self.doc_id_to_pos_mapper.get(collection,np.array([]))[min_idx: max_idx+1]
            
            
            self.pre_converted_doc_id_info[ collection ] = {
                "min_idx":min_idx,
                "max_idx":max_idx,
                "indices_mask":indices_mask,
                "valid_doc_id_to_pos_mapper":valid_doc_id_to_pos_mapper
            }
        
    def get_indices_range( self, keyword_filtering_results = None, doc_id_list = None ):
        """ doc_id_list structure:
            [ { "collection": "pubmed/arxiv/pmcoa",
                "id_field": "id_int",
                "id_value": 2000
              },
            ]
            Note that the doc id's field must be "id_int", as this is required when building the index
            However, in practice other field might be passed, so in this case a try expect block is needed
        """
        indices_range = None
        
        if keyword_filtering_results is not None:
            indices_range_kwd = []
            for collection in keyword_filtering_results:
                if collection not in self.pre_converted_doc_id_info:
                    continue
                
                min_idx = self.pre_converted_doc_id_info[collection]["min_idx"]
                max_idx = self.pre_converted_doc_id_info[collection]["max_idx"]
                indices_mask = self.pre_converted_doc_id_info[collection]["indices_mask"]
                valid_doc_id_to_pos_mapper = self.pre_converted_doc_id_info[collection]["valid_doc_id_to_pos_mapper"]
                
                k_filter = keyword_filtering_results[collection][min_idx:max_idx+1]
                if len(k_filter) < len(indices_mask):
                    k_filter = np.concatenate([k_filter, np.zeros( len(indices_mask)-len(k_filter) ).astype(np.bool)   ] )
                k_filter = indices_mask & k_filter
                
                indices_range_kwd.append(valid_doc_id_to_pos_mapper[k_filter])
            if len( indices_range_kwd )>0:
                indices_range = np.concatenate(indices_range_kwd)
            else:
                indices_range = None

        if doc_id_list is not None:
            indices_range_given_doc_ids = []
            for doc_id in doc_id_list:
                if doc_id["collection"]  not in self.doc_id_to_pos_mapper:
                    continue
                try:
                    assert doc_id["id_field"] == "id_int"
                    pos = self.doc_id_to_pos_mapper[ doc_id["collection"] ][ int(doc_id["id_value"]) ]
                    assert pos != -1
                except:
                    continue
                indices_range_given_doc_ids.append(pos)
            indices_range_given_doc_ids = np.unique( np.array( indices_range_given_doc_ids ) )
            if indices_range is None:
                indices_range = indices_range_given_doc_ids
            else:
                indices_range = np.intersect1d( indices_range, indices_range_given_doc_ids )

        return indices_range


class Ranker:
    def __init__( self, base_ranker_para_list, num_of_processes_of_gpu = {} ):
        
        ## convert embedding path to absolute path
        for base_ranker_para in base_ranker_para_list:
            base_ranker_para["embedding_path"] = os.path.abspath( base_ranker_para["embedding_path"]  )
        
        rank_process_dict = {}
        self.parsed_index = {}
        self.index_parser_dict = {}
        

        self.num_of_processes_of_gpu = num_of_processes_of_gpu
            
        for base_ranker_para in base_ranker_para_list:
            shard_id = base_ranker_para["shard_id"]

            if len(base_ranker_para.get("gpu_list", [])) >0:
                n_processes_list = []
                for gpu_id in base_ranker_para.get("gpu_list", []):
                    n_processes_list.append( ( gpu_id, self.num_of_processes_of_gpu.get( gpu_id, 0 )) )
                n_processes_list.sort( key = lambda x:x[1] )
                base_ranker_para["gpu_list"] = [ n_processes_list[0][0] ]
                self.num_of_processes_of_gpu[ n_processes_list[0][0] ] = self.num_of_processes_of_gpu.get(n_processes_list[0][0], 0 )+1

            query_q, res_q = Pipe()
            rank_process = Process(target=self.base_rank, args=( res_q, base_ranker_para,))
            
            rank_process.deamon = True
            if len(base_ranker_para.get("gpu_list", [])) >0:
                rank_process_dict[shard_id] = [ query_q,   base_ranker_para["gpu_list"][0] ]
            else:
                rank_process_dict[shard_id] = [ query_q,  None ]
            
            rank_process.start()

        threads = []
        for base_ranker_para in base_ranker_para_list:
            shard_id = base_ranker_para["shard_id"]
            t = threading.Thread( target = self.assign_index_parser_dict, args = ( shard_id, base_ranker_para["embedding_path"] )  )
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        
        ## make sure all shards are ready, and record the shards that did not start successfully!
        failed_shard_ids = []
        for shard_id in rank_process_dict:
            is_running = rank_process_dict[shard_id][0].recv()
            if not is_running or shard_id not in self.index_parser_dict or self.index_parser_dict[shard_id] is None:
                failed_shard_ids.append(shard_id)
        self.rank_process_dict = rank_process_dict
        
        ## Delete the shards that did not start successfully!
        for shard_id in failed_shard_ids:
            print("Deleting failed shard: "+shard_id)
            self.delete_shard( shard_id )
        
        print("All processes are ready!")


    def update_shards( self, updating_ranker ):

        self.index_parser_dict.update( updating_ranker.index_parser_dict )
        self.num_of_processes_of_gpu.update(updating_ranker.num_of_processes_of_gpu )
        self.rank_process_dict.update( updating_ranker.rank_process_dict )


    def delete_shard( self, shard_id ):

        if shard_id in self.rank_process_dict:
            self.rank_process_dict[shard_id][0].send( None )            
            gpu_id = self.rank_process_dict[shard_id][1]
            if gpu_id is not None:
                self.num_of_processes_of_gpu[gpu_id] = max(self.num_of_processes_of_gpu.get(gpu_id,0)-1,0)
            del self.rank_process_dict[shard_id]

        if shard_id in self.index_parser_dict:
            del self.index_parser_dict[shard_id]
                
           
    def assign_index_parser_dict( self, shard_id, embedding_path ):
        try:
            self.index_parser_dict[shard_id] = LocalIndexParser(embedding_path)
        except:
            print("Error: LocalIndexParser initialization failed!")
            self.index_parser_dict[shard_id] = None
    
    def parse_local_index( self, shard_id , keyword_filtering_results = None , doc_id_list = None  ):
        if shard_id in self.index_parser_dict:
            local_index = self.index_parser_dict[shard_id].get_indices_range( keyword_filtering_results  , doc_id_list )
        else:
            local_index = None

        if local_index is None:
            self.parsed_index[shard_id] = {"packed":False, "value": None}
        else:
            if shard_id in self.index_parser_dict and len(local_index) > int(self.index_parser_dict[shard_id].num_docs / 32):
                bool_arr = np.zeros( np.max(local_index)+1 , dtype = np.uint8)
                bool_arr[local_index] = 1
                packed_local_index = np.packbits(bool_arr)
                self.parsed_index[shard_id] = { "packed":True, "value":packed_local_index}
            else:
                self.parsed_index[shard_id] = {"packed":False, "value": local_index}
                
    
    def base_rank(self, res_q, base_ranker_para ):
        try:
            base_ranker = BaseRanker( **base_ranker_para )
            print( "shard id: %s is waiting for response ..."%(str( base_ranker_para["shard_id"] )), flush = True )
            is_running = True
        except:
            print( "Error: shard id: %s initialization failed!"%(str( base_ranker_para["shard_id"] )), flush = True  )
            is_running = False
        
        res_q.send( is_running )
        
        while is_running:
            
            query = res_q.recv()

            if query is None:
                break
            
            indices_range = query["indices_range"]
            if not indices_range["packed"]:
                query["indices_range"] = indices_range["value"]
            else:
                query["indices_range"] = np.argwhere( np.unpackbits(indices_range["value"]))[:,0]
                    
            rank_res = base_ranker.get_top_n_given_embedding( **query )

            res_q.send( rank_res )

    
    def get_top_n_given_embedding( self, n, query_embedding, keyword_filtering_results = None , doc_id_list = None, ranking_shard_id_list = None ):

        if ranking_shard_id_list is None:
            ranking_shard_id_list = list(self.rank_process_dict.keys())
        else:
            ranking_shard_id_list = list(set(ranking_shard_id_list) & set(self.rank_process_dict.keys()))

        tic = time.time()
        threads = []
        for shard_id in ranking_shard_id_list:
            t = threading.Thread( target = self.parse_local_index, args = ( shard_id, keyword_filtering_results, doc_id_list )  )
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        tac = time.time()
        print("parsing time",tac-tic)
        
        tic = time.time()
        
        for shard_id in ranking_shard_id_list:
            if self.rank_process_dict.get(shard_id,None) is not None and self.parsed_index.get( shard_id, None ) is not None:
                self.rank_process_dict[shard_id][0].send(  { "n":n, "query_embedding":query_embedding, "indices_range":self.parsed_index[shard_id] }  )   
                
        tac = time.time()
        print("sending query time",tac-tic)

        self.parsed_index = {}
        
        res_list = []
        for shard_id in ranking_shard_id_list:
            if shard_id in self.rank_process_dict:
                res_list.append(self.rank_process_dict[shard_id][0].recv())
        
        sim_list = []
        doc_id_list = []
        for res in res_list:
            sim_list.append( res[0] )
            doc_id_list += res[1]
        if len(sim_list)>0:
            sim_list = np.concatenate( sim_list )
            top_n_indices = np.argsort( -sim_list )[:n]
        else:
            sim_list = np.array([])
            top_n_indices = np.array([])
                    
        return [ doc_id_list[idx] for idx in top_n_indices  ]
    
class SentenceRanker:
    def __init__( self, model_path ):
        self.encoder = Sent2vecEncoder(model_path)

    def encode(self, sentences, tokenize = True):
        return self.encoder.encode( sentences, tokenize )

    def normalize_embeddings(self, embeddings ):
        assert len( embeddings.shape ) == 2
        normalized_embeddings = embeddings /(np.linalg.norm( embeddings, axis =1, keepdims=True )+1e-12)
        return normalized_embeddings

    def rank_sentences( self, query_sentence, sentences_to_be_ranked, top_n = None ):
        if len(sentences_to_be_ranked) == 0:
            return np.array([]), np.array([])
        query_embedding = self.normalize_embeddings(self.encode( [query_sentence] ))[0]
        sentences_embedding = self.normalize_embeddings(self.encode( sentences_to_be_ranked ))
        sims = np.dot(sentences_embedding, query_embedding)
        if top_n is None:
            top_n = len(sentences_to_be_ranked)
        I = np.argsort( -sims )[:top_n]  
        D = sims[I]
        return D,I
    
    def get_scores( self, query_sentence, sentences_to_be_ranked ):
        if len(sentences_to_be_ranked) == 0:
            return np.array([]), np.array([])
        query_embedding = self.normalize_embeddings(self.encode( [query_sentence] ))[0]
        sentences_embedding = self.normalize_embeddings(self.encode( sentences_to_be_ranked ))
        sims = np.dot(sentences_embedding, query_embedding)
        
        return sims