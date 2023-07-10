import json
import time
 
import os
import re
import transformers
transformers.logging.set_verbosity_error()
from transformers import AdamW, BertTokenizerFast, BertForNextSentencePrediction
import torch
import torch.nn as nn
import numpy as np

from glob import glob
from tqdm import tqdm
import threading


class SciBertReranker:
    def __init__( self, model_path, max_input_length = 512, batch_size_for_computing_score = 32, gpu_list = [] ):
        
        if len(gpu_list) == 0:
            self.device_list = [ torch.device("cpu") ]
        else:
            self.device_list = [ torch.device("cuda", gpu) for gpu in gpu_list ]
            
        self.tokenizer_list = [ BertTokenizerFast.from_pretrained(model_path) for _ in  self.device_list ]
        
        self.model_list = [ BertForNextSentencePrediction.from_pretrained(model_path).to(device) for device in self.device_list ]
                
        self.paper_scores_list =[ list() for _ in  self.device_list  ]
        
        self.max_input_length = max_input_length
        self.batch_size_for_computing_score = batch_size_for_computing_score
    
    def rerank(self, context, keywords, papers ):
        paper_scores = self.score_papers( context, keywords, papers )
        if len(paper_scores) == 0:
            return []
        indices = np.arange(len(paper_scores)).tolist()
        
        reranked_indices = list(map(list,zip(*sorted( zip(paper_scores,indices), key = lambda x:-x[0] ))))[1]
        
        return reranked_indices
    
    def score_papers( self, context, keywords, papers ):
        for thread_id in range(len(self.paper_scores_list)):
            self.paper_scores_list[thread_id] = list()
        
        if len(papers) == 0:
            return []
        
        num_papers_per_device = int( np.ceil( len(papers)/len(self.device_list) ) )
        
        thread_list = []
        for thread_id, pos in enumerate(range(0, len(papers), num_papers_per_device )):
            t = threading.Thread(target = self.score_papers_kernel, args = ( context, 
                                                                             keywords, 
                                                                             papers[pos:pos+num_papers_per_device],
                                                                             thread_id
                                                                           ) )
            t.start()
            thread_list.append(t)
        
        for t in thread_list:
            t.join()
        
        scores = []
        for thread_id in range(len(self.paper_scores_list)):
            scores += self.paper_scores_list[thread_id]
            self.paper_scores_list[thread_id] = list()
        return scores
        
    
    
    def score_papers_kernel( self, context, keywords, papers, thread_id):
        
        if len(papers) == 0:
            self.paper_scores_list[thread_id] = []
            return 
    
        model = self.model_list[thread_id]
        device = self.device_list[thread_id]
        tokenizer = self.tokenizer_list[thread_id]
    
        query_text = " ".join( [ "keywords:", keywords, "text before citation:", context ]  )
    
        sen_AB_list = []
        for paper_info in papers:
            sen_AB_list.append( ( query_text, " ".join( [ "title:", paper_info["Title"], "abstract:", paper_info["Abstract"]  ] )  ) )
        
        encoded_input = tokenizer( sen_AB_list, max_length = self.max_input_length, padding = True, truncation = True , return_tensors= "pt" )
    
        with torch.no_grad():
            paper_scores = []
            
            for pos in range( 0, encoded_input.input_ids.size(0), self.batch_size_for_computing_score ):
                
                model_out = model( 
                           input_ids = encoded_input.input_ids[pos:pos+self.batch_size_for_computing_score].to(device),
                           token_type_ids = encoded_input.token_type_ids[pos:pos+self.batch_size_for_computing_score].to(device),
                           attention_mask = encoded_input.attention_mask[pos:pos+self.batch_size_for_computing_score].to(device)
                         )
                paper_scores += model_out.logits[:,1].detach().cpu().numpy().tolist()
        self.paper_scores_list[thread_id] = paper_scores