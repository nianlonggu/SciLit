import json
import os
from tqdm import tqdm
import pmc_parser.pubmed_oa_parser as pp
import re
from lxml import etree

import argparse


class PMCParser:
    def __init__(self, ):
        
        self.xref_matcher = re.compile( "<xref.*?</xref>" )
        self.xref_placeholder = "<xref>PLACEHOLDER</xref>"
        
        self.cit_mask_matcher = re.compile( "(?<=\[CITSTART\])(.*?)(\[CITEND\]\[IDSTART\])(.*?)(?=\[IDEND\])" ) 
        self.cit_splitter = re.compile( "\[CITSTART\].*?\[CITEND\]\[IDSTART\].*?\[IDEND\]" ) 
    
        
    def parse_reference( self, path ):
        
        bib_entries = {}
        
        ref_list = pp.parse_pubmed_references(path)
        for ref in ref_list:
            try:
                ref_id = ref["ref_id"]
            except:
                continue
            
            title = str(ref.get("article_title",""))
            authors = []
            for author_text in ref.get("name","").split("; "):
                if author_text.strip() == "":
                    continue
                splited_names = author_text.split()
                if len(splited_names) < 2:
                    splited_names += ["",""]
                    splited_names = splited_names[:2]
                first_name = splited_names[0]
                last_name = splited_names[-1]
                middle_name = splited_names[1:-1]
                authors.append( 
                    { "first": str(first_name),
                      "middle": str(middle_name),
                      "last": str(last_name),
                      "suffix": ""
                    })
            try:
                year = int( ref["year"] )
            except:
                year = ""
            
            venue = str( ref.get("journal","") )
            link = None
            
            bib_entries[ref_id] = {
                "title":title,
                "authors":authors,
                "year":year,
                "venue":venue,
                "link":link
            }        
        return bib_entries
            
    def parse_metadata(self, path):
        raw_metadata = pp.parse_pubmed_xml(path)
        
        paper_id = str(raw_metadata.get("pmc",""))
        title = str( raw_metadata.get("full_title","") )
        authors = []
        for author in raw_metadata.get("author_list",[]):
            if len(author) < 3:
                author += ["","",""]
                author = author[:3]
            last_name, first_name, _ = author
            authors.append( 
                {"first": first_name, "middle": [], "last": last_name, "suffix": ""}
            )
        abstract = str( raw_metadata.get("abstract","") )
        
        try:
            year = int( raw_metadata["publication_year"] )
        except:
            year = ""

        pmc_id = str( raw_metadata.get("pmc","") )
        pubmed_id = str( raw_metadata.get("pmid","") )
        doi = str(raw_metadata.get("doi",""))
        
        venue = str( raw_metadata.get("journal","") )
        journal = str( raw_metadata.get("journal","") )
        
        has_pdf_body_text = True
        mag_id = ""
        mag_field_of_study = []
        outbound_citations = []
        inbound_citations = []
        has_outbound_citations = False
        has_inbound_citations = False
        has_pdf_parse = True
        
        return {
            "paper_id":paper_id,
            "title":title,
            "authors":authors,
            "abstract":abstract,
            "year":year,
            "arxiv_id":None,
            "acl_id":None,
            "pmc_id":pmc_id,
            "pubmed_id":pubmed_id,
            "doi":doi,
            "venue":venue,
            "journal":journal,
            "has_pdf_body_text":True,
            "mag_id":"",
            "mag_field_of_study":[],
            "outbound_citations":[],
            "inbound_citations":[],
            "has_outbound_citations":False,
            "has_inbound_citations":False,
            "has_pdf_parse":True,
            "has_pdf_parsed_abstract":True,
            "has_pdf_parsed_body_text":True,
            "has_pdf_parsed_bib_entries":True,
            "has_pdf_parsed_ref_entries":False,
            "s2_url":"",

        }
    
    def update_xrefs(self, all_xrefs ):
        updated_xrefs = []
        for xref in all_xrefs:
            if "bibr" not in xref:
                updated_xrefs.append( xref )
            else:
                xref_tree = etree.fromstring(xref)
                ref_type = xref_tree.attrib.get("ref-type", "bibr")
                ref_id = xref_tree.attrib.get("rid", "")
                ref_text = xref_tree.text
            
                new_ref_text = "[CITSTART]%s[CITEND][IDSTART]%s[IDEND]"%( ref_text, ref_id )
                updated_xrefs.append(  '''<xref ref-type="bibr" rid="%s">%s</xref>'''%( ref_id,  new_ref_text ) )
    
        return updated_xrefs
    
    def parse_paragraph( self, path ):
        tree = pp.read_xml(path)
        
        paragraphs = tree.xpath("//body//p")
        
        parsed_paras = []
        for paragraph in paragraphs:
            
            section = paragraph.find("../title")
            if section is not None:
                section = pp.stringify_children(section).strip()
            else:
                section = ""
            
            try:
                para_xml_text = etree.tostring(paragraph).decode("utf-8")
            except:
                continue
            
            para_xml_text = para_xml_text.replace("<sup>"," ").replace("</sup>","")
                

            all_xrefs = self.xref_matcher.findall( para_xml_text )
            para_xml_text = self.xref_matcher.sub( self.xref_placeholder, para_xml_text )
            updated_xrefs = self.update_xrefs( all_xrefs )
            masked_para_xml_text = self.xref_matcher.sub( lambda m: updated_xrefs.pop(0) , para_xml_text )

            
            para_text = pp.stringify_children( etree.fromstring(masked_para_xml_text) )
            
            cit_info_list = self.cit_mask_matcher.findall( para_text )
            splitted_sentences = self.cit_splitter.split( para_text )
            
            text = ""
            cite_spans = []
            
            for count, sen in enumerate(splitted_sentences):
                text += sen
                if count >= len(cit_info_list):
                    continue
                
                ref_text, _, ref_id = cit_info_list[ count ]
                cit_start = len(text)
                cit_end = len(text) + len( ref_text )
                cite_spans.append(
                    {
                        "start":cit_start,
                        "end":cit_end,
                        "text":str(ref_text),
                        "ref_id":str(ref_id)
                    }
                )    
                text += ref_text
                
            parsed_paras.append(
                {
                    "section":str(section),
                    "text":str(text),
                    "cite_spans":cite_spans,
                    "ref_spans":[]
                }
            )
                    
        return parsed_paras
    
    def parse_all(self, path ):
        metadata = self.parse_metadata(path)
        abstract = metadata["abstract"]
        paper_id = metadata["paper_id"]
        
        try:
            fullbody_paragraphs = self.parse_paragraph(path)
        except:
            fullbody_paragraphs = []
        try:
            references = self.parse_reference(path)
        except:
            references = {}
        
        pdf_parse = {
            "paper_id":paper_id,
            "_pdf_hash":"",
            "abstract":[ {
                "section":"Abstract",
                "text":abstract,
                "cite_spans": [],
                "ref_spans": []
            } ],
            "body_text":fullbody_paragraphs,
            "bib_entries":references,
            "ref_entries":{}
        }
        
        metadata["pdf_parse"] = pdf_parse
        return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-xml_root_folder" )
    parser.add_argument("-raw_jsonl_database_save_path")
    parser.add_argument("-save_path_suffix", default = "" )
    parser.add_argument("-start", type = int, default = 0 )
    parser.add_argument("-size", type =int, default = 0 )
    
    args = parser.parse_args()
    
    args.raw_jsonl_database_save_path += args.save_path_suffix
    
    save_folder = os.path.dirname( args.raw_jsonl_database_save_path )
    if not os.path.exists( save_folder ):
        os.makedirs( save_folder )

    pmc_parser = PMCParser()
        
    path_xml = pp.list_xml_path( args.xml_root_folder )
    path_xml.sort()
    
    if args.size == 0:
        args.size = len(path_xml) 
    
    with open(args.raw_jsonl_database_save_path, "w") as fw:
        for path in tqdm( path_xml[ args.start:args.start + args.size ] ):
            try:
                parsed_data = pmc_parser.parse_all( path )
            except:
                print("Warning: Parsing failed! Skip")
                continue
            fw.write( json.dumps( parsed_data ) + "\n" )