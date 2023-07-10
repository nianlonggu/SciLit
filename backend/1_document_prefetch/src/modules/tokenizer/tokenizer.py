import nltk
nltk.download('stopwords', quiet = True)
nltk.download('wordnet',quiet = True)
nltk.download('punkt', quiet = True)
nltk.download('omw-1.4', quiet = True)
from nltk.tokenize import  RegexpTokenizer
from nltk.stem import WordNetLemmatizer 
from functools import lru_cache
from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize
import string

class SentenceTokenizer:
    def __init__(self ):
        self.tokenizer = RegexpTokenizer(r'\w+')
        self.lemmatizer = WordNetLemmatizer()
        self.general_stopwords = set(stopwords.words('english')) - set(list(string.ascii_lowercase))

    @lru_cache(100000)
    def lemmatize( self, w ):
        return self.lemmatizer.lemmatize(w)
    
    def tokenize(self, sen, remove_stopwords = False ):
        word_list = []
        for w in self.tokenizer.tokenize( sen.lower() ):
            if w in self.general_stopwords:
                if not remove_stopwords:
                    word_list.append(w)
            else:
                word_list.append( self.lemmatize(w) )
                
        return " ".join( word_list )