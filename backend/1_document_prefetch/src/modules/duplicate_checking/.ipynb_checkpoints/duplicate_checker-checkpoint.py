from array import array
import os
from tqdm import tqdm
import re

import nltk
from nltk.tokenize import  RegexpTokenizer
from nltk.stem.snowball import SnowballStemmer
from functools import lru_cache
from nltk.corpus import stopwords
nltk.download('stopwords')

from rapidfuzz import fuzz

class SentenceTokenizer:
    def __init__(self ):
        self.tokenizer = RegexpTokenizer( "[A-Za-z]+"  )
        self.stemmer = SnowballStemmer("english")
        self.general_stopwords = set(stopwords.words('english'))

    @lru_cache(100000)
    def stem( self, w ):
        return self.stemmer.stem(w)
    
    def tokenize(self, sen ):
        sen = sen.lower()
        sen = " ".join( [ w for w in sen.split() if w not in self.general_stopwords  ] )
        wlist = self.tokenizer.tokenize( sen )
        sen = " ".join( [ self.stem(w.lower()) for w in wlist ] )
        return sen


class DuplicateChecker:
    def __init__(self, data_path):
        """
            The file at data_path has the following format:
            collection \t id_int \t md5 \t doi \t title \t title_head \t title_tail \t first_author:
            
            title_head is the first 5 words of the title;
            title_tail is the last 5 words of the title;
            These two fields are used when there is no good match with the title due small differences
            
        """
        self.field_separator_regx = "\u0888<SEP>\u0888"
        self.field_separator_matcher = re.compile( self.field_separator_regx )
        
        self.head_tail_len = 5
        
        self.fuzz_ratio_thres = 90
        
        self.stopwords_set = set(stopwords.words('english'))
        
        self.sent_tok = SentenceTokenizer()
        self.data_path = data_path
        self.inv_idx = {}
        self.title_record = {}
        self.first_author_record = {}
        
        data_folder = os.path.dirname(data_path)
        if not os.path.exists( data_folder ):
            os.makedirs( data_folder )
        
        if not os.path.exists( data_path ):
            with open(data_path,"a") as f:
                pass
        with open( data_path, "r" ) as f:
            for line in tqdm(f):
                try:
                    collection, id_int, md5, doi, title, title_head, title_tail, first_author =[item.strip() for item in  self.field_separator_matcher.split( line) ]
                except:
                    print("Warning: line data broken!")
                    continue
                id_int = int(id_int)
                
                if collection not in self.inv_idx:
                    self.inv_idx[collection] = {}
                
                for key in set([ md5, doi, title, title_head, title_tail, first_author ]):
                    if key == "":
                        continue
                    if key not in self.inv_idx[collection] :
                        self.inv_idx[collection][key] = id_int
                    else:
                        if not isinstance(self.inv_idx[collection][key], array):
                            self.inv_idx[collection][key] = array( "I", [ self.inv_idx[collection][key] ] )
                        self.inv_idx[collection][key].append( id_int )
                        
                if collection not in self.title_record:
                    self.title_record[ collection ] = {}
                self.title_record[ collection ][ id_int ] = title
                
                if collection not in self.first_author_record:
                    self.first_author_record[ collection ] = {}
                self.first_author_record[ collection ][ id_int ] = self.get_abbrev_name(first_author)
                
    def tokenize( self, sen ):
        return self.sent_tok.tokenize( sen )
    
    def get_doc_ids( self, key ):
        doc_ids = {}
        for collection in self.inv_idx:
            sub_doc_ids = self.inv_idx[collection].get( key, None)
            if sub_doc_ids is not None:
                if not isinstance( sub_doc_ids, array ):
                    sub_doc_ids = list([sub_doc_ids])
                else:
                    sub_doc_ids = list(sub_doc_ids)
                doc_ids[collection] = sub_doc_ids
        return doc_ids
    
    def merge_doc_ids(self, doc_ids_1, doc_ids_2 ):
        doc_ids = doc_ids_1.copy()
        for collection in doc_ids_2:
            if collection not in doc_ids:
                doc_ids[collection] = []
            doc_ids[collection] = list( set( doc_ids[collection] + doc_ids_2[collection] ) )
        return doc_ids
    
    def get_abbrev_name( self, name ):
        name_splitted = name.split()
        abbrev_name = " ".join([_[:1] for _ in name_splitted[:-1]] +  name_splitted[-1:] )
        return abbrev_name.lower()
        
    def check( self, md5 = "",  doi = "", title = "", first_author = "", tokenize = True):
        if tokenize:
            md5 = md5.lower().strip()
            doi = doi.lower().strip()
            first_author = self.tokenize(first_author)
            
            title = self.tokenize(title)
            title_words = title.split()
            title_head = " ".join( title_words[:self.head_tail_len] )
            title_tail = " ".join( title_words[-self.head_tail_len:] )
        
        first_author = self.get_abbrev_name( first_author )
            
        if md5 == "" and doi == "" and title =="":
            return []
        
        if md5 != "":
            doc_ids = self.get_doc_ids( md5 )
            res = []
            for collection in doc_ids:
                for id_value in doc_ids[collection]:
                    res.append( { 
                        "collection":collection,
                        "id_field": "id_int", 
                        "id_type": "int",
                        "id_value":id_value
                    }   )
            return res  ## if md5 is provided, then we find the exact matching with md5
            
        if doi != "":
            
            doc_ids = self.get_doc_ids( doi)
            res = []
            for collection in doc_ids:
                for id_value in doc_ids[collection]:
                    res.append( { 
                        "collection":collection,
                        "id_field": "id_int", 
                        "id_type": "int",
                        "id_value":id_value
                    }   )
            if len(res)>0:  ## This is because that sometimes our DB do not contain DOIs but contain other information
                return res
        
        if title != "":
            doc_ids = self.get_doc_ids( title) 
            if sum( [ len(doc_ids[collection]) for collection in  doc_ids  ]  ) == 0:
                doc_ids_1 = self.get_doc_ids( title_head )
                doc_ids_2 = self.get_doc_ids( title_tail )
                doc_ids = self.merge_doc_ids( doc_ids_1, doc_ids_2 )
                
                
            clean_doc_ids = {}
            for collection in doc_ids:
                for id_value in doc_ids[collection]:
                    if fuzz.ratio( self.title_record.get( collection, {} ).get( id_value,"" ), title  ) >  self.fuzz_ratio_thres:
                        if first_author.strip() == "" or fuzz.ratio( self.first_author_record.get( collection, {} ).get( id_value, "" ),  first_author ) > self.fuzz_ratio_thres:
                            if collection not in clean_doc_ids:
                                clean_doc_ids[collection] = []
                            clean_doc_ids[collection].append( id_value )
            doc_ids = clean_doc_ids
                
            res = []
            for collection in doc_ids:
                for id_value in doc_ids[collection]:
                    res.append( { 
                        "collection":collection,
                        "id_field": "id_int", 
                        "id_type": "int",
                        "id_value":id_value
                    }   )
            return res    
                
        return []
        
        
    def update(self, data, tokenize = True ):
        
        with open(self.data_path,"a") as fw:
        
            for collection, id_int, md5, doi, title, first_author in tqdm(data):
                if tokenize:
                    md5 = md5.lower().strip()
                    doi = doi.lower().strip()
                    first_author = self.tokenize(first_author)
            
                    title = self.tokenize(title)
                    title_words = title.split()
                    title_head = " ".join( title_words[:self.head_tail_len] )
                    title_tail = " ".join( title_words[-self.head_tail_len:] )
                
                id_int = int(id_int)
                
                if collection not in self.inv_idx:
                    self.inv_idx[collection] = {}
                
                for key in set([ md5, doi, title, title_head, title_tail, first_author  ]):
                    if key == "":
                        continue
                    if key not in self.inv_idx[collection] :
                        self.inv_idx[collection][key] = id_int
                    else:
                        if not isinstance(self.inv_idx[collection][key], array):
                            self.inv_idx[collection][key] = array( "I", [ self.inv_idx[collection][key] ] )
                        self.inv_idx[collection][key].append( id_int )
                
                if collection not in self.title_record:
                    self.title_record[ collection ] = {}
                self.title_record[ collection ][ id_int ] = title
                
                if collection not in self.first_author_record:
                    self.first_author_record[ collection ] = {}
                self.first_author_record[ collection ][ id_int ] = self.get_abbrev_name(first_author)
                        
                fw.write( self.field_separator_regx.join( map( lambda x: self.field_separator_matcher.sub( "", str(x) ).strip(),  [ collection, id_int, md5, doi, title, title_head, title_tail, first_author] ) )+"\n" )