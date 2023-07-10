import os,sys,inspect
import numpy as np
import sent2vec
from .tokenizer import SentenceTokenizer

import time

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