import sqlite3
import numpy as np
import threading
import json
import time

class SqliteClient:
    def __init__(self, db_address , check_same_thread=False):
        self.conn = sqlite3.connect(db_address, check_same_thread = check_same_thread)
        self.cur = self.conn.cursor()
        self.cur.execute( "SELECT name FROM sqlite_master WHERE type='table'" )
        try:
            self.collections = set([_[0] for _ in self.cur.fetchall()] )
        except:
            self.collections = set([])
    
    
    def get_max_rowid(self, collection ):
        if collection not in self.collections:
            return 0
        self.cur.execute('SELECT max(rowid) From %s'%( collection ))
        try:
            max_rowid = self.cur.fetchone()[0]
        except:
            max_rowid = 0
        return max_rowid

    def get_paper( self, collection, id_field, id_value  ):
        try:
            assert collection in self.collections
            sql_command = """
                        SELECT paper_id, Text FROM %s WHERE %s = %d
                     """%( collection, id_field, id_value  )
    
            self.cur.execute(sql_command)
            res = self.cur.fetchall()
            assert len(res) > 0
            res = res[0]
        except:
            return None
        return {"paper_id":res[0],"Text": res[1]}
    
    def get_papers( self, paper_id_list ):
        papers = []
        for paper_id in paper_id_list:
            try:
                paper = self.get_paper( paper_id["collection"], paper_id["id_field"], paper_id["id_value"] )
            except:
                paper = None
            papers.append( paper  )
        return papers
            
    def insert_papers( self, collection,  papers  ):
        starting_id_int = self.get_max_rowid( collection ) +1
        
        if collection not in self.collections:
            self.cur.execute( "CREATE TABLE %s( paper_id INT, Text TEXT);"%( collection ) )
            self.cur.execute( "CREATE INDEX IF NOT EXISTS paper_id ON %s (paper_id ASC);"%(collection) )
            
            self.collections.add(collection )
        values = []
        for paper in papers:
            values.append( "(%d,'%s')"%( int(paper["paper_id"]), paper["Text"].replace("'","''") ) )
        values = ",".join( values )
        self.cur.execute( "INSERT INTO %s('paper_id','Text') VALUES %s;"%(collection, values )  )
        self.conn.commit()
        
    
    
    def update_paper( self, paper_id, paper_text ):
        self.cur.execute("""UPDATE %s 
                            SET Text = '%s'
                            WHERE
                                %s = %d;
                            """ %( paper_id["collection"],
                                   paper_text.replace("'","''"),
                                   paper_id["id_field"],
                                   int(paper_id["id_value"])
                                 ) )
        self.conn.commit()
    
    def __del__(self):
        self.conn.close()
