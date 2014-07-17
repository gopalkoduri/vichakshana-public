# -*- coding: utf-8 -*-

from __future__ import division
from os.path import expanduser
from os import chdir
from numpy import mean
from gensim import corpora, models
from SPARQLWrapper import SPARQLWrapper, JSON
import pickle
import networkx as nx
import numpy as np
import community
from urllib import quote_plus


#TODO: Switch to absolute imports
home = expanduser("~")
chdir(home+'/workspace/wiki_tools')
from wiki_grapher import ochiai_coefficient
import progressbar

chdir(home+'/workspace/vichakshana/vichakshana/')

#NOTE: Use Page class in relation extraction for getting the plain text and cleaning it


def retrieve(query, endpoint='http://devaraya.s.upf.edu/dbpedia-sparql'):
    """
    A generic function to query the SPARQL endpoint and return the results if any.
    Returns [] when there are no results/query fails(in which case it prints the query
    to stdout).
    """
    endpoint = SPARQLWrapper(endpoint)
    endpoint.setQuery(query)
    endpoint.setReturnFormat(JSON)

    try:
        results = endpoint.query().convert()
    except:
        print 'Query did not succeed: ', query
        return []

    if results['results']['bindings']:
        results = results['results']['bindings']
    else:
        #print query
        results = []
    return results


