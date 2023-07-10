import sqlite3
import numpy as np
import threading
try:
    import ujson as json
except ImportError:
    import json
import json
import time
from tqdm import tqdm

def get_data_given_projection( input_data, projection = None ):
    if projection is None:
        return input_data
    output_data = {}
    for nested_key in projection:
        if projection[nested_key] != 1:
            continue
        key_list = nested_key.split(".")
        ## get the value from input_data
        temp_output_data = {}
        value_found = False

        current_input_dict = input_data
        current_temp_output_dict = temp_output_data

        for pos in range(len(key_list)):
            key = key_list[pos]
            try:
                assert key in current_input_dict
            except:
                break
            if pos == len(key_list)-1:
                value = current_input_dict[key]
                current_temp_output_dict[key] = value
                value_found = True
            else:
                current_input_dict = current_input_dict[key]
                current_temp_output_dict[key] = {}
                current_temp_output_dict = current_temp_output_dict[key] 

        if value_found:
            current_output_dict = output_data
            current_temp_output_dict = temp_output_data
            for pos in range(len(key_list)):
                key = key_list[pos]

                if key not in current_output_dict:
                    current_output_dict[key] = current_temp_output_dict[key]
                    break
                if pos == len(key_list)-1:
                    current_output_dict[key] = current_temp_output_dict[key]
                else:
                    current_output_dict = current_output_dict[key]
                    current_temp_output_dict = current_temp_output_dict[key]
    return output_data

