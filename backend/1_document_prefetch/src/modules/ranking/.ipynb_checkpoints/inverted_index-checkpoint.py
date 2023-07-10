import os,sys,inspect
# current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
# parent_dir = os.path.dirname(current_dir)
# sys.path.insert(0, parent_dir) 
from modules.tokenizer.tokenizer import SentenceTokenizer
import numpy as np
import re
import spacy
from nameparser import HumanName

from sqlitedict import SqliteDict
import threading
import numba
from numba import njit
from tqdm import tqdm



class QueryParser:
    def __init__( self, ):
        self.sent_tokenizer = SentenceTokenizer() 
        
        self.doi_matcher = re.compile("10.\d{4,9}/[-._;()/:A-Za-z0-9]+")
        self.not_matcher =  re.compile("<NOT>" )
        self.or_matcher =  re.compile("<OR>" )
        self.and_matcher =  re.compile("<AND>" )
        self.year_matcher = re.compile("([^\d]|^)((19[0-9][0-9]|20[0-9][0-9])\.\.(19[0-9][0-9]|20[0-9][0-9]))(?=[^\d]|$)|([^\d]|^)(19[0-9][0-9]|20[0-9][0-9])(?=[^\d]|$)")
        
        self.field_name_and_ngram_matcher = re.compile("([A-Za-z\.]+:)(.+)|(.+)")
        
        self.stopwords_set = set( self.sent_tokenizer.general_stopwords )
        self.spacy_nlp = spacy.load("en_core_web_sm")
        
        """
            Allowable field name set
        """
        self.allowable_field_names = set(map(lambda x:x.lower(),[
                        "Author:", "Author.FamilyName:", "Author.GivenName:", "Author.FullName:",
                        "Title:", "Venue:", "DOI:",
                        "Year:", "PublicationDate.Year:",
                        "AvailableField:"
                    ]) )
        
        
    def get_bigrams(self, word_list ):
        bigrams = set()
        for pos in range( len(word_list) - 1 ):
            bigram_left = word_list[pos]
            bigram_right = word_list[pos+1]
            if bigram_left not in self.stopwords_set and bigram_right not in self.stopwords_set:
                bigrams.add( bigram_left + " " + bigram_right )  # bigram A B
        return bigrams
    
    def get_unigrams(self, word_list ):
        unigrams = set()
        for w in word_list:
            if w not in self.stopwords_set:
                unigrams.add(w)
        return unigrams
    
    def normalize( self, query_element ):
        if query_element["operation"] is None:
            if len(query_element["elements"]) == 0:
                query_element["elements"] = [ "" ]
            else:
                query_element["elements"] = [ query_element["elements"][0].strip() ]
        else:
            query_element["elements"] = [ element for element in query_element["elements"] if not ( element["operation"] is None and element["elements"][0] == "" )  ]
            if len(query_element["elements"]) == 0:
                query_element["operation"] = None
                query_element["elements"] = [""]
                
    def parse(self, keys, skip_stages = set() ):
        
        # priority of operations in parsing queries:  NOT > OR > AND
        # split the query string from the lowest priority to the highest
        
        if "AND-parse" not in skip_stages:
            skip_stages = skip_stages | set(["AND-parse"])
            elements = [ key.strip() for key in self.and_matcher.split(keys)]
            if len(elements) > 1:
                query_element =  {
                    "operation":"AND",
                    "elements":elements
                }
                for pos in range(len(query_element["elements"] )):
                    query_element["elements"][pos] = self.parse( query_element["elements"][pos], skip_stages )
                self.normalize(query_element)
                return query_element
            
        if "OR-parse" not in skip_stages:
            skip_stages = skip_stages | set(["OR-parse"])
            elements = [ key.strip() for key in self.or_matcher.split(keys)]
            if len(elements) > 1:
                query_element = {
                    "operation":"OR",
                    "elements":elements
                }
                for pos in range(len(query_element["elements"])):
                    query_element["elements"][pos] = self.parse( query_element["elements"][pos], skip_stages )
                self.normalize(query_element)
                return query_element
            
        if "NOT-parse" not in skip_stages:
            skip_stages = skip_stages | set(["NOT-parse"])
            elements = [ key.strip() for key in self.not_matcher.split(keys.strip())]
            if len(elements) > 1:
                query_element = {
                    "operation":"NOT",
                    "elements":elements[1:2]
                }
                for pos in range(len(query_element["elements"])):
                    query_element["elements"][pos] = self.parse( query_element["elements"][pos], skip_stages )
                self.normalize(query_element)
                return query_element
            
        keys = keys.strip()
        try:
            found_field_name_and_ngram = self.field_name_and_ngram_matcher.findall( keys )[0]
            field_name = found_field_name_and_ngram[0]
            ngram = found_field_name_and_ngram[1] + found_field_name_and_ngram[2]
        except:
            field_name = ""
            ngram = ""
            
        field_name = field_name.strip().lower()
        if field_name not in self.allowable_field_names:
            field_name = ""
                    
        """
            The ngram connector is space " ", so we can just split the ngram using ngram.split()
        """
        word_list = ngram.split()
        
        if "Name-parse" not in skip_stages:
            skip_stages = skip_stages | set(["Name-parse"])
            ## check name
            name_word_list = list(  map( lambda x:x.rstrip(","), word_list ) )
            if field_name == "" or field_name.lower() == "author:":
                # check name
                ## check if the uni/bigram is a human name using spacy NER
                potential_name = " ".join( name_word_list )                        
                parsed_potential_name = self.spacy_nlp(potential_name)
                start_pos = 0
                end_pos = 0
                for ent in parsed_potential_name.ents:
                    if ent.label_ == "PERSON":
                        start_pos = ent.start_char
                        end_pos = ent.end_char
                        break
                ## NER found a person name
                if (end_pos - start_pos)/(len(potential_name)+1e-9) > 0.9:
                    human_name_scenario = HumanName( potential_name[ start_pos:end_pos ] )
                    first_name = human_name_scenario.first
                    last_name = human_name_scenario.last
                    elements = []
                    
                    if first_name != "" and last_name != "":
                        elements.append( {
                            "operation":None,
                            "elements":[("Author.FullName:"+first_name+" "+last_name ).lower()] }
                        )
                    elif first_name != "":
                        elements.append( {
                            "operation":None,
                            "elements":[("Author.GivenName:"+first_name).lower()] }
                        )
                    elif last_name != "":
                        elements.append( {
                            "operation":None,
                            "elements":[("Author.FamilyName:"+last_name).lower()] }
                        )
                    query_element_scenario_1 = {
                        "operation": "AND",
                        "elements": elements
                    }
                    ## switch the order between first name and last name, as we may not be sure what is the exact order typed by the users
                    elements = []
                    if first_name != "" and last_name != "":
                        elements.append( {
                            "operation":None,
                            "elements":[("Author.FullName:"+last_name+" "+first_name ).lower()] }
                        )
                    elif first_name != "":
                        elements.append( {
                            "operation":None,
                            "elements":[("Author.FamilyName:"+first_name).lower()] }
                        )
                    elif last_name != "":
                        elements.append( {
                            "operation":None,
                            "elements":[("Author.GivenName:"+last_name).lower()] }
                        )
                    query_element_scenario_2 = {
                        "operation": "AND",
                        "elements": elements
                    }
                    ## scenario 3: If using the two scenarios above we did not find any paper, it means the recognized name may not be a real author name. In this case, we just treat the first name and the last name as normal keywords; Note: If we find a good match using the parsed author name based on scenario 1 & 2, then scenario 3 is ignored.
                    query_element_scenario_3 = {
                        "operation": "AND",
                        "elements": [   
                            {"operation":None, "elements":[ first_name.lower() ]  },
                            {"operation":None, "elements":[ last_name.lower() ]  },
                        ]
                    }
                    self.normalize(query_element_scenario_3)
                    
                    query_element = {
                        "operation": "OR",
                        "optional_after_pos":1,
                        "elements": [ query_element_scenario_1, query_element_scenario_2, query_element_scenario_3 ]
                    }
                    self.normalize(query_element)
                    return query_element
                
                ## deactivate the "Author" field name, becasue it is not correctly parsed if the function does not end here yet.
                field_name = ""
                        
            elif field_name.lower() == "Author.FamilyName:".lower() or \
                                        field_name.lower() == "Author.GivenName:".lower() or \
                                        field_name.lower() == "Author.FullName:".lower():                            
                query_element = {
                    "operation":"OR",
                    "elements":[  
                       { "operation":None, "elements":[ field_name + " ".join( name_word_list ).strip().lower() ]  },
                       { "operation":None, "elements":[ field_name + " ".join( reversed(name_word_list) ).strip().lower() ]  },
                    ]
                }
                self.normalize(query_element)
                return query_element
            
        
        
        if "DOI-parse" not in skip_stages:
            skip_stages = skip_stages | set(["DOI-parse"])
            ## check doi
            if field_name == "":
                found_dois = self.doi_matcher.findall( " ".join(word_list) )
                if len(found_dois) > 0:
                    found_doi = found_dois[0]
                    query_element = {
                        "operation":None,
                        "elements":[ ("DOI:"+found_doi).lower() ]
                    }
                    self.normalize(query_element)
                    return query_element
                
                field_name = ""
                
            elif field_name.lower() == "DOI:".lower():
                doi = " ".join(word_list).strip().lower()
                query_element = {
                        "operation": None,
                        "elements": [ (field_name + doi).lower() if doi != "" else ""  ]
                }
                self.normalize(query_element)
                return query_element
        
        if "Year-parse" not in skip_stages:
            skip_stages = skip_stages | set(["Year-parse"])
            ## check year
            if field_name == "" or "year" in field_name.lower():
                found_years = self.year_matcher.findall( " ".join( word_list ) )
                if len(found_years) > 0:
                    found_year = found_years[0]
                    if found_year[1]!="":
                        start_year, end_year = found_year[1].split("..")
                        year_range = map(str,np.arange( int(start_year), int(end_year)+1 ).tolist())
                        query_element = {
                            "operation":"OR",
                            "elements":[ { "operation":None, "elements":[ ("PublicationDate.Year:"+year).lower() ] }  for year in year_range ]
                        }
                        self.normalize(query_element)
                        return query_element
                    elif found_year[-1] != "":
                        query_element = {
                            "operation": None,
                            "elements":[ ("PublicationDate.Year:"+found_year[-1]).lower() ]
                        }
                        self.normalize(query_element)
                        return query_element
                    
                field_name = ""
        
        if "AvailableField-parse" not in skip_stages:
            skip_stages = skip_stages | set( ["AvailableField-parse"] )
            if field_name.lower() == "AvailableField:".lower():
                avail_field = " ".join(word_list).strip().lower()
                query_element = {
                        "operation": None,
                        "elements": [ (field_name + avail_field).lower() if avail_field != "" else "" ]
                }
                self.normalize(query_element)
                return query_element
                    
                
        ## Check query keyword from other potential fields: Title, Venue    
        tokenized_words_list = self.sent_tokenizer.tokenize( " ".join(word_list) ).strip().split()
        tokenized_uni_bi_gram_list = list(self.get_unigrams(tokenized_words_list)) + list(self.get_bigrams( tokenized_words_list ))
        
        ## newly added 15-08-2022: to remove unnecessary unigrams that are already included in bigrams
        non_duplicate_tokenized_uni_bi_gram_list = []
        for kwd in sorted(tokenized_uni_bi_gram_list, key = lambda x:-len(x.split())):
            if len(non_duplicate_tokenized_uni_bi_gram_list) == 0:
                non_duplicate_tokenized_uni_bi_gram_list.append(kwd)
            elif not any([ kwd in item and len(set(kwd.split()) - set(item.split()) ) == 0  for item in non_duplicate_tokenized_uni_bi_gram_list ]):
                non_duplicate_tokenized_uni_bi_gram_list.append(kwd)
        tokenized_uni_bi_gram_list = non_duplicate_tokenized_uni_bi_gram_list
        
        query_element ={
            "operation":"AND",
            "elements":[ {
                "operation": None,
                "elements":[ (field_name+tokenized_uni_bi_gram).lower() ]
                } for tokenized_uni_bi_gram in tokenized_uni_bi_gram_list
            ]
        }
        self.normalize(query_element)
        return query_element
                        
                

