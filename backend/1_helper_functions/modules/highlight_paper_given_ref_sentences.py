import Levenshtein as lev
from copy import deepcopy
import numpy as np

def get_highlighted_paper_given_ref_sentences( paper, ref_sentences ):
    
    paper = deepcopy(paper)
    
    if "Content" not in paper:
        paper["Content"]= { "Abstract":"",
                            "Abstract_Parsed":[],
                            "Fullbody":"",
                            "Fullbody_Parsed":[]
                          }
    paper["Content"]["Abstract"] = paper["Content"].get("Abstract","")
    paper["Content"]["Abstract_Parsed"] = paper["Content"].get("Abstract_Parsed",[])
    paper["Content"]["Fullbody"] = paper["Content"].get("Fullbody","")
    paper["Content"]["Fullbody_Parsed"] = paper["Content"].get("Fullbody_Parsed",[])
    
    abstract_parsed = paper["Content"]["Abstract_Parsed"]
    fullbody_parsed = paper["Content"]["Fullbody_Parsed"]
    
    matched_sentence_id_infos = [None for _ in ref_sentences]
    
    for sec_count, sec in enumerate(abstract_parsed+fullbody_parsed):
        section_id = sec["section_id"]
        for para in sec["section_text"]:
            paragraph_id = para["paragraph_id"]
            for sen in para["paragraph_text"]:
                sentence_id = sen["sentence_id"]
                lev_ratio_list = np.array([ lev.ratio( ref_sen, sen["sentence_text"] ) for ref_sen in ref_sentences ])
                
                if len(ref_sentences)== 0 or np.max( lev_ratio_list )<0.95:
                    default_action = "none"
                else:
                    default_action = "highlight"
                    
                    closest_ref_sen_id = np.argmax( lev_ratio_list )
                    if sec_count < len(abstract_parsed):
                        field_name = "abstract"
                    else:
                        field_name = "fullbody"
                    matched_sentence_id_infos[closest_ref_sen_id] = { 
                        "field_name":field_name,
                        "section_id":str(section_id),
                        "paragraph_id":str(paragraph_id),
                        "sentence_id":str(sentence_id)
                    }
                    
                cite_spans = sorted(sen.get("cite_spans",[]), key = lambda x:x["start"] )
                
                sen["spans"] = []
                current_pos = 0
                for item in cite_spans:
                    item["start"] = int(item["start"])
                    item["end"] = int(item["end"])
                    
                    if item["start"]>current_pos:
                        sen["spans"].append( {
                            "start":current_pos, 
                            "end":item["start"], 
                            "action":default_action,
                            "param":{}
                        } )
                    sen["spans"].append( {
                            "start":item["start"], 
                            "end":item["end"], 
                            "action":"citation_marker",
                            "param":{"ref_id":item["ref_id"]}
                        } )
                    current_pos = item["end"]
                if current_pos<len(sen["sentence_text"]):
                    sen["spans"].append( {
                            "start":current_pos, 
                            "end":len(sen["sentence_text"]), 
                            "action":default_action,
                            "param":{}
                        } )
                for item in sen["spans"]:
                    item["start"] = str(item["start"])
                    item["end"] = str(item["end"])
                    
    
    ref_sentences_with_matched_sen_ids = [ {"text":text, 
                                            "matched_sen_id_info":matched_sen_id_info
                                           } for text, matched_sen_id_info in zip( ref_sentences, matched_sentence_id_infos )  ]
    
    return { "highlighted_paper":paper,
             "ref_sentences_with_matched_sen_ids":ref_sentences_with_matched_sen_ids
           }
        