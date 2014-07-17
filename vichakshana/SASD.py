from __future__ import division
from os.path import expanduser, exists
from os import chdir, mkdir
import pickle

import numpy as np
from scipy import sparse
import networkx as nx

home = expanduser('~')
chdir(home+'/workspace/vichakshana/vichakshana/')

#CELERY
from mycelery import app


class SASD():
    def __init__(self, keyword):
        self.keyword = keyword

        self.sasd_data = pickle.load(file(home+'/data/text-analysis/vichakshana/SASD/'+keyword+'.pickle'))
        self.normalize_sasd_data()

        self.cocitation_g = nx.read_graphml(home+'/data/text-analysis/vichakshana/page_graphs/'
                                            + keyword+'_entitylinks_core_cocitation.graphml', node_type=unicode)

        self.fileindex_reverse = pickle.load(file(home+'/data/text-analysis/fileindex/'+keyword+'_fileindex.pickle'))
        self.fileindex = {v: k for k, v in self.fileindex_reverse.items()}
        self.fileindex_sorted = sorted(self.fileindex.items(), key=lambda x: x[1])

    def normalize_sasd_data(self):
        max_score = max([i['relevance_score'] for i in self.sasd_data])
        for i in self.sasd_data:
            i['relevance_score'] /= max_score

    def compute_shortest_paths(self):
        import graph_tool.all as gt

        graph_file = home+'/data/text-analysis/vichakshana/page_graphs/' + self.keyword + '_entitylinks_core.graphml'
        g = gt.load_graph(graph_file, fmt='xml')
        distance_data = gt.shortest_distance(g)

        vertices = list(g.vertices())
        rows = []
        cols = []
        distances = []

        for src_v in vertices:
            for i in xrange(len(vertices)):
                if distance_data[src_v][i] > 100:
                    continue
                rows.append(self.fileindex[unicode(g.vertex_properties['_graphml_vertex_id'][src_v],
                                                   encoding='utf-8')])
                cols.append(self.fileindex[unicode(g.vertex_properties['_graphml_vertex_id'][vertices[i]],
                                                   encoding='utf-8')])
                distances.append(distance_data[src_v][i])

        n = max(self.fileindex.values())+1  # since the indexing starts with 0
        shortest_paths = sparse.coo_matrix((distances, (rows, cols)), shape=(n, n))
        shortest_paths = sparse.csr_matrix(shortest_paths).todense()

        if not exists(home+'/data/text-analysis/vichakshana/page_graphs/'+self.keyword+'_shortest_paths/'):
            mkdir(home+'/data/text-analysis/vichakshana/page_graphs/'+self.keyword+'_shortest_paths/')
        for i in xrange(shortest_paths.shape[0]):
            pickle.dump(shortest_paths[i], file(home+'/data/text-analysis/vichakshana/page_graphs/'
                                                + self.keyword+'_shortest_paths/'+str(i)+'.pickle', 'w'))

    def get_sasd(self, page_a, page_b, shortest_paths):
        """
        There are three parts in this distance:
        1. Corelevance based
        2. Shortest paths: extended version of direct links
        3. Indirect links: cocitation and bibcouling graphs' direct edges

        Each distance varies between 0-1.

        The returned distance is a weighted average of all these distances.
        """

        if page_a != page_b:
            #1. Corelevance
            co_relevance = []
            for group in self.sasd_data:
                if page_a in group['pages'] and page_b in group['pages']:
                    co_relevance.append(group['relevance_score'])

            if len(co_relevance) > 0:
                similarity_corel = len(co_relevance)+np.average(co_relevance)
            else:
                similarity_corel = 0
            distance_corel = 1/(1+similarity_corel)

            #2. Shortest paths
            shortest_path_length = shortest_paths[0, self.fileindex[page_b]]-1
            if shortest_path_length == -1:
                shortest_path_length = np.inf

            similarity_shortest_path = 1/(1+shortest_path_length*shortest_path_length)
            distance_shortest_path = 1-similarity_shortest_path

            #3. Indirect links
            try:
                cocitation_weight = self.cocitation_g[page_a][page_b]['weight']
            except KeyError:
                cocitation_weight = 0
            distance_cocitation = 1-cocitation_weight

            #Finally, the weighted version
            distance = 0.25*distance_shortest_path + 0.25*distance_cocitation + 0.50*distance_corel

            #print co_relevance, distance_corel, distance_shortest_path, distance_cocitation
        else:
            distance = 1

        return distance

    #CELERY
    @app.task
    def get_sasd_celery(self, page_a):
        pages = self.fileindex.keys()
        distances = []
        shortest_paths = pickle.load(file(home+'/data/text-analysis/vichakshana/page_graphs/'
                                          + self.keyword+'_shortest_paths/'+str(self.fileindex[page_a])+'.pickle'))
        for page_b in pages:
            distances.append((self.fileindex[page_b], self.get_sasd(page_a, page_b, shortest_paths)))

        if not exists(home+'/data/text-analysis/vichakshana/SASD/'+self.keyword+'/'):
            mkdir(home+'/data/text-analysis/vichakshana/SASD/'+self.keyword)
        pickle.dump(distances, file(home+'/data/text-analysis/vichakshana/SASD/' +
                                    self.keyword+'/'+str(self.fileindex[page_a])+'.pickle', 'w'))

    def get_sasd_cluster(self, index_a):
        if exists(home+'/data/text-analysis/vichakshana/SASD/' + self.keyword+'/'+str(index_a)+'.pickle'):
            return
        page_a = self.fileindex_reverse[index_a]
        pages = self.fileindex.keys()
        distances = []
        shortest_paths = pickle.load(file(home+'/data/text-analysis/vichakshana/page_graphs/'
                                          + self.keyword+'_shortest_paths/'+str(index_a)+'.pickle'))
        for page_b in pages:
            distances.append((self.fileindex[page_b], self.get_sasd(page_a, page_b, shortest_paths)))

        if not exists(home+'/data/text-analysis/vichakshana/SASD/'+self.keyword+'/'):
            mkdir(home+'/data/text-analysis/vichakshana/SASD/'+self.keyword)
        pickle.dump(distances, file(home+'/data/text-analysis/vichakshana/SASD/' +
                                    self.keyword+'/'+str(self.fileindex[page_a])+'.pickle', 'w'))

    def compute_sasds(self, n_jobs=0):
        submitted_jobs = 0
        for page_a, index_a in self.fileindex_sorted:
            #CELERY
            if exists(home+'/data/text-analysis/vichakshana/SASD/' + self.keyword+'/'+str(index_a)+'.pickle'):
                continue

            self.get_sasd_celery.apply_async((self, page_a,))
            if n_jobs > 0:
                submitted_jobs += 1
                if submitted_jobs >= n_jobs:
                    print index_a
                    break

    def get_related(self, page, n=10, distance_threshold=0.5):
        distance_data = pickle.load(file(home+'/data/text-analysis/vichakshana/SASD/' +
                                    self.keyword+'/'+str(self.fileindex[page])+'.pickle'))
        distance_data = sorted(distance_data, key=lambda x: x[1])
        related_entities = []
        for i in distance_data:
            if i[1] >= distance_threshold:
                break
            if len(related_entities) < n:
                related_entities.append((self.fileindex_reverse[i[0]], i[1]))
        return related_entities
