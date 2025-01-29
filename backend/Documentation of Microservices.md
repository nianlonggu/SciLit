# Documentation of Microservices


```python
!pip install -q imageio
!pip install -q termcolor
```


```python
import requests, json
import matplotlib.pyplot as plt
import imageio
import numpy as np
from termcolor import colored
import time
```

## Define Helper Functions
* These helper functions are used only for this notebook for displaying results returned from the microservice API gateway.
* They are not necessary when using the the microservice APIs when deploying the frontend.


```python
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_title(title, max_len = 110):
    title = title +" " * (max_len-len(title)) +' "Cite'
    print(bcolors.BOLD + bcolors.HEADER + title + bcolors.ENDC)

def print_year(year):
    print(bcolors.BOLD + bcolors.OKBLUE + str(year) + bcolors.ENDC)

def print_section_name( section_name ):
    print(bcolors.BOLD  + section_name + bcolors.ENDC)
    
def print_highlighted_sentence(sen, end ="\n"):
    sen = sen.replace("\n"," ").replace("\r"," ")
    print(bcolors.BOLD + bcolors.WARNING + str(sen)[:150] + bcolors.ENDC, end=end, flush =True)

def remove_none(a):
    if a is None:
        return ""
    else:
        return a

def print_authors(authors):
    author_list = []
    for author in authors:
        given_name = remove_none(author.get("GivenName", ""))
        family_name = remove_none(author.get("FamilyName", ""))
        author_list.append( given_name+" "+family_name)
    print("   ".join(author_list))
    
def print_pagination_results(pagination_results):
    for res in pagination_results:
        print_title(res.get("Title",""))
        if isinstance(res.get("PublicationDate",{}),dict):
            print_year(res.get("PublicationDate",{}).get("Year",""))
        if isinstance(res.get("Author",[]),list) and len(res.get("Author",[]))>0:
            print_authors(res.get("Author",[]))
        if isinstance(res.get("relevant_sentences",[]),list) and len(res.get("relevant_sentences",[]))>0:
            print()
            print("...".join(res.get("relevant_sentences",[])))
        if res.get("Content",{}).get("Abstract","").strip() != "":
            print( res.get("Content",{}).get("Abstract","")  )
            print("\n")
        print()
        
def print_paper( paper_info, collection):
    print_title(paper_info.get("Title",""))
    print("source: ", collection)
    if isinstance(paper_info.get("PublicationDate",{}),dict):
        print_year(paper_info.get("PublicationDate",{}).get("Year",""))
    print_authors(paper_info.get("Author",[]))
    print("\n")
    
    if "Content" in paper_info:
        for tag in ["Abstract_Parsed","Fullbody_Parsed"]:
            if tag not in paper_info["Content"]:
                continue
            for section in paper_info["Content"][tag]:
                print_section_name( section.get("section_title","") )
                print("\n")
                for para in section.get("section_text",[]):
                    for sen in para.get("paragraph_text",[]):
                        sim = sen.get("sentence_similarity",0.0)
                        text = sen.get("sentence_text","")
                        if sim >0:
                            print_highlighted_sentence(text, end = " ")
                        else:
                            print(text, end=" ", flush = True)
                print("\n")
                
def color_sen(sen):
    sen_text = sen["sentence_text"]
    cite_spans = sen["cite_spans"]
    colored_text = ""
    current_pos = 0
    for cite_span in cite_spans:
        start, end = int(cite_span["start"]), int(cite_span["end"])
        colored_text += sen_text[current_pos:start]+colored(sen_text[start:end],"blue")
        current_pos = end
    colored_text += sen_text[current_pos:]
    return colored_text

def print_para( para ):
    corlored_para = ""
    for sen in para["paragraph_text"]:
        corlored_para += color_sen(sen) + " "
    print(corlored_para)

def print_sec( sec ):
    print(bcolors.BOLD+ sec["section_title"] +bcolors.ENDC + "\n")
    for para in sec["section_text"]:
        print_para(para)
        print()
```

## Microservice-Based Architecture

[![microservice architecture](images/architecture.png)](https://aclanthology.org/2023.acl-demo.22/)

## Address of API Gateway 

As shown in the architecture, once the backend service has been started, the API gateway is used the bridge the connection between frontend and backend. Therefore, from the perspective of frontend (or API user), we only need to know the address of the API gateway.

Suppose that in the file [final_api_gateway/docker-compose.yaml](final_api_gateway/docker-compose.yaml), the port mapping rule looks like:

        ports:
            - 8060:8060    # Host PORT : container PORT
this means it maps the host machine's 8060 port to the port 8060 of API gateway's docker container. In this case, when we can to send request to the API gateway, the base address (without endpoint name) is:

        http://localhost:8060

where localhost refers to the hostmachine. We can further use [ngrok](https://ngrok.com/) to map the port 8060 to www, to make the API gateway accessible from anywhere in the world. Then the API address will be changed to 

        https://xxxxx.ngrok.io (no port number is needed)
        
In this example, we run the backend in our local machine, so we set (suppose the host port is 8060):


```python
api_gateway_address = "http://localhost:8060" 
```

## Microservice: Document search

### Service address
Service address refers to the address to the corresponding endpoint: api gateway's base address + endpoint name


```python
api_gateway_address+"/ml-api/doc-search/v1.0"
```




    'http://localhost:8060/ml-api/doc-search/v1.0'



### Description
1. **Function:** perform document search under different scenarios, including: <br>
    a) semantic search:  selected content (text or paper) as ranking source & keywords filtering <br>
    b) search from my library <br>
    c) generic search: given the title of a paper, find this paper from our database
    
2. **Input:** a request dictionary that contains the following key-value pairs: <br>
    a) "**ranking_variable**": <br> 
    &ensp;&ensp; optional, default: ""(empty string) <br>
    &ensp;&ensp; texts that users type in the "ranking source text" box, or texts that are selected from the manuscript as the query. If "ranking_variable" is provided, then the value of "ranking_variable" will be used as final ranking source.<br>
    b) "**ranking_collection**": <br>
    &ensp;&ensp; optional, default: "" <br>
    &ensp;&ensp; If users want to find relevant papers of a certain query paper, then the collection name of that query paper must be provided. <br>
    c) "**ranking_id_field**": <br>
    &ensp;&ensp; optional, default: "" <br>
    &ensp;&ensp; If users want to find relevant papers of a certain query paper, then the paper id field of that query paper must be provided. E.g. the paper id type can be "id_int", which is most commonly used. It is also possible to use the "DOI" field as paper id. <br>
    d) "**ranking_id_value**": <br>
    &ensp;&ensp; optional, default: "" <br>
    &ensp;&ensp; If users want to find relevant papers of a certain query paper, then the paper id value of that query paper must be provided.<br>
    e) "**ranking_id_type**": <br>
    &ensp;&ensp; optional, default: "", not necessary<br>
    f) "**keywords**": <br>
    &ensp;&ensp; optional, default: ""<br>
    &ensp;&ensp; This is used for keyword boolean filter. If all the keys above are not provided and only keywords provided, then use keywords alse as ranking source. When users want to perform a generic search, e.g. **search for a paper given title**, then simply use the title as "keywords". In this case, the ranking variable can either be the abstract (if available) or "" (empty string). This is documented in more detail below.<br> 
    g) "**paper_list**": <br>
    &ensp;&ensp; optional, default: ""<br>
    &ensp;&ensp; This is used to specify a range of papers within wich users search for relevant papers. For example, if users want to search for relevant papers from "My Libraray", then set the value of "paper_list" as the list of the ids of the papers in users' libraray, with the following format:<br> [ { "collection":"PMCOA", "id_field": "id_int", "id_value": 123  }, ... ]<br>
    h) "**username**": <br>
    &ensp;&ensp; optional, default: ""<br>
    i) "**nResults**": <br> 
    &ensp;&ensp; The maximum number of returned paper ids <br>
    &ensp;&ensp; optional, default: 100<br>
    Max number of results to be returned. <br>
3. **Output:** A results dictionary with the following format: <br>
{ "query_id": "fa27a7a6-0026-45f9-9c81-e47cf4ea5c57", <br>
  "response": [ {'collection': 'pubmed', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 123}, ...  ], <br>
  'search_stats': {'DurationTotalSearch': 87, 'nMatchingDocuments': 1000000}<br>
}<br>
Here "query_id" is a randomly generated unique id string that is associated with current search behavior. This can be used to achieve the click feedback function. For example, when users search for something, after they get the searched results and they click a certain paper, then the frontend can return current "query_id" and the id information of the clicked paper back to the click-feedback api (described below).


### Example


```python
ranking_variable = "recent progress in Covid-19"
keywords = "covid"
query_data ={
    "ranking_variable":ranking_variable,
    "keywords":keywords,
}
output = requests.post( api_gateway_address+"/ml-api/doc-search/v1.0", 
                                      data = json.dumps(  query_data ), 
                                      headers = {"Content-Type": "application/json"} ).json()

print(output)
```

    {'query_id': 'd510ee29-6c02-490f-b38d-a5e57fdf7c97', 'response': [{'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 798}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 499}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 664}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 251}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 38}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 722}, {'collection': 'arXiv', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 213}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 504}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 1011}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 638}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 346}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 666}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 905}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 237}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 708}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 712}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 340}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 1007}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 787}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 535}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 404}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 700}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 461}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 784}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 212}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 12}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 143}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 640}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 292}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 843}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 44}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 557}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 547}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 813}, {'collection': 'arXiv', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 448}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 822}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 23}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 752}, {'collection': 'arXiv', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 337}, {'collection': 'arXiv', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 745}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 530}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 786}, {'collection': 'arXiv', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 250}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 781}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 1027}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 502}, {'collection': 'arXiv', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 435}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 639}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 77}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 704}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 331}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 870}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 993}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 641}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 1006}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 732}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 645}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 324}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 680}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 89}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 808}, {'collection': 'arXiv', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 32}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 966}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 554}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 505}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 5}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 815}, {'collection': 'arXiv', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 189}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 391}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 359}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 740}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 768}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 466}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 624}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 97}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 337}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 869}, {'collection': 'arXiv', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 586}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 246}, {'collection': 'arXiv', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 180}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 725}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 858}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 847}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 1020}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 1019}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 855}, {'collection': 'arXiv', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 67}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 501}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 650}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 898}, {'collection': 'arXiv', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 173}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 586}, {'collection': 'arXiv', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 77}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 979}, {'collection': 'arXiv', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 306}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 394}, {'collection': 'arXiv', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 666}, {'collection': 'PMCOA', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 986}, {'collection': 'arXiv', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 111}, {'collection': 'arXiv', 'id_field': 'id_int', 'id_type': 'int', 'id_value': 607}], 'search_stats': {'DurationTotalSearch': 9695, 'nMatchingDocuments': 143}}

### Keyword filtering

SciLit enables advanced filtering of papers with boolean logic during literature discovery. Filtering is achieved by including specific keywords when submitting the POST request to the doc-search API, like so:
- `CRISPR`-> Papers must contain the term "CRISPR" somewhere (i.e., in content or in metadata)
- `argument mining|argument parsing` -> Papers must contain "argument mining" or "argument parsing" somewhere

To search only among papers with a keyword in a specific field, prepend the field to the keyword like so:
- **Title**
	- `Title:EEG` -> Only papers whose titles contain "EEG"
	- `Title:!COVID` -> Only papers whose titles do not contain "COVID"
- **Venue**
	- `Venue:ICML` -> Papers must be from a venue whose name contains "ICML"
	- `Venue:Nature|arXiv` -> Papers must be from a venue whose name contains either "Nature" or "arXiv"
- **Year** of publication
	- `Year:2020` -> Paper must be from the year 2020
	- `Year:..2003` -> Paper must be from up to 2003 (inclusive)
	- `Year:1996..` -> Paper must be from after 1996 (inclusive)
	- `Year:!2020..2024` -> Paper must not be from between 2020 and 2024 (inclusive)
- **Author** name
	- `Author:Cohen`, `Author.FullName:Cohen` -> Only papers where at least one author's name contains "Cohen"
	- `Author.GivenName:!Hopkind` -> Only papers where no author's given name contains "Hopkind"
	- `Author.FamilyName:Tchaikovsky|Chopin` -> Only papers where at least one author's family name contains "Tchaikovsky" or "Chopin"
- **DOI**
	- `DOI:10.1038/s41586-024-08455-0`: Only papers whose DOI is exactly "10.1038/s41586-024-08455-0"

To search only among papers with certain fields available, try: 
- `AvailableField:Content.Abstract_Parsed` -> For papers with abstracts
- `AvailableField:Content.Fullbody_Parsed` -> For papers with fullbody texts 

To specify that multiple keywords should be used for filtering simultaneously, just submit multiple separate keywords:
- `rubisco` `protein engineering` -> Papers must contain both "rubisco" and "protein engineering" somewhere
- `Title:COVID` `Year:!2021` -> Only papers whose titles contain "COVID" and are not from 2021

## Microservice: Query Paper Database

### Service address


```python
api_gateway_address+"/ml-api/get-papers/v1.0"
```




    'http://localhost:8060/ml-api/get-papers/v1.0'



### Description
1. **Function:** Given a list of paper ids, return the content of those papers. The frontend can also specify which field (e.g abstract/title/date) to return. This API can be generally used to display a list papers. For example, **display a page of search results, or display all papers in my library**

2. **Input:** <br>
    a) "**paper_list**": <br>
    &ensp;&ensp; **mandatory**<br>
    &ensp;&ensp; a list of papers' ids to be displayed and highlighted. For example, a list of ids of the papers to be displayed on the first retrived page, or a list ids of the papers in "My Library" <br>
    &ensp;&ensp; Format: [ { "collection":"PMCOA", "id_field": "id_int", "id_value": 123  }, ... ]<br>
    b) "**projection**": <br>
    &ensp;&ensp; optional, default: "" <br>
    &ensp;&ensp; The frontend can specify which field to return, with a high level of flexibility. This parameter is similar to the pymongoDB api.  If "projection" is not specified, the by default the server will return the following fields: "PublicationDate", "Author", "Title", "Venue", "id_int", "relevant_sentences". If the frontend requires only title and abstract, then set the value of "projection" as the following:  { "Title":1, "Content.Abstract":1 } <br>
3. **Output:** A list of papers, each of which has structured information confined by the "projection". <br>
**Note: the output will always be a list, even if the value of the "paper_list" is a list of one element.**

* If in the paper_list at a certain position a wrong paper id information provide, the service will return a placeholder {} for the corresponding paper, in order to make sure the returned paper list and the paper_list parameter have the same length

* If the paper_list parameter is empty [], the service will just return an empty list []

### Example
Given a query, search for relevant papers and get the paper's content


```python
ranking_variable = "recent progress in Covid-19"
keywords = "covid"
query_data ={
    "ranking_variable":ranking_variable,
    "keywords":keywords,
}
searched_document_ids = requests.post( api_gateway_address+"/ml-api/doc-search/v1.0", 
                                      data = json.dumps(  query_data ), 
                                      headers = {"Content-Type": "application/json"} ).json()["response"]

search_document_contents = requests.post(  api_gateway_address+ "/ml-api/get-papers/v1.0", 
                                   data = json.dumps( {
                                       "paper_list":searched_document_ids,
                                   } ), 
                                   headers = {"Content-Type": "application/json"} ).json()["response"]
```

Let's have a look at the first 10 search results:


```python
print_pagination_results( search_document_contents[:10])
```

    [1m[95mA systematic review of participatory approaches to empower health workers in low- and middle-income countries, highlighting Health Workers for Change "Cite[0m
    [1m[94m2023[0m
    
    [1m[95mAcceptance of Public Health Measures During the COVID-19 Pandemic: A Cross-Sectional Study of the Swiss Population’s Beliefs, Attitudes, Trust, and Information-Seeking Behavior "Cite[0m
    [1m[94m2023[0m
    Maddalena Fiordelli   Maddalena Fiordelli   Sara Rubinelli   Sara Rubinelli   Nicola Diviani   Nicola Diviani
    
    [1m[95mDoes COVID-19 vaccine exacerbate rotator cuff symptoms? A prospective study                                    "Cite[0m
    [1m[94m2023[0m
    Servet İğrek   İbrahim Ulusoy   Aytek Hüseyin Çeliksöz
    
    [1m[95mA rapid cell-free expression and screening platform for antibody discovery                                     "Cite[0m
    [1m[94m2023[0m
    Andrew C. Hunt   Andrew C. Hunt   Bastian Vögeli   Bastian Vögeli   Ahmed O. Hassan   Laura Guerrero   Laura Guerrero   Weston Kightlinger   Weston Kightlinger   Danielle J. Yoesep   Danielle J. Yoesep   Antje Krüger   Antje Krüger   Madison DeWinter   Madison DeWinter   Madison DeWinter   Michael S. Diamond   Michael S. Diamond   Michael S. Diamond   Michael S. Diamond   Ashty S. Karim   Ashty S. Karim   Michael C. Jewett   Michael C. Jewett   Michael C. Jewett   Michael C. Jewett   Michael C. Jewett
    
    [1m[95mAssociations of online religious participation during COVID-19 lockdown with subsequent health and well-being among UK adults "Cite[0m
    [1m[94m2023[0m
    Koichiro Shiba   Koichiro Shiba   Richard G. Cowden   Natasha Gonzalez   Yusuf Ransome   Atsushi Nakagomi   Ying Chen   Matthew T. Lee   Tyler J. VanderWeele   Tyler J. VanderWeele   Tyler J. VanderWeele   Daisy Fancourt
    
    [1m[95mThe diversity of providers’ and consumers’ views of virtual versus inpatient care provision: a qualitative study "Cite[0m
    [1m[94m2023[0m
    Robyn Clay-Williams   Peter Hibbert   Peter Hibbert   Ann Carrigan   Ann Carrigan   Natalie Roberts   Elizabeth Austin   Diana Fajardo Pulido   Isabelle Meulenbroeks   Hoa Mi Nguyen   Mitchell Sarkies   Sarah Hatem   Katherine Maka   Graeme Loy   Jeffrey Braithwaite
    
    [1m[95mUtilizing a Capture-Recapture Strategy to Accelerate Infectious Disease Surveillance                           "Cite[0m
    [1m[94m2023[0m
    Lin Ge   Yuzi Zhang   Lance Waller   Robert Lyles
    
    [1m[95mWhat is the health status of girls and boys in the COVID-19 pandemic? Selected results of the KIDA study       "Cite[0m
    [1m[94m2023[0m
    Julika Loss   Miriam Blume   Laura Neuperdt   Nadine Flerlage   Tim Weihrauch   Kristin Manz   Roma Thamm   Christina Poethko-Müller   Elvira Mauz   Petra Rattay   Jennifer Allen   Mira Tschorn   Mira Tschorn
    
    [1m[95mProlonged T-cell activation and long COVID symptoms independently associate with severe COVID-19 at 3 months   "Cite[0m
    [1m[94m2023[0m
    Marianna Santopaolo   Michaela Gregorova   Fergus Hamilton   David Arnold   Anna Long   Aurora Lacey   Elizabeth Oliver   Alice Halliday   Holly Baum   Kristy Hamilton   Rachel Milligan   Olivia Pearce   Lea Knezevic   Begonia Morales Aza   Alice Milne   Emily Milodowski   Eben Jones   Rajeka Lazarus   Anu Goenka   Anu Goenka   Adam Finn   Adam Finn   Adam Finn   Nicholas Maskell   Andrew D Davidson   Kathleen Gillespie   Linda Wooldridge   Laura Rivino
    
    [1m[95mUsing technology to reduce critical deterioration (the DETECT study): a cost analysis of care costs at a tertiary children's hospital in the United Kingdom "Cite[0m
    [1m[94m2023[0m
    Eduardo Costa   Eduardo Costa   Céu Mateus   Bernie Carter   Holly Saron   Chin-Kien Eyton-Chong   Fulya Mehta   Steven Lane   Sarah Siner   Jason Dean   Michael Barnes   Chris McNally   Caroline Lambert   Caroline Lambert   Bruce Hollingsworth   Enitan D. Carrol   Enitan D. Carrol   Gerri Sefton
    


## Microservice: Extractive Summarization

### Service address


```python
api_gateway_address+"/ml-api/extractive-summarize/v1.0"
```




    'http://localhost:8060/ml-api/extractive-summarize/v1.0'



### Description

1. **Function:** Given a document containing a list of sentences, return the highlights of it.


2. **Input:** <br>
    a) "**sentence_list**" : a list of sentences, e.g., we can convert a full scientific paper into a list of consecutive  sentences, and use it as the input
    
    
3. **Output:** Extracted summary (highlights) of the given paper. It is a dictionary containing 

        "summary": extracted_sen,
        "sentence_position":sen_pos

### Example
We can search for a paper, and get the extractive summary of it


```python
ranking_variable = "recent progress in Covid-19"
keywords = "covid"
query_data ={
    "ranking_variable":ranking_variable,
    "keywords":keywords,
}
searched_document_ids = requests.post( api_gateway_address+"/ml-api/doc-search/v1.0", 
                                      data = json.dumps(  query_data ), 
                                      headers = {"Content-Type": "application/json"} ).json()["response"]

## We get the content of the first paper
document_content = requests.post(  api_gateway_address+ "/ml-api/get-papers/v1.0", 
                                   data = json.dumps( {
                                       "paper_list":searched_document_ids,
                                   } ), 
                                   headers = {"Content-Type": "application/json"} ).json()["response"][0]

## we need to convert the paper's full text into a list of sentences
sentences = []
for sec in document_content["Content"]["Abstract_Parsed"] + document_content["Content"]["Fullbody_Parsed"]:
    for para in sec["section_text"]:
        for sen in para["paragraph_text"]:
            sentences.append(sen["sentence_text"])

## summarize it!
summary = requests.post(  api_gateway_address+"/ml-api/extractive-summarize/v1.0", 
                                   data = json.dumps( {
                                       "sentence_list":sentences,
                                   } ), 
                                   headers = {"Content-Type": "application/json"} ).json()["response"]
summary
```




    {'summary': ['Abstract This systematic review assesses participatory approaches to motivating positive change among health workers in low- and middle-income countries (LMICs).',
      'The mistreatment of clients at health centres has been extensively documented, causing stress among clients, health complications and even avoidance of health centres altogether.',
      'Health workers, too, face challenges, including medicine shortages, task shifting, inadequate training and a lack of managerial support.',
      'Solutions are urgently needed to realise global commitments to quality primary healthcare, country ownership and universal health coverage.',
      'This review searched 1243 titles and abstracts, of which 32 were extracted for full text review using a published critical assessment tool.',
      'Eight papers were retained for final review, all using a single methodology, ‘Health Workers for Change’ (HWFC).',
      'Health workers acknowledged their negative behaviour towards clients, often as a way of coping with their own unmet needs.'],
     'sentence_position': [0, 1, 2, 3, 4, 5, 8]}



## Microservice: Citation Generation

### Service address


```python
api_gateway_address + "/ml-api/generate-citation/v1.0"
```




    'http://localhost:8060/ml-api/generate-citation/v1.0'



### Description

1. **Function:** Batch-wise generation of citation sentences given a batch of local contexts, keywords, and papers to be cited. (The batchwise operation is used to handle concurrent requests, e.g. generating citation sentences for multiple papers simultaneously.)

2. **Input:**<br>
   a) "**context_list**" : a batch of local context texts (text in the manuscript  before the target citation sentence.)<br>
   b) "**keywords_list**": a batch of keywords used to guide the generation<br>
   c) "**papers**": a batch of papers' content to be cited
   
2. **Output:**<br>
   a batch of generated citation sentences

### Example
Given a query, we can search for relevant papers, and generated citation sentences for top 5 relevant papers.


```python
ranking_variable = "There have been many recent advances in the treatment of Covid-19."
keywords = "Covid"
query_data ={
    "ranking_variable":ranking_variable,
    "keywords":keywords,
}
searched_document_ids = requests.post( api_gateway_address+"/ml-api/doc-search/v1.0", 
                                      data = json.dumps(  query_data ), 
                                      headers = {"Content-Type": "application/json"} ).json()["response"]

## We get the content of the top 5 paper
document_contents = requests.post(  api_gateway_address+ "/ml-api/get-papers/v1.0", 
                                   data = json.dumps( {
                                       "paper_list":searched_document_ids[:5],
                                   } ), 
                                   headers = {"Content-Type": "application/json"} ).json()["response"]

## Generate citation sentences:
citation_sentences = requests.post(  api_gateway_address+ "/ml-api/generate-citation/v1.0",
                                   data = json.dumps( {
                                       ## we use the ranking variable also as context, as an example
                                       "context_list":[ranking_variable for _ in range(len(document_contents))],
                                       ## we use the ranking keywords also as the keywords to guide generation, but this can be changed to other keywords
                                       "keywords_list":[keywords for _ in range(len(document_contents))],
                                       "papers":document_contents
                                   } ), 
                                   headers = {"Content-Type": "application/json"} ).json()["response"]


citation_sentences
```




    ['However, the treatment of Covid-19 has been largely based on a lack of knowledge, skills, and experience [ #CIT ].',
     'However, there is still a lack of data on the effects of Covid-19 vaccination on shoulder injury [ #CIT ].',
     'IL-5 is a well-known anti-inflammatory cytokine that plays an important role in the treatment of COVID-19 [ #CIT ].',
     'For example, a large reservoir-based continuous positive airway pressure (CPAP) has been developed for the treatment of COVID-19 [ #CIT ].',
     'For example, the treatment of Covid-19 has been mainly based on the use of a variety of drugs [ #CIT ].']



## Microservice: Citation Formating

### Service address


```python
api_gateway_address + "/ml-api/citation-formatting-service/v1.0"
```




    'http://localhost:8060/ml-api/citation-formatting-service/v1.0'



### Description
1. **Function:** Given a list of paper ids, return the formatted citation information (e.g. in bibtex or mla format) of the input papers

2. **Input:** <br>
    a) "**paper_list**": <br>
    &ensp;&ensp; **mandatory**<br>
    &ensp;&ensp; a list of papers' ids:
    &ensp;&ensp; Format: [ { "collection":"PMCOA", "id_field": "id_int", "id_value": 123  }, ... ]<br>
    (NOTE: This has to be a list even if there is only one paper)
    
    b) "**username**": same as doc-serach api <br>
3. **Output:** A list of papers' citation entries, each citation entry is a dictionary that contains two keys "bibtex" and "mla". The values of these two keys represent two different format of the citation information <br>

### Example


```python
paper_ids = [ 
              {"collection":"PMCOA","id_field":"id_int", "id_value":1},
              {"collection":"PMCOA","id_field":"id_int", "id_value":2},
]

requests.post( api_gateway_address +"/ml-api/citation-formatting-service/v1.0", 
                                      data = json.dumps( 
                                          {
                                              "paper_list":paper_ids
                                          }
                                      ), 
                                      headers = {"Content-Type": "application/json"} ).json()
```




    {'response': [{'bibtex': '@article{2022, paperIDInfo={collection:PMCOA, id_value:1, id_type:int}, title={“Bringing you the Best”: John Player &amp; Sons, Cricket, and the Politics of Tobacco Sport Sponsorship in Britain, 1969–1986}, volume={80}, ISSN={2666-7711}, url={http://dx.doi.org/10.1163/26667711-bja10022}, DOI={10.1163/26667711-bja10022}, number={1}, journal={European Journal for the History of Medicine and Health}, publisher={Brill}, author={O’Neill, Daniel and Greenwood, Anna}, year={2022}, month={Aug}, pages={152–184} }',
       'mla': 'O’Neill, Daniel, and Anna Greenwood. “‘Bringing You the Best’: John Player &amp; Sons, Cricket, and the Politics of Tobacco Sport Sponsorship in Britain, 1969–1986.” European Journal for the History of Medicine and Health, vol. 80, no. 1, Aug. 2022, pp. 152–84. Crossref, https://doi.org/10.1163/26667711-bja10022.'},
      {'bibtex': '@article{2022, paperIDInfo={collection:PMCOA, id_value:2, id_type:int}, title={Acetylcholine Boosts Dendritic NMDA Spikes in a CA3 Pyramidal Neuron Model}, volume={489}, ISSN={0306-4522}, url={http://dx.doi.org/10.1016/j.neuroscience.2021.11.014}, DOI={10.1016/j.neuroscience.2021.11.014}, journal={Neuroscience}, publisher={Elsevier BV}, author={Humphries, Rachel and Mellor, Jack R. and O’Donnell, Cian}, year={2022}, month={May}, pages={69–83} }',
       'mla': 'Humphries, Rachel, et al. “Acetylcholine Boosts Dendritic NMDA Spikes in a CA3 Pyramidal Neuron Model.” Neuroscience, vol. 489, May 2022, pp. 69–83. Crossref, https://doi.org/10.1016/j.neuroscience.2021.11.014.'}]}



## Microservice: Title Generic Search

### Service address


```python
api_gateway_address+"/ml-api/title-generic-search/v1.0"
```




    'http://localhost:8060/ml-api/title-generic-search/v1.0'



### Description
1. **Function:** Given a list of titles, find the corresponding papers from our database. 

2. **Input:** <br>
    a) "**titles**":
      1) "titles" can be a list of strings. In this case, we assume each string is the title of a paper;
      2) "titles" can also be a list of dictionaries, and each dictionary contains the metadata (Title and Author) of a paper, among the metadata, the key "Title" is mandatory, while "Author" is not mandantory but recommended. For example: <br>
      
             [ {"Title":"bird song ...","Author":[{"GivenName":"Tom", "FamilyName":"Lee"}]}, {"Title": "machine learning"} ] 
    
    b) "**projection**": same as pagination api<br>
    &ensp;&ensp; optional. Default: None   (return all the content of the found paper) <br>
    "projection" specifies which field to return as usual. If "projection" is set to None, all the content of the found paper will be returned.

3. **Output:** A list of papers, each of which has structured information confined by the "projection". If a paper is not found, then the value of the key "found" is False. If the paper is found, then "found"=True, and "collection","id_field","id_type" and "id_value" will be returned apart from the items defined by the projection  <br>
     1) This API returns a list of papers, each paper is a dictionary.
        Given a title/metadata, if we find the paper, we will return the id information (collection, id_field, id_type, id_value), and in the dictionary, the value of "found" will be True. Moreover, the paper's content will also be included in the returned results, determined by the "projection" given when calling the API.
     2) If we do not find the paper, in the returned dictionary the value of "found" is False.

### Example


```python
query_data = {
    "titles":[
        ## Either is okay: 1) a title's string or 2) a dictionary with "Title" (and "Author") as keys.
        "A rapid cell-free expression and screening platform for antibody discovery  ",
        {"Title":"Adaptive GLCM sampling for transformer-based COVID-19 detection on CT ",
         "Author": [{'GivenName': 'Jung', 'FamilyName': 'Okchul'}]
        },
    ],
    "projection": {}
}

searched_papers = requests.post( api_gateway_address+"/ml-api/title-generic-search/v1.0", 
                                      data = json.dumps(  query_data ), 
                                      headers = {"Content-Type": "application/json"} ).json()["response"]

searched_papers
```




    [{'Title': 'A rapid cell-free expression and screening platform for antibody discovery  ',
      'Author': [],
      'First_Author': '',
      'found': True,
      'collection': 'PMCOA',
      'id_field': 'id_int',
      'id_type': 'int',
      'id_value': 251,
      '_id': 'PMCOA_251'},
     {'Title': 'Adaptive GLCM sampling for transformer-based COVID-19 detection on CT ',
      'Author': [{'GivenName': 'Jung', 'FamilyName': 'Okchul'}],
      'First_Author': 'Jung Okchul',
      'found': False}]




```python

```
