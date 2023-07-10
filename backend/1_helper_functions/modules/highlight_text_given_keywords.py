import numpy as np
import nltk
nltk.download('stopwords', quiet = True)
nltk.download('wordnet',quiet = True)
nltk.download('punkt', quiet = True)
from nltk.tokenize import  RegexpTokenizer
# from nltk.stem import WordNetLemmatizer 
from functools import lru_cache
from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize  
import spacy

# class WordTokenizer:
#     def __init__(self ):
#         self.tokenizer = RegexpTokenizer(r'\w+')
#         # self.lemmatizer = WordNetLemmatizer()
#         self.general_stopwords = set(stopwords.words('english'))

#     # @lru_cache(100000)
#     # def lemmatize( self, w ):
#     #     return self.lemmatizer.lemmatize(w)
    
#     def tokenize(self, sen, remove_stopwords = False ):
#         word_list = []
#         for w in self.tokenizer.tokenize( sen.lower() ):
#             if w in self.general_stopwords:
#                 if not remove_stopwords:
#                     word_list.append(w)
#             else:
#                 word_list.append( self.lemmatize(w) )
                
#         return word_list

# class WordTokenizer:
#     def __init__(self ):
#         self.nlp = spacy.load('en_core_web_sm', disable=["parser", "ner", "tagger"])
#     @lru_cache(100000)
#     def tokenize(self, sen, remove_stopwords = False ):
#         doc = self.nlp( sen )
#         return [token.lemma_ for token in doc if not remove_stopwords or not token.is_stop ]


class WordTokenizer:
    def __init__(self ):
        self.general_stopwords = set(stopwords.words('english'))
    def tokenize(self, sen, remove_stopwords = False ):
        return [ w for w in sen.lower().split() if not remove_stopwords or w not in self.general_stopwords ]
    
class TextHighlighterGivenKeywords:
    def __init__(self, ):
        self.tokenizer = WordTokenizer()
    
    def highlight_text( self, text, keywords ):
        ref_words = set( self.tokenizer.tokenize( keywords, remove_stopwords = True ))
        
        words_and_labels = []
        for w in text.split():
            if " ".join( self.tokenizer.tokenize(w, remove_stopwords = False) ) in ref_words:
                words_and_labels.append( (w, 1) )
            else:
                words_and_labels.append( (w, 0) )
                
        highlight_spans = []
        highlighted_text = ""
        
        for word, label in words_and_labels:
            if label == 1:
                start = len(highlighted_text)
                highlighted_text += word + " "
                end = len(highlighted_text)
                
                if len(highlight_spans) == 0 or highlight_spans[-1]["end"]<start:
                    highlight_spans.append( {
                                         "start": start,
                                         "end": end
                                        } 
                                      )
                else:
                    highlight_spans[-1]["end"] = end
            else:
                highlighted_text += word + " "
        return highlight_spans