def get_topics(name_index, topic_type='category', pickle_file=None, recompute=True):
    """
    This function returns page:topics dictionary by querying a dbpedia sparql endpoint.
    """
    if not recompute and pickle_file:
        return pickle.load(file(pickle_file))
    elif not recompute and not pickle_file:
        print 'You are asking not to recompute topics, but did not pass any pickle file path'
        return None

    # for k, v in name_index.items():
    #     v = unicode(v)
    #     name_index[unicode(k)] = v.encode('utf-8')

    topics = {}

    if topic_type == 'rdftype':
        key = 'rdftype'
        query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        SELECT ?rdftype
        WHERE {
         <http://dbpedia.org/resource/%s> rdf:type ?rdftype .
        }
        """
    elif topic_type == 'category':
        key = 'category'
        query = """
        SELECT ?category
        WHERE {
         <http://dbpedia.org/resource/%s> <http://purl.org/dc/terms/subject> ?category .
        }
        """
    else:
        print 'topic_type not known'
        return

    p = progressbar.ProgressBar(len(name_index))
    count = 0
    for page_lower, page_cap in name_index.items():
        count += 1
        p.animate(count)

        page_cap = quote_plus(page_cap.encode('utf-8'), safe=':/')
        cur_query = query % page_cap
        results = retrieve(cur_query)

        if not results:
            continue

        page_topics = []
        #print page_cap,
        for topic in results:
            page_topics.append(topic[key]['value'].split('/')[-1])
            #print topic['topic']['value'],
        uniq_topics = set(page_topics)
        topics[page_lower] = uniq_topics
    return topics


def score_topics(topics, page_scores, method='tfidf'):
    """
    For each page, it's pagerank multiplied by the idf score of its topic becomes the
    relevance score of that topic for that page. An average across all pages for each
    topic then becomes the relevance score of that topic for that music.
    """

    topic_scores = {}
    [topics.pop(page) for page in topics.keys() if page not in page_scores.keys()]

    p = progressbar.ProgressBar(len(topics))
    count = 0
    if method == 'tfidf':
        texts = topics.values()
        dictionary = corpora.Dictionary(texts)
        corpus = [dictionary.doc2bow(text) for text in texts]
        tfidf = models.TfidfModel(corpus)

    for page, page_topics in topics.items():
        score = page_scores[page]
        count += 1
        p.animate(count)
        if method == 'basic':
            for topic in page_topics:
                if topic in topic_scores.keys():
                    topic_scores[topic][0].append(score)
                    topic_scores[topic][1].append(page)
                else:
                    topic_scores[topic] = [[score], [page]]
        elif method == 'split':
            n = len(page_topics)
            for topic in page_topics:
                if topic in topic_scores.keys():
                    topic_scores[topic][0].append(score/n)
                    topic_scores[topic][1].append(page)
                else:
                    topic_scores[topic] = [[score/n], [page]]

        elif method == 'tfidf':
            topic_weights = tfidf[dictionary.doc2bow(page_topics)]
            for topic, weight in topic_weights:
                if topic in topic_scores.keys():
                    topic_scores[topic][0].append(score*weight)
                    topic_scores[topic][1].append(page)
                else:
                    topic_scores[topic] = [[score*weight], [page]]

    if method == 'tfidf':
        id2token = {v: k for k, v in dictionary.token2id.items()}
        topic_scores = {id2token[k]: v for k, v in topic_scores.items()}

    for topic, values in topic_scores.items():
        topic_scores[topic][0] = mean(topic_scores[topic][0])

    return topic_scores


def graph_topics(topics):
    """
    A graph with skos:broader heirarchy as edges is returned for a given set of topics.
    """
    query = """
    SELECT ?rel, ?invrel WHERE {{
        {{ <{0}> ?rel <{1}> }}
        UNION
        {{ <{1}> ?invrel <{0}> }}
    }}
    """
    topic_graph = nx.DiGraph()
    n = len(topics)
    p = progressbar.ProgressBar(n*(n+1)/2)
    count = 0

    for i in xrange(len(topics)):
        node_i = topics[i].split('/')[-1]
        for j in xrange(i, len(topics)):
            p.animate(count)
            count += 1
            node_j = topics[j].split('/')[-1]
            relations = retrieve(query.format(topics[i], topics[j]))
            for r in relations:
                if 'rel' in r.keys() and 'broader' in r['rel']['value']:
                    topic_graph.add_edge(node_i, node_j)
                elif 'invrel' in r.keys() and 'broader' in r['invrel']['value']:
                    topic_graph.add_edge(node_j, node_i)
    return topic_graph


def topic_overlap(topic_scores):
    """
    Returns a graph with topics as nodes and the edges whose weights represent the mutual overlap between them.
    """
    topicindex = dict(enumerate(topic_scores.keys()))
    distMatrix = np.matrix([np.zeros(len(topicindex))]*len(topicindex), dtype=float)

    for i in xrange(len(topicindex)):
        for j in xrange(i, len(topicindex)):
            if i == j: continue
            x = topic_scores[topicindex[i]][1]
            y = topic_scores[topicindex[j]][1]
            score = ochiai_coefficient(x, y)
            distMatrix[i, j] = score
            distMatrix[j, i] = score

    sim_graph = nx.DiGraph()
    for index, topic in topicindex.items():
        x = topic
        sorted_neighbors = sorted(list(enumerate(distMatrix[index].tolist()[0])), key=lambda k: k[1], reverse=True)
        neighbor_indices = [n[0] for n in sorted_neighbors[:10] if n[1] > 0.5]

        if len(neighbor_indices) == 0:
            continue
        #print topic, ranked_topics[topic][1]

        for n_index in neighbor_indices:
            y = topicindex[n_index]
            sim_graph.add_edge(x, y, {'weight':float(distMatrix[index, n_index])})
            #print topicindex[n_index], ranked_topics[topicindex[n_index]][1]
        #print '\n', '-'*40, '\n'

    return sim_graph


def defrag_topics(sim_graph, topic_scores, large_topic_thresh=50):
    """
    Given a graph which represents the overlap between topics, and the topic_scores dictionary,
    this function returns the final representation of topics for a given music style.

    The result is of this format:
    topic_information = [{'topic_id1': {'representative_topics': [t1, t4.. tk], 'topic_group': [t1, t2.. tn]
                        'pages': [[p1, p2 ...], 'relevance_score': 0.8},
                        ...
                        {'topic_id2':  .... }]
    """
    topic_information = []
    for topic, values in topic_scores.items():
        if topic not in sim_graph.nodes():
            topic_information.append({'topic_group': [topic], 'representative_topics': [topic],
                                      'pages': values[1], 'relevance_score': values[0]})
    large_topics = []
    partition = community.best_partition(sim_graph.to_undirected())
    categories = {}
    for com in set(partition.values()):
        com_nodes = [nodes for nodes in partition.keys() if partition[nodes] == com]
        categories[com] = com_nodes

    for topics in categories.values():
        page_counts = {topic: len(topic_scores[topic][1]) for topic in topics}
        page_counts = page_counts.items()
        page_counts = sorted(page_counts, key=lambda k: k[1], reverse=True)
        #Skip big topics!
        large_topic = False
        for i in xrange(len(page_counts)):
            if page_counts[i][1] > large_topic_thresh:
                large_topic = True
                break
        if large_topic:
            large_topics.extend([i[0] for i in page_counts])
            continue

        page_counts = [(i[0], i[1]/page_counts[0][1]) for i in page_counts]
        rep_topics = [i[0] for i in page_counts if i[1] >= 0.8]
        topic_group = [i[0] for i in page_counts]
        pages = set()
        for topic in topics:
            pages.update(topic_scores[topic][1])

        relevance_score = np.average([topic_scores[topic][0] for topic in topics])

        topic_information.append({'topic_group': topic_group, 'representative_topics': rep_topics,
                                 'pages': list(pages), 'relevance_score': relevance_score})

    #Don't forget to add the large topics which were skipped earlier
    for topic in large_topics:
        values = topic_scores[topic]
        topic_information.append({'topic_group': [topic], 'representative_topics': [topic],
                                  'pages': values[1], 'relevance_score': values[0]})
    return topic_information