@njit
def fast_assign( a, indices, v):
    a[indices] = v

class OnDiskInvertedIndex:
    def __init__(self, database_folder ):
        self.database_folder = os.path.abspath(database_folder)
        self.query_parser = QueryParser()
        self.initiate()
        
    def initiate(self,):
        try:
            self.close()
        except:
            pass

        self.shards = os.listdir(self.database_folder)
        print("all shards:", self.shards)
        self.on_disk_dicts = { shard: SqliteDict( "%s/%s"%(self.database_folder, shard ), journal_mode = "OFF" )
                                 for shard in self.shards 
                             }
        self.packed_doc_ids = { shard: self.on_disk_dicts[shard]["INFO:PACKED_DOC_IDS"]  
                                 for shard in self.shards   
                              } 

        for shard in self.shards:
            self.collection = self.on_disk_dicts[shard]["INFO:COLLECTION"]
            break
        
        ### get all available ids when no keyword given and the total number of document in this inverted index
        filtered_results = self.get( "" )
        num_matched_documents = 0
        for c in filtered_results:
            num_matched_documents += int(np.sum(filtered_results[c] ))
        
        self.filtered_results = filtered_results
        self.num_matched_documents = num_matched_documents
        
        
    def pause_shards( self, shards ):
        for shard in shards:
            if shard in self.shards:
                self.shards = list( set(self.shards) - set([shard])  )

    def zero_pad(self, arr_list ):
        max_len = max([ len(arr) for arr in arr_list  ])
        padded_arr_list = []
        for arr in arr_list:
            padded_arr_list.append( np.concatenate( [arr, np.zeros( max_len -len(arr), dtype = np.uint8 )] ) )
        return padded_arr_list
                
    def bitwise_or(self, arr_list, optional_after_pos = None ):
        if len(arr_list) == 0:
            return np.array([], dtype = np.uint8)
        
        if optional_after_pos is None:
            optional_after_pos = len( arr_list ) - 1
        optional_after_pos = min( max( optional_after_pos, 0 ), len( arr_list ) - 1 )
        
        arr_list = self.zero_pad(arr_list)
        res_arr = None
        for arr in arr_list[0: optional_after_pos+1]:
            if res_arr is None:
                res_arr = arr
            else:
                res_arr = np.bitwise_or(res_arr,arr)
        ## if there are some match so far, then just skip all the arr after the position: optional_after_pos
        if res_arr.sum() > 0:
            return res_arr
        
        for arr in arr_list[optional_after_pos+1 :]:
            res_arr = np.bitwise_or(res_arr,arr)
        return res_arr
            
    def bitwise_and(self, arr_list ):
        if len(arr_list) == 0:
            return np.array([], dtype = np.uint8)
        if len(arr_list) == 1:
            return arr_list[0]
        arr_list = self.zero_pad(arr_list)
        res_arr = arr_list[0]
        for arr in arr_list[1:]:
            res_arr = np.bitwise_and(res_arr,arr)
        return res_arr
    
    def get_from_shard(self, shard, query, results = None ):
        max_len = len( self.packed_doc_ids[shard] ) * 8
        if query["operation"] is None:
            query_text = query["elements"][0]
            if query_text == "":
                bool_arr = np.ones( max_len, dtype = np.uint8 )
            else:
                bool_arr = np.zeros( max_len, dtype = np.uint8 )
                ids = self.on_disk_dicts[shard].get( query_text, np.array([]) )
                if len(ids) > 0:
                    fast_assign( bool_arr,  ids, 1 )
            bool_arr = np.packbits( bool_arr, bitorder='little' )
        else:
            arr_list = [ self.get_from_shard(shard, element ) for element in query["elements"]  ]
            if query["operation"] == "AND":
                bool_arr = self.bitwise_and( arr_list )
            elif query["operation"] == "OR":
                bool_arr = self.bitwise_or( arr_list, query.get("optional_after_pos", None) )
            elif query["operation"] == "NOT":
                bool_arr = np.bitwise_not( arr_list[0] )
            else:
                print("Warning: wrong operation type")
                bool_arr = np.packbits(np.zeros( max_len, dtype = np.uint8 ), bitorder='little' )
        
        if results is not None:
            results[shard] = bool_arr
        
        return bool_arr
    
    def get_bool_array( self, packed_ids):
        unpacked_ids = np.unpackbits( packed_ids, bitorder = "little" ) == 1
        return unpacked_ids
    
    def get( self, key_string, bool_array = True):
        query = self.query_parser.parse(key_string)
        results = {}
        threads = []
        for shard in self.shards:
            t =  threading.Thread(target=self.get_from_shard, args=(shard, query, results ))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        
        combined_unpacked_bool_arr = self.get_bool_array( self.bitwise_or( [ results[shard] for shard in results] ))
        
        if bool_array:
            return { self.collection: combined_unpacked_bool_arr}
        else:
            filtered_indices = np.argwhere( combined_unpacked_bool_arr )[:,0]
            return { self.collection: filtered_indices }
    
    def close(self):
        for shard in self.on_disk_dicts:
            self.on_disk_dicts[shard].close()
    
    def __del__(self):
        self.close()