import os,sys
from modules.paper_database.database_managers import SqliteClient
import json
from tqdm import tqdm
import dateparser
from nameparser import HumanName
import time
import threading 

import array
import numpy as np
from more_itertools import unique_everseen

from modules.tokenizer.tokenizer import SentenceTokenizer
from sqlitedict import SqliteDict
import argparse


def add_ngrams( inv_idx, ngram_set, doc_id ):
    #ngram_set is a set of ngrams
    for ngram in ngram_set:
        if ngram not in inv_idx:
            inv_idx[ngram] = array.array("I", [doc_id] )
        else:
            inv_idx[ngram].append( doc_id )

"""
save inv_idx (in memory) to inv_idx_on_disk
The basic logic is to first create an inv_idx in memory, processing a few documents, 
adding unigrams and bigrams to inv_idx, then dump the inv_idx to inv_idx_on_disk.
"""
def dump_inv_idx( inv_idx, inv_idx_on_disk, overwrite = True, key_list = None ):
    if key_list is None:
        key_list = inv_idx.keys()
    for word in tqdm(key_list):
        if overwrite or word not in inv_idx_on_disk:
            doc_id_list = np.unique(inv_idx[word])
            # doc_id_list.sort()  ## this is time consuming! and not really necessary..
            inv_idx_on_disk[word] = doc_id_list
        else:
            doc_id_list = list(set(inv_idx_on_disk[word].tolist()+inv_idx[word].tolist()))
            doc_id_list = np.array( doc_id_list )
            doc_id_list.sort()
            inv_idx_on_disk[word] = doc_id_list
            

def get_unigrams( word_list, stopwords ):
    unigrams = set()
    for w in word_list:
        if w not in stopwords:
            unigrams.add(w)
    return unigrams

def get_bigrams( word_list, stopwords ):
    bigrams = set()
    for pos in range( len(word_list) - 1 ):
        bigram_left = word_list[pos]
        bigram_right = word_list[pos+1]
        if bigram_left not in stopwords and bigram_right not in stopwords:
            bigrams.add( bigram_left + " " + bigram_right )  # bigram A B
    return bigrams

def get_sentence_list_from_parsed( parsed ):
    sentence_list = []
    for section in parsed:
        sentence_list.append(str(section.get( "section_title", "" )))
        for para in section.get("section_text",[]):
            for sen in para.get("paragraph_text", []):
                sentence_list.append( str(sen.get("sentence_text","")) )
    return sentence_list

