import re
import time
import numpy as np
from jsonschema import validate
from nltk.tokenize import sent_tokenize
import json
class DocumentNormalizer:
    def __init__(self, json_schema_path ):
        self.json_schema = json.load(open(json_schema_path,"r"))
        self.cit_marker_matcher = re.compile("(^[^A-Za-z\d]*)([0-9]+)(?=[^A-Za-z\d]*$)")
        self.sentence_boundary_matcher = re.compile("\.\s")
    
    def normalize( self, paper, requires_validation = True ):
        ##### Author #####
        parsed_authors = self.parse_author( paper )
        ##### Title #####
        parsed_title = self.parse_title( paper )
        ##### Venue #####
        parsed_venue = self.parse_venue( paper )
        ##### DOI #####
        parsed_doi = self.parse_doi(paper)
        ##### URL #####
        parsed_url = self.parse_url(paper)
        ##### PublicationDate #####
        parsed_pub_date = self.parse_pub_date(paper)
        ##### Reference #####
        parsed_reference, bib_entry_key_to_row_id_mapper = self.parse_reference(paper)
        
        ##### Content #####
        parsed_content = self.parse_content(paper, bib_entry_key_to_row_id_mapper)
        ##### Abstract (The abstract text stored in the metadata) #####
        abstract_text = (" ".join(self.get_sentence_list_from_parsed_sections( parsed_content["Abstract_Parsed"] ))).strip()
        
        ##### Last_update_unixtime ######
        Last_update_unixtime = int(time.time())
        ##### Others #####
        Abstract_in_metadata = abstract_text != ""
        isDuplicated = False
        
        normalized_paper = {
            "Author":parsed_authors,
            "Title":parsed_title,
            "Abstract":abstract_text,
            "Venue":parsed_venue,
            "DOI":parsed_doi,
            "URL":parsed_url,
            "PublicationDate":parsed_pub_date,
            "Content":parsed_content,
            "Reference":parsed_reference,
            "Last_update_unixtime":Last_update_unixtime,
            "Abstract_in_metadata":Abstract_in_metadata,
            "isDuplicated":isDuplicated
        }
        
        ##### Additional IDs, this is only added for S2ORC dataset #####
        additional_ids = self.parse_additional_ids(paper)
        normalized_paper.update( additional_ids )
        
        if requires_validation:
            try:
                validate(instance=normalized_paper, schema=self.json_schema)
            except:
                return None
        return normalized_paper
    
    def get_sentence_list_from_parsed_sections(self, parsed_sections ):
        sentence_list = []
        for section in parsed_sections:
            sentence_list.append(str(section.get( "section_title", "" )))
            for para in section.get("section_text",[]):
                for sen in para.get("paragraph_text", []):
                    sentence_list.append( str(sen.get("sentence_text","")) )
        return sentence_list
    
    
    def parse_author(self, paper ):
        try:
            parsed_authors = []
            authors = paper.get("authors", [] )
            for author in authors:
                parsed_authors.append(
                    {
                        "GivenName":str( author.get( "first", "" ).replace("None","") ),
                        "FamilyName":str( author.get( "last", "" ).replace("None","") )
                    }
                )
        except:
            parsed_authors = []
        return parsed_authors
    
    def parse_title(self, paper ):
        try:
            parsed_title = str(paper.get("title", "")).replace("None","").lstrip("[").rstrip("]")
        except:
            parsed_title = ""
        return parsed_title
    
    def parse_venue(self, paper):
        try:
            parsed_venue = str(paper.get("venue", "")).replace("None","")
        except:
            parsed_venue = ""
        
        if parsed_venue.strip() == "":
            try:
                parsed_venue = str(paper.get("journal","")).replace("None","")
            except:
                parsed_venue = ""
        return parsed_venue
    
    def parse_doi(self, paper):
        try:
            parsed_doi = str( paper.get("doi","") ).replace("None","")
        except:
            parsed_doi = ""
        return parsed_doi
    
    def parse_url(self, paper):
        try:
            parsed_doi = str(paper.get("doi","")).strip().replace("%", "%25").replace('"', "%22").replace("#", "%23").replace(" ", "%20").replace("?", "%3F").replace("None","")
            if parsed_doi.strip() != "":
                parsed_url = "https://doi.org/" + parsed_doi
            else:
                parsed_url = str(paper.get("s2_url", ""))
        except:
            parsed_url = ""
        return parsed_url
        
    
    def parse_pub_date( self, paper ):
        try:
            year = str(int(paper.get("year", ""))).replace("None","")
        except:
            year = ""
        return {
            "Year":year
        }

    def parse_para( self, para, bib_entry_key_to_row_id_mapper ):
        paragraph_text = [{ "sentence_id":str(sen_id), "sentence_text": str(sen), "cite_spans":[] }  
                          for sen_id, sen in  enumerate(self.sent_tok( str(para.get("text",""))) )]
        para_cite_spans = para.get( "cite_spans", [] )
        for cite_span in para_cite_spans:
            start, end = cite_span["start"], cite_span["end"]
            for sen in paragraph_text:
                if start < len( sen["sentence_text"] ):
                    end = min( end, len( sen["sentence_text"] ) )
                    sen["cite_spans"].append(
                        {
                            "start":start,
                            "end":end,
                            "text":sen["sentence_text"][start:end],
                            "ref_id":cite_span["ref_id"]
                        }
                    )
                    break
                else:
                    start -= len( sen["sentence_text"] )
                    end -= len( sen["sentence_text"] )
        cleaned_paragraph_text = []
        for sen in paragraph_text:
            sentence_text = sen["sentence_text"]
            cite_spans = sen["cite_spans"]
            
            sentence_text = sentence_text.rstrip()
            
            cite_spans.sort( key= lambda x:x["start"] )
            
            cleaned_cite_spans = []
            for sen_cite_span in cite_spans:
                if sen_cite_span["ref_id"] not in bib_entry_key_to_row_id_mapper:
                    continue
                
                start, end = sen_cite_span["start"], sen_cite_span["end"]
                ## make sure ther is no overlapping between multiple citation markers
                if len(cleaned_cite_spans) > 0 and start < int(cleaned_cite_spans[-1]["end"]):
                    continue
                
                if start >= len(sentence_text):
                    continue
                end = min( end, len(sentence_text) )
                
                sen_cite_span["start"] = str(start)
                sen_cite_span["end"] = str(end)
                sen_cite_span["text"] = sentence_text[start:end]
                sen_cite_span["ref_id"] = str(bib_entry_key_to_row_id_mapper[ sen_cite_span["ref_id"] ])
                
                cleaned_cite_spans.append( sen_cite_span )
            
            sentence_id = str(len(cleaned_paragraph_text))
            cleaned_paragraph_text.append(
                {
                    "sentence_id":sentence_id,
                    "sentence_text":sentence_text,
                    "cite_spans":cleaned_cite_spans
                }
            )
            
        return cleaned_paragraph_text
    
    
    def parse_para_list( self, para_list, bib_entry_key_to_row_id_mapper ):
        section_list = []
        current_section = None
        
        for para in para_list:            
            paragraph_text = self.parse_para( para, bib_entry_key_to_row_id_mapper )
            
            para_section = str(para.get("section",""))
            
            if current_section is None or (para_section != "" and para_section != current_section["section_title"]):
                if current_section is not None:
                    section_list.append(current_section)
                current_section = {
                    "section_id":str(len(section_list)),
                    "section_title":para_section,
                    "section_text":[
                        {
                            "paragraph_id":"0",
                            "paragraph_text":paragraph_text
                        }
                    ]
                }
            else:
                next_para_id = len(current_section["section_text"])
                current_section["section_text"].append(
                    {
                        "paragraph_id":str(next_para_id),
                        "paragraph_text":paragraph_text
                    }
                )
        if current_section is not None:
            section_list.append(current_section)
            
        if (" ".join(self.get_sentence_list_from_parsed_sections( section_list ))).strip() == "":
            section_list = []
            
        return section_list
                
    def parse_content( self, paper, bib_entry_key_to_row_id_mapper ):
        ### Abstract 
        abstract = ""
        ### Abstract_Parsed
        try:
            pdf_parsed_abstract = paper.get("pdf_parse",{}).get("abstract",[])
            if len( pdf_parsed_abstract ) == 0:
                abstract_text = str(paper.get("abstract",""))
                if abstract_text != "None" and abstract_text != "":
                    pdf_parsed_abstract = [ { "section":"Abstract", "text":abstract_text } ]
            assert len(pdf_parsed_abstract) > 0
            
            abstract_parsed = self.parse_para_list( pdf_parsed_abstract, bib_entry_key_to_row_id_mapper )
        except:
            abstract_parsed = []
        
        ### Fullbody
        fullbody = ""
        
        ### Fullbody_Parsed
        try:
            fullbody_parsed = self.parse_para_list( paper.get( "pdf_parse", {} ).get("body_text", []), bib_entry_key_to_row_id_mapper )
        except:
            fullbody_parsed = []
        return {
            "Abstract":abstract,
            "Abstract_Parsed":abstract_parsed,
            "Fullbody":fullbody,
            "Fullbody_Parsed":fullbody_parsed
        }
    
    def parse_reference(self, paper):
        try:
            bibref_text = {}
            body_text = paper.get("pdf_parse",{}).get("body_text", [])
            for para in body_text:
                for cit in para.get("cite_spans", []):
                    if isinstance(cit, dict):
                        ref_id, ref_text = cit.get("ref_id",""), cit.get("text","")
                        if ref_id != "":
                            bibref_text[ref_id] = ref_text
                            
            for ref_id in bibref_text:
                ref_text = bibref_text[ref_id]
                matched_texts = self.cit_marker_matcher.findall(ref_text)
                if len(matched_texts) > 0:
                    ref_text = matched_texts[0][1]+"."
                else:
                    ref_text = ""
                bibref_text[ref_id] = ref_text
                
        except:
            bibref_text = {}
            
        try:
            reference = []
            bib_entry_key_to_row_id_mapper = {}
            
            bib_entries = paper.get("pdf_parse",{}).get("bib_entries",{})
            bib_entry_keys = list(bib_entries.keys())
            try:
                bib_entry_keys.sort( key = lambda x : int(x[6:]) )
            except:
                pass    

            for bib_entry_key in bib_entry_keys:
                try:
                    parsed_entry = self.convert_bibentry_to_metadata( bib_entries[bib_entry_key] )
                    reference_text = self.get_citation_from_paper_metadata(parsed_entry)
                    if bibref_text.get(bib_entry_key,"").strip() != "":
                        reference_text = bibref_text[bib_entry_key] + " "+ reference_text
                    parsed_entry["ReferenceText"] = reference_text
                    
                    bib_entry_key_to_row_id_mapper[bib_entry_key] = len(reference)
                    reference.append(parsed_entry)
                except:
                    continue
        except:
            reference = []
            bib_entry_key_to_row_id_mapper = {}

        return reference, bib_entry_key_to_row_id_mapper
    
    def parse_additional_ids(self, paper):
        try:
            S2CID = str(paper.get("paper_id", "")).replace("None","")
            PMID = str(paper.get("pubmed_id", "")).replace("None","")
            PMCID = str(paper.get("pmc_id", "")).replace("None","")
            ArxivId = str(paper.get("arxiv_id", "")).replace("None","")
            ACLId = str(paper.get("acl_id","")).replace("None","")
            MAGId = str(paper.get("mag_id","")).replace("None","")
        except:
            S2CID = ""
            PMID = ""
            PMCID = ""
            ArxivId = ""
            ACLId = ""
            MAGId = ""
        return {
            "S2CID":S2CID,
            "PMID":PMID,
            "PMCID":PMCID,
            "ArxivId":ArxivId,
            "ACLId":ACLId,
            "MAGId":MAGId
        }

    
    def sent_tok(self, text, min_sen_len = 10 ):

        sens = self.sentence_boundary_matcher.split( text )
        for pos in range( len(sens)-1 ):
            sens[pos] += ". "
        
        return self.merge_sens( sens, min_sen_len = min_sen_len )

    def merge_sens(self, sens, min_sen_len = 10 ):
        out_sens =[]
        current_sen = None
    
        for sen in sens:
            sen_len = len(sen.split())
            if sen_len >= min_sen_len:
                if current_sen is not None:
                    out_sens.append( current_sen )
                current_sen = sen
            else:
                if current_sen is not None: 
                    current_sen += sen
                else:
                    current_sen = sen
        if current_sen is not None:
            if len( current_sen.split() ) < min_sen_len and len( out_sens ) > 0:
                out_sens[-1] += current_sen
            else:
                out_sens.append(current_sen)
        return out_sens
    
    def convert_bibentry_to_metadata(self, bibentry):
        metadata = {}
        metadata["Title"] = bibentry["title"]
        metadata["Author"] = []
        for author in bibentry.get("authors",[]):
            metadata["Author"].append({
                "GivenName":author.get("first",""),
                "FamilyName": author.get("last", "")
            })
        metadata["Venue"] = bibentry.get("venue","")
        metadata["PublicationDate"] = {"Year":str( bibentry.get("year","") )}
        return metadata


    def get_citation_from_paper_metadata(self,  paper_metadata ):
        author = paper_metadata.get("Author",[])
        title = paper_metadata.get("Title","")
        venue = paper_metadata.get("Venue","")
        year = paper_metadata.get("PublicationDate",{}).get("Year","")   
            
        author_list = []
        for pos,author_item in enumerate(author):
            if pos == 0:
                author_list.append( "%s, %s"%(  author_item.get("FamilyName",""), author_item.get("GivenName","") ) )
            else:
                author_list.append( "%s %s"%(  author_item.get("GivenName",""), author_item.get("FamilyName","") ) )    

        if len(author_list)>3:
            author_info = author_list[0] + " et al"
        elif len(author_list)>1:
            author_info = ", ".join( author_list[:-1] ) + ", and " + author_list[-1]
        elif len(author_list)==1:
            author_info = author_list[0]
        else:
            author_info = ""
        author_info += "."  

        title_info = "“"+title.rstrip(".")+".”"
        journal_info = venue
        if year.strip() != "":
            year_info = "(%s)"%(year)
        else:
            year_info = ""  

        citation_text = " ".join(" ".join( [author_info, title_info, journal_info, year_info  ] ).split()) +"."

        return citation_text