class SqliteClient:
    def __init__(self, db_address , check_same_thread=False):
        self.conn = sqlite3.connect(db_address, check_same_thread = check_same_thread)
        self.cur = self.conn.cursor()
        self.cur.execute( "SELECT name FROM sqlite_master WHERE type='table'" )
        try:
            self.collections = set([_[0] for _ in self.cur.fetchall()] )
        except:
            self.collections = set([])
                    
    def get_row_count( self, collection ):
        if collection not in self.collections:
            return 0
        self.cur.execute('SELECT COUNT(*) From %s'%( collection ))
        cur_result = self.cur.fetchone()
        return cur_result[0]
    
    def get_max_rowid(self, collection ):
        if collection not in self.collections:
            return 0
        self.cur.execute('SELECT max(id_int) From %s'%( collection ))
        try:
            max_rowid = self.cur.fetchone()[0]
            assert max_rowid is not None
        except:
            max_rowid = 0
        return max_rowid
        
    def get_papers( self, paper_id_list, projection = None, **kwargs ):
        ## currently, only query via id_int is possible
        
        need_content = False
        need_reference = False
        need_pdf_base64_string = False
        
        ## unless PDF is explicit specified in the projection, we do not provide the PDF_Base64_String
        if projection is None: 
            need_content = True
            need_reference = True
        else:
            for pj_key in projection:
                if "Content" in pj_key:
                    need_content = True
                if "Reference" in pj_key:
                    need_reference = True
                if "PDF_Base64_String" in pj_key:
                    need_pdf_base64_string = True
                    
        
        paper_id_dict = {}
        for pid in paper_id_list:
            try:
                collection, id_field, id_value = pid["collection"], pid["id_field"], pid["id_value"]
                id_value = int(id_value)
                assert collection in self.collections and id_field == "id_int"
                if collection not in paper_id_dict:
                    paper_id_dict[ collection ] = [ id_value ]
                else:
                    paper_id_dict[ collection ].append( id_value )
            except:
                continue
            
        paper_dict = {}
        for collection in paper_id_dict:
            paper_dict[ collection ]  = {}
            sql_command = """
                        SELECT id_int, Metadata, Parsed_Content, Reference, %s Last_update_unixtime FROM %s 
                        WHERE id_int IN (%s)
                    """%( "PDF_Base64_String," if need_pdf_base64_string else "" , collection, str(paper_id_dict[ collection ] )[1:-1].strip(",")  )
            self.cur.execute(sql_command)
            res_list = self.cur.fetchall()
            for res in res_list:
                if need_pdf_base64_string:
                    id_int, Metadata, Parsed_Content, Reference, PDF_Base64_String, Last_update_unixtime = res
                else:
                    id_int, Metadata, Parsed_Content, Reference, Last_update_unixtime = res
                
                paper_record = {}
                paper_record.update( json.loads( Metadata ) )
                paper_record.update( { "id_int": id_int , "Last_update_unixtime": Last_update_unixtime })
                
                if need_content:
                    paper_record.update( json.loads( Parsed_Content ) )
                if need_reference:
                    paper_record.update( json.loads( Reference )  )
                if need_pdf_base64_string:
                    paper_record.update( json.loads( PDF_Base64_String )  )
                    
                paper_dict[ collection ][ id_int ] = paper_record
            
        paper_list = []
        for pid in paper_id_list:
            collection, id_field, id_value = pid["collection"], pid["id_field"], pid["id_value"]
            if id_field != "id_int" or collection not in self.collections:
                paper_list.append( None )
                continue
            try:
                paper_info = paper_dict[collection][id_value]
            except:
                paper_info = None
            
            if paper_info is not None:
                paper_info =  get_data_given_projection( paper_info, projection )
            
            paper_list.append( paper_info )
        return paper_list
    
    def insert_papers( self, papers, collection ):
        if len(papers) == 0:
            return len(papers)
        
        starting_id_int = self.get_max_rowid( collection ) +1
        
        if collection not in self.collections:
            self.cur.execute( "CREATE TABLE %s(id_int INTEGER PRIMARY KEY, Metadata TEXT, Parsed_Content TEXT, Reference TEXT, PDF_Base64_String TEXT, Last_update_unixtime INT);"%( collection ) )
            self.collections.add(collection )
        
        values = []
        for paper in papers:
            metadata = {}
            exclusive_fields = set(["Content","Reference", "PDF_Base64_String", "Last_update_unixtime","id_int"])
            for field_name in paper.keys():
                if field_name not in exclusive_fields:
                    metadata[field_name] = paper[field_name]
            content = { "Content": paper["Content"]}
            reference = { "Reference": paper["Reference"]}
            PDF_base64_string = { "PDF_Base64_String": paper.get("PDF_Base64_String", None) }
                    
            values.append( "('%s','%s','%s','%s',%d)"%( json.dumps( metadata ).replace("'","''"),
                                                   json.dumps( content ).replace("'","''"),
                                                   json.dumps( reference ).replace("'","''"),
                                                   json.dumps( PDF_base64_string ).replace("'","''"),
                                                   int( time.time() )
                                                ) )
        values = ",".join( values )
        self.cur.execute( "INSERT INTO %s('Metadata','Parsed_Content','Reference','PDF_Base64_String','Last_update_unixtime') VALUES %s;"%(collection, values )  )
        self.conn.commit()
        
        return len(papers)
    
    def update_paper( self, paper_id, paper ):
        if paper_id.get("id_field","id_int") != "id_int":
            print("Warning: only id_int can be used for id_field!")
        else:
            metadata = {}
            exclusive_fields = set(["Content","Reference","PDF_Base64_String","Last_update_unixtime","id_int"])
            for field_name in paper.keys():
                if field_name not in exclusive_fields:
                    metadata[field_name] = paper[field_name]
            content = { "Content": paper["Content"]}
            reference = { "Reference": paper["Reference"]}
            PDF_base64_string = { "PDF_Base64_String": paper.get("PDF_Base64_String", None) }
            self.cur.execute("""UPDATE %s 
                            SET Metadata = '%s', 
                                Parsed_Content = '%s', 
                                Reference = '%s',
                                PDF_Base64_String = '%s',
                                Last_update_unixtime = %d  
                            WHERE
                                id_int = %d;
                            """ %( paper_id["collection"],
                                   json.dumps( metadata ).replace("'","''"),
                                   json.dumps( content ).replace("'","''"),
                                   json.dumps( reference ).replace("'","''"),
                                   json.dumps( PDF_base64_string ).replace("'","''"),
                                   int( time.time() ),
                                   paper_id["id_value"]
                                 ) )
            self.conn.commit()
    
    def __del__(self):
        self.conn.close()



