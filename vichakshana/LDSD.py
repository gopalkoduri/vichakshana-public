from __future__ import division
from collections import Counter
from os.path import expanduser
from os import chdir
import pickle

from SPARQLWrapper import SPARQLWrapper, JSON
import numpy as np

home = expanduser('~')
chdir(home+'/workspace/vichakshana/vichakshana/')

#CELERY
from mycelery import app


def query(query_content):
    sparql = SPARQLWrapper("http://devaraya.s.upf.edu/dbpedia-sparql")

    #print query_content
    sparql.setQuery(query_content)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()

    if not results["results"]["bindings"]:
        return None
    else:
        return results["results"]["bindings"]


def get_all_relations(src_page, keyword):
    """
    This function gets all the relations of a given page.
    """
    query_content = """
    SELECT ?relation, ?another_entity
    FROM NAMED {1}
    WHERE
    {{
        GRAPH {1} {{
            {0} ?relation ?another_entity .
        }}
    }}
    """.format('<'+src_page+'>', '<http://dbpedia.org/'+keyword+'>')
    #print query_content
    res = query(query_content)
    if res:
        res = [[r['relation']['value'], r['another_entity']['value']]
               for r in res if r['another_entity']['type'] == 'uri']
        return res
    return []


#CELERY
@app.task
def get_direct_relations(src_page, keyword, pages, out_file):
    """
    From all the relations of all the pages, this function keeps
    only those that exist directly between the pages. Gets rid of
    those relations which point to a uri outside given pages.
    """
    all_relations = get_all_relations(src_page, keyword)

    direct_relations = {}
    for rel in all_relations:
        if rel[1] not in pages:
            continue
        if rel[0] in direct_relations.keys():
            direct_relations[rel[0]].append(rel[1])
        else:
            direct_relations[rel[0]] = [rel[1]]

    pickle.dump(direct_relations, file(out_file, 'w'))


#CELERY
@app.task
def get_indirect_relations(src_page, keyword, out_file):
    indirect_relations = {}

    for direction in ['in', 'out']:
        if direction == 'out':
            query_content = """
            SELECT ?another_entity, ?linked_by_rel, ?an_entity
            FROM NAMED {0}
            WHERE
            {{
                GRAPH {0} {{
                    {1} ?linked_by_rel ?an_entity .
                    ?another_entity ?linked_by_rel ?an_entity .
                }}
            }}
            """.format('<http://dbpedia.org/'+keyword+'>', '<'+src_page+'>')
        elif direction == 'in':
            query_content = """
            SELECT ?another_entity, ?linked_by_rel, ?an_entity
            FROM NAMED {0}
            WHERE
            {{
                GRAPH {0} {{
                    ?an_entity ?linked_by_rel {1} .
                    ?an_entity ?linked_by_rel ?another_entity .
                }}
            }}
            """.format('<http://dbpedia.org/'+keyword+'>', '<'+src_page+'>')
        else:
            print 'Not handled'
            return

        #print query_content
        res = query(query_content)
        rel_data = {}
        if res:
            for r in res:
                if r['an_entity']['type'] != 'uri':
                    continue
                if r['linked_by_rel']['value'] in rel_data.keys():
                    rel_data[r['linked_by_rel']['value']].append(r['another_entity']['value'])
                else:
                    rel_data[r['linked_by_rel']['value']] = [r['another_entity']['value']]

        indirect_relations[direction] = rel_data

    pickle.dump(indirect_relations, file(out_file, 'w'))


def get_direct_similarity(dest_page, direct_relations):
    similarity = 0
    for link_type, linked_resources in direct_relations.items():
        if dest_page in linked_resources:
            similarity += 1/(1+np.log(len(linked_resources)))
    return similarity


def get_indirect_similarity(dest_page, indirect_relations):
    similarity = 0

    for link_type, linked_resources in indirect_relations['in'].items():
        if dest_page in linked_resources:
            similarity += 1/(1+np.log(len(linked_resources)))

    for link_type, linked_resources in indirect_relations['out'].items():
        if dest_page in linked_resources:
            similarity += 1/(1+np.log(len(linked_resources)))

    return similarity


#CELERY
@app.task
def compute_ldsd_matrix(src_page, pages, direct_relation_file, indirect_relation_file, out_file):
    direct_relations = pickle.load(file(direct_relation_file))
    indirect_relations = pickle.load(file(indirect_relation_file))
    distances = []
    for dest_page in pages:
        if src_page == dest_page:
            distances.append((dest_page, 1))
        else:
            direct_similarity = get_direct_similarity(dest_page, direct_relations)
            indirect_similarity = get_indirect_similarity(dest_page, indirect_relations)
            distances.append((dest_page, 1/(1+direct_similarity+indirect_similarity)))

    distances = sorted(distances, key=lambda x: x[1])
    pickle.dump(distances, file(out_file, 'w'))


#Common utility functions

def similar_entities(distance_file, n, distance_threshold):
    distance_data = pickle.load(file(distance_file))
    sim_entities = []
    for i in distance_data:
        if i[1] >= distance_threshold or len(sim_entities) >= n:
            break
        if 'Template' in i[0] or 'List' in i[0]:
            continue
        sim_entities.append(i)
    return sim_entities


def get_common_linktypes(relation_data, n=10):
    res = np.concatenate([relation_data])
    common_linktypes = []
    for i in res:
        for k, v in i.items():
            if v:
                common_linktypes.append(k)
    c = Counter(common_linktypes)
    return c.most_common(n)


if __name__ == '__main__':
    pass