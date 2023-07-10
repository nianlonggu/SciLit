import json
import time

import os
import re
import transformers
transformers.logging.set_verbosity_error()
from transformers import AdamW, BertTokenizerFast, BertForTokenClassification
import torch
import torch.nn as nn
import numpy as np

from glob import glob
from tqdm import tqdm

class BertSumExtractor:
    def __init__(self, model_path, gpu = None, max_input_length = 512, compute_batch_size = 8, thres = 0.4):
        if gpu is None:
            self.device = torch.device("cpu")
        else:
            self.device = torch.device("cuda", gpu)
        
        self.tokenizer = BertTokenizerFast.from_pretrained( model_path )
        self.model = BertForTokenClassification.from_pretrained( model_path ).to(self.device)
        self.max_input_length = max_input_length
        self.compute_batch_size = compute_batch_size
        self.thres = thres
        

    def extract(self, text_batch, return_sentence_position = True ):
        if len(text_batch) == 0:
            if return_sentence_position:
                return [],[]
            else:
                return []
        
        model = self.model
        tokenizer = self.tokenizer
        device = self.device
        max_input_length = self.max_input_length
        compute_batch_size = self.compute_batch_size
        thres = self.thres
        
        input_ids_batch = []
        token_type_ids_batch = []
        attention_mask_batch = []
        cls_token_indices_batch = []
        
        for text in text_batch:
            input_text = "".join( [ tokenizer.cls_token + sen.replace(tokenizer.cls_token, "") for sen in text ])
            input_ids = np.asarray( tokenizer( input_text, add_special_tokens=False, 
                                              max_length = max_input_length, 
                                              padding="max_length", truncation=True ).input_ids)
            
            token_type_ids = (np.mod(np.cumsum(input_ids == tokenizer.cls_token_id),2) == 0).astype(np.int32)
            attention_mask = (input_ids != tokenizer.pad_token_id).astype(np.int32)
        
            cls_token_indices = np.sort(np.argwhere( input_ids == tokenizer.cls_token_id )[:,0])
            
            input_ids_batch.append( input_ids )
            token_type_ids_batch.append( token_type_ids )
            attention_mask_batch.append( attention_mask )
            cls_token_indices_batch.append( cls_token_indices )
            
        input_ids_batch = torch.from_numpy( np.asarray( input_ids_batch ) ).to(device)
        token_type_ids_batch = torch.from_numpy( np.asarray( token_type_ids_batch ) ).to(device)
        attention_mask_batch = torch.from_numpy( np.asarray( attention_mask_batch ) ).to(device)
        
        
        with torch.no_grad():
            all_scores = []
            
            for offset in range( 0, input_ids_batch.size(0), compute_batch_size ):
                model_out = model( input_ids = input_ids_batch[offset:offset+compute_batch_size], 
                           token_type_ids = token_type_ids_batch[offset:offset+compute_batch_size], 
                           attention_mask = attention_mask_batch[offset:offset+compute_batch_size]
                             )
                scores = model_out.logits[:,:,0].sigmoid().detach().cpu().numpy()
                all_scores.append(scores)
            
            scores = np.concatenate( all_scores, axis = 0 )
        
        extracted_indices_batch = []
        for batch_i in range(len( text_batch )):
            extracted_indices = []
            for idx, cls_pos in enumerate( cls_token_indices_batch[batch_i] ):
                if  idx < len(text_batch[batch_i]) and scores[batch_i][cls_pos] >= thres:
                    extracted_indices.append(idx)
            
            extracted_indices_batch.append( extracted_indices )
        
        extracted_summaries_batch = []
        for batch_i, extracted_indices in enumerate(extracted_indices_batch):
            extracted_summaries_batch.append( [text_batch[batch_i][idx] for idx in extracted_indices ] )
        
        if return_sentence_position:
            return extracted_summaries_batch, extracted_indices_batch
        else:
            return extracted_summaries_batch