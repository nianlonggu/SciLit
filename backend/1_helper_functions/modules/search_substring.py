import sys, json

import re
import timeout_decorator
from fuzzysearch import find_near_matches
import numpy as np
@timeout_decorator.timeout(1, use_signals=False)
def search_substring_core( substring, text ):
    for max_l_dist in range(5, 20, 5):
        res = find_near_matches(substring.lower(), text.lower() , max_l_dist= max_l_dist)
        if len(res)>0:
            break
    
    if len(res) == 0:
        start_pos = np.random.choice(len(substring)-30)
        length = 30
        end_pos = min( start_pos+length, len( substring ) )
        subsubstring = substring[start_pos:end_pos]
        for submax_l_dist in range(5, 20, 5):
            res = find_near_matches(subsubstring.lower(), text.lower() , max_l_dist= submax_l_dist)
            if len(res)>0:
                break
        if len(res) >0:
            return {
                "start":res[0].start - start_pos,
                "end":res[0].end + len( substring ) - end_pos
            }

    if len(res) == 0 or res[0].start >= res[0].end - 1:
        return None
    return {
        "start":res[0].start,
        "end":res[0].end - 1
    }

def remove_multiple_blank_characters( s ):
    b_matcher = re.compile("\s(?=\s)")
    matched_poses = [[m.start(),m.end()] for m in b_matcher.finditer(s)]
    
    new_s = ""
    pos_mapper = []
    start_pos = 0
    for m_start, m_end in matched_poses:
        new_s += s[start_pos:m_start]
        pos_mapper+= np.arange( start_pos, m_start ).tolist()
        start_pos = m_end
    
    new_s += s[start_pos:]
    pos_mapper+= np.arange( start_pos, len(s) ).tolist()

    return new_s, pos_mapper


def search_substring( substring, text):
    try:
        new_text, pos_mapper = remove_multiple_blank_characters(text)
        res = search_substring_core( substring, new_text )
        if res is not None:
            res["start"] = max( pos_mapper[ res["start"] ], 0)
            res["end"] = min(pos_mapper[ res["end"] ]+1, len(text))
            assert res["start"]< res["end"]
    except:
        res = None  
        
    if res is None:
        res_list = []
    else:
        res_list = [res]
        
    return res_list