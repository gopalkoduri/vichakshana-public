from os.path import expanduser
from os import chdir
from SPARQLWrapper import SPARQLWrapper, JSON, N3, POST
import requests
import codecs
from numpy import arange


def get_subgraph(pages):
    sparql = SPARQLWrapper("http://devaraya.s.upf.edu/dbpedia-sparql")
    
    values = " ".join(['<'+i+'>' for i in pages])
    query_content = """
    CONSTRUCT 
    {{ 
        ?s ?p1 ?o1 .
        ?s2 ?p2 ?o .
    }} 
    WHERE 
    {{ 
        {{
            values ?s {{ {0} }}
            ?s ?p1 ?o1 .
        }}
        UNION
        {{
            values ?o {{ {0} }}
            ?s2 ?p2 ?o .        
        }}
    }}
    """.format(values)
    #return query_content
    sparql.setMethod(POST)
    sparql.setQuery(query_content)
    sparql.setReturnFormat(N3)
    results = sparql.query().convert()
    
    return results

if __name__ == '__main__':
    home = expanduser('~')
    chdir(home+'/workspace/vichakshana/vichakshana/')

    keyword = 'baroque_music'
    step = 500
    pages = ['http://dbpedia.org/resource/'+i.strip().replace(' ', '_')
             for i in codecs.open(home+'/data/text-analysis/content_categories/'+keyword+'_pages.txt', encoding='utf-8')]
    chunks = arange(0, len(pages)+step, step)

    for i in xrange(1, len(chunks)):
        temp = [requests.utils.quote(p.encode('utf-8'), safe=':/') for p in pages[chunks[i-1]:chunks[i]]]
        graph = get_subgraph(temp)
        f = codecs.open(home+'/workspace/vichakshana/data/'+keyword+'_'+str(i)+'_subgraph.n3', 'w', encoding='utf-8')
        f.write(graph.decode('utf-8'))
        f.close()