def parse_document( doc_data, sent_tokenizer, stopwords ):
    ngram_set = set()
    
    ## Author
    for author in doc_data.get("Author", []):
        
        family_name = str(author.get("FamilyName", "")).lower().strip()
        given_name =  str(author.get("GivenName", "")).lower().strip()
        
        ## add the formatted author names
        if family_name != "":
            ngram_set.add( "Author.FamilyName:" + family_name )
        if given_name != "":
            ngram_set.add( "Author.GivenName:" + given_name )
        if family_name != "" and given_name != "":
            ngram_set.add( "Author.FullName:" + given_name + " " + family_name)
        
        ## add the unformatted author names
        name = sent_tokenizer.tokenize(family_name + " " + given_name).strip()
        if name != "":
            word_list = name.split()
            ## get unigrams
            ngram_set.update( get_unigrams( word_list, stopwords ) )
            ## get bigrams
            ngram_set.update( get_bigrams( word_list, stopwords ) )
            ## get reversed bigrams
            ngram_set.update( get_bigrams( list(reversed(word_list)), stopwords ) )
    if len(doc_data.get("Author", [])) > 0:
        ngram_set.add( "AvailableField:Author" )
        
    ## Title
    title = sent_tokenizer.tokenize( str(doc_data.get("Title", ""))).strip()
    if title != "":
        word_list = title.split()
        ## get unigrams
        unigrams = get_unigrams( word_list, stopwords )
        ngram_set.update( unigrams )
        ngram_set.update( [ "Title:"+word for word in unigrams ] )
        ## get bigrams
        bigrams = get_bigrams( word_list, stopwords )
        ngram_set.update( bigrams )
        ngram_set.update( [ "Title:"+word for word in bigrams ] )
        
        ngram_set.add( "AvailableField:Title" )
    
    ## Venue    
    venue = sent_tokenizer.tokenize( str(doc_data.get("Venue", ""))).strip()
    if venue != "":
        word_list = venue.split()
        ## get unigrams
        unigrams = get_unigrams( word_list, stopwords )
        ngram_set.update( unigrams )
        ngram_set.update( ["Venue:"+word for word in unigrams ] )
        ## get bigrams
        bigrams = get_bigrams( word_list, stopwords )
        ngram_set.update( bigrams )
        ngram_set.update( ["Venue:"+word for word in bigrams] )
        
        ngram_set.add( "AvailableField:Venue" )
    
    ## DOI
    doi = str(doc_data.get("DOI","")).lower().strip()
    if doi != "":
        ngram_set.add(doi)
        ngram_set.add("DOI:"+doi)
        
        ngram_set.add( "AvailableField:DOI" )

    ## Year
    year = str(doc_data.get("PublicationDate",{}).get("Year", "")).lower().strip()
    if year != "":
        ngram_set.add(year)
        ngram_set.add("PublicationDate.Year:"+year)
        
        ngram_set.add( "AvailableField:PublicationDate.Year" )
        
    ## Abstract
    abstract_sen_list = get_sentence_list_from_parsed(doc_data.get( "Content", {} ).get( "Abstract_Parsed", [] ))
    if " ".join(abstract_sen_list).strip() != "":
        ngram_set.add( "AvailableField:Content.Abstract_Parsed" )
        
    ## Fullbody
    fullbody_sen_list = get_sentence_list_from_parsed(doc_data.get( "Content", {} ).get( "Fullbody_Parsed", [] ))
    if " ".join(fullbody_sen_list).strip() != "":
        ngram_set.add( "AvailableField:Content.Fullbody_Parsed" )
    
    sen_list = abstract_sen_list + fullbody_sen_list
    for sen in sen_list:
        sen_tokenized = sent_tokenizer.tokenize( str(sen) ).strip()
        if sen_tokenized != "":
            word_list = sen_tokenized.split()
            ## get unigrams
            ngram_set.update( get_unigrams( word_list, stopwords ) )
            ## get bigrams
            ngram_set.update( get_bigrams( word_list, stopwords ) )
    
    
    ## Others, not mandatory, varies on different collections
    ## To be added here ...
    
    ## lower all ngrams
    ngram_set = set( map( lambda x:x.lower(), ngram_set ) )
    
    return ngram_set

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-db_address")
    parser.add_argument("-collection")
    parser.add_argument("-inv_idx_file_name")
    parser.add_argument("-inv_idx_file_name_suffix", default = "")
    parser.add_argument("-commit_per_num_of_keys", type = int, default = 10000000)
    parser.add_argument("-overwrite", type = int, default = 1)
    parser.add_argument("-start", type = int, default = 0)
    parser.add_argument("-size", type = int, default = 0)
    
    args = parser.parse_args()

    args.inv_idx_file_name += args.inv_idx_file_name_suffix
    inv_idx_folder = os.path.dirname( args.inv_idx_file_name )
    if not os.path.exists( inv_idx_folder ):
        os.makedirs( inv_idx_folder )
    
    sent_tokenizer = SentenceTokenizer()
    stopwords = set( sent_tokenizer.general_stopwords )
    sqlite_client = SqliteClient(db_address= args.db_address )

    all_doc_ids = set()

    print("Computing inverted index in ram...")
    
    max_rowid = sqlite_client.get_max_rowid( args.collection )
    if args.size == 0:
        args.size = max_rowid 
    end = min( args.start + args.size, max_rowid)
    
    inv_idx_in_ram = {}        
    for count in tqdm(range( args.start, end )):
        
        doc_id = count + 1
        paper_info = sqlite_client.get_papers( [{"collection":args.collection,"id_field":"id_int", "id_value":doc_id }] )[0]
        
        if paper_info is None or not paper_info.get("RequireIndexing", True):
            continue
        
        ngram_set = parse_document( paper_info, sent_tokenizer, stopwords )
        add_ngrams( inv_idx_in_ram, ngram_set, doc_id )

        all_doc_ids.add(doc_id)

    key_list = list( inv_idx_in_ram.keys() )
    total_num_keys = len(key_list)
    print("Total number of keys:",total_num_keys )
    
    
    if total_num_keys > 0:

        print("Dumping inverted index on disk ...")
        inv_idx_on_disk = SqliteDict(args.inv_idx_file_name, journal_mode = "OFF")

        all_doc_ids = np.array(list( all_doc_ids ))
    
        bool_arr = np.zeros( np.max(all_doc_ids) +1, dtype = np.uint8 )
        bool_arr[ all_doc_ids ] = 1
    
        packed_doc_ids = np.packbits( bool_arr,  bitorder = "little")

        for start_pos in range( 0, total_num_keys, args.commit_per_num_of_keys ):
            dump_inv_idx( inv_idx_in_ram, inv_idx_on_disk, args.overwrite , key_list[  start_pos : start_pos+args.commit_per_num_of_keys ]  )
            inv_idx_on_disk.commit()
            print("Number of stored keys:", min( start_pos+args.commit_per_num_of_keys, total_num_keys  ) )


        ## Add some INFO:XXX keys at last to make sure that they are not overwritten!
        inv_idx_on_disk["INFO:PACKED_DOC_IDS"] = packed_doc_ids
        inv_idx_on_disk["INFO:COLLECTION"] = args.collection
        inv_idx_on_disk.commit()
        
            
        inv_idx_in_ram.clear()
        inv_idx_in_ram = {}
        inv_idx_on_disk.close()
        print("Processed documents:", end-args.start )
        print("Inverted Index Computation Complete!")