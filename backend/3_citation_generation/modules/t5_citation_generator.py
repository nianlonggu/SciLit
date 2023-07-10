import json
import time

import os
import re

from transformers import AdamW, T5Tokenizer, T5ForConditionalGeneration
import torch
import torch.nn as nn
import numpy as np
from rouge_score import rouge_scorer

from glob import glob
from tqdm import tqdm

import threading


class CitationGenerator:
    def __init__( self, model_path, max_input_length = 512, max_output_length = 75, 
                        batch_size_for_generation = 8,
                        num_beams = 4, early_stopping= True,
                        gpu_list = []  ):
        
        if len(gpu_list) == 0:
            self.device_list = [ torch.device("cpu") ]
        else:
            self.device_list = [ torch.device("cuda", gpu) for gpu in gpu_list ]
        
        self.tokenizer_list = [ T5Tokenizer.from_pretrained(model_path) for _ in  self.device_list ]
        self.model_list = [ T5ForConditionalGeneration.from_pretrained(model_path).to(device) for device in self.device_list ]
        
        self.gen_text_list = [ list() for _ in self.device_list ]
        
        self.max_input_length = max_input_length
        self.max_output_length = max_output_length
        self.batch_size_for_generation = batch_size_for_generation
        
        self.num_beams = num_beams
        self.early_stopping = early_stopping
    
    def generate_citation( self, context_list, keywords_list, papers):
        for thread_id in range(len(self.gen_text_list)):
            self.gen_text_list[thread_id] = list()
        
        if len(papers) == 0 or len(context_list) != len(papers) or len(keywords_list) != len(papers) :
            return []
        
        num_papers_per_device = int( np.ceil( len(papers)/len(self.device_list) ) )
        
        thread_list = []
        for thread_id, pos in enumerate(range(0, len(papers), num_papers_per_device )):
            t = threading.Thread(target = self.generate_citation_kernel, args = ( 
                                context_list[pos:pos+num_papers_per_device], 
                                keywords_list[pos:pos+num_papers_per_device], 
                                papers[pos:pos+num_papers_per_device],
                                thread_id
                                                                           ) )
            t.start()
            thread_list.append(t)
        
        for t in thread_list:
            t.join()
        
        all_gen_texts = []
        for thread_id in range(len(self.gen_text_list)):
            all_gen_texts += self.gen_text_list[thread_id]
            self.gen_text_list[thread_id] = list()
        return all_gen_texts
    
    
    def generate_citation_kernel(self, context_list, keywords_list, papers, thread_id ):
        if len(papers) == 0 or len(context_list) != len(papers) or len(keywords_list) != len(papers) :
            self.gen_text_list[thread_id] = []
            return 
    
        model = self.model_list[thread_id]
        device = self.device_list[thread_id]
        tokenizer = self.tokenizer_list[thread_id]
        
        all_gen_texts = []
        for pos in range( 0, len(papers), self.batch_size_for_generation ):
            input_text_batch = []
            for count, paper in enumerate(papers[pos:pos+self.batch_size_for_generation]):
                input_text_batch.append( 
                    " ".join(
                        [
                                "keywords:", keywords_list[pos:pos+self.batch_size_for_generation][count],
                                "text before citation:", context_list[pos:pos+self.batch_size_for_generation][count],
                                "cited title:", paper.get("Title",""),
                                "cited abstract:", paper.get("Abstract","")
                        ]
                    )
                )
                
            input_token_ids_batch = tokenizer( input_text_batch, 
                                             max_length = self.max_input_length, 
                                             padding= True, truncation = True,
                                             return_tensors= "pt"
                                           ).input_ids.to(device)
                
            gen_token_ids = model.generate( input_token_ids_batch, 
                                            num_beams= self.num_beams, 
                                            early_stopping= self.early_stopping, 
                                            max_length = self.max_output_length )
            
            gen_text_batch = [ sen.replace( "<pad>","" ).replace("</s>","").replace("<unk>","")
                               for sen in tokenizer.batch_decode(gen_token_ids, skip_special_tokens = False) ]
            
            all_gen_texts += gen_text_batch
        
        self.gen_text_list[thread_id] = all_gen_texts
