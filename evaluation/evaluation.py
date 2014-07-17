from __future__ import division
from os.path import expanduser, exists
import numpy as np
import pickle
from scipy.stats import kendalltau
import networkx as nx
import random

from mycelery import app

home = expanduser('~')
import sys
sys.path.append(home+'/workspace/vichakshana/vichakshana/')

import progressbar
import SASD
import LDSD
reload(SASD)
reload(LDSD)


def choose_evalset_by_topic(topic_information, pageranks, n_topics=10, n_pages=2):
    """
    Use this function before the survey to pick the pages/terms using something
    like a quartile rule. From each topic, handpick pages and start the
    survey with those.

    n_pages can be either 1, 2 or 3
    """
    total_topics = len(topic_information)
    selected_topics = np.linspace(0, total_topics-2, n_topics)
    selected_topics = selected_topics.astype(int)
    selected_pages = []
    for index in selected_topics:
        pages = [(page, pageranks[page]) for page in topic_information[index]['pages']]
        pages = sorted(pages, key=lambda x: x[1])
        if n_pages == 1:
            selected_pages.append(pages[-1][0])
        elif n_pages == 2:
            selected_pages.append(pages[-1][0])
            selected_pages.append(pages[0][0])
        elif n_pages == 3:
            if len(pages) > 4:
                selected_pages.append(pages[-1][0])
                selected_pages.append(pages[0][0])
                mid_index = int(len(pages)/2.0)
                selected_pages.append(pages[mid_index][0])
            elif len(pages) == 4:
                selected_pages.append(pages[-1][0])
                selected_pages.append(pages[-2][0])
                selected_pages.append(pages[0][0])
            else:
                selected_pages.extend([i[0] for i in pages])
        else:
            print 'Not handled'
            return
    return list(np.unique(selected_pages))


@app.task
def compute_overlap(keyword, fileindex, n_pages=10, distance_threshold=0.75, show_progress=True):
    sasd = SASD.SASD(keyword)
    pages = fileindex.keys()
    overlaps = []
    sasd_empty = []
    ldsd_empty = []
    if show_progress:
        p = progressbar.ProgressBar(len(pages))
        count = 0
    for page in pages:
        page = page.split('/')[-1].replace('_', ' ').lower()

        try:
            sasd_res = [i[0] for i in sasd.get_related(page, n_pages, distance_threshold)]
            if len(sasd_res) == 0:
                sasd_empty.append(page)
        except:
            sasd_empty.append(page)
            continue

        try:
            ldsd_dist_file = home+'/data/text-analysis/vichakshana/LDSD/'\
                            + keyword+'/distances/'+str(fileindex[page])+'.pickle'
            ldsd_res = [i[0].split('/')[-1].replace('_', ' ').lower()
                        for i in LDSD.similar_entities(ldsd_dist_file, n_pages, distance_threshold)]
            if len(ldsd_res) == 0:
                ldsd_empty.append(page)
        except:
            ldsd_empty.append(page)
            continue

        try:
            overlaps.append((page, len(set(ldsd_res).intersection(sasd_res))/max([len(ldsd_res), len(sasd_res)])))
        except ZeroDivisionError:
            continue
        if show_progress:
            count += 1
            p.animate(count)

    overlap_information = {'overlaps': overlaps, 'sasd_empty': sasd_empty, 'ldsd_empty': ldsd_empty}
    pickle.dump(overlap_information, file(home+'/data/text-analysis/vichakshana/evaluation/overlap_'+keyword+'_'
                                          + str(n_pages)+'_'+str(distance_threshold)+'.pickle', 'w'))


def analyze_overlaps(keyword, sizes, thresholds):
    all_results = {}
    for n_pages in sizes:
        mean_overlaps = []
        std_overlaps = []
        sasd_empty = []
        ldsd_empty = []
        both_empty = []

        for distance_threshold in thresholds:
            f = home+'/data/text-analysis/vichakshana/evaluation/overlap_'\
                + keyword+'_'+str(n_pages)+'_'+str(distance_threshold)+'.pickle'
            data = pickle.load(file(f))
            overlaps = [i[1] for i in data['overlaps']]
            mean_overlaps.append(np.average(overlaps))
            std_overlaps.append(np.std(overlaps))
            sasd_empty.append(len(data['sasd_empty']))
            ldsd_empty.append(len(data['ldsd_empty']))
            both_empty.append(len(set(data['sasd_empty']).intersection(data['ldsd_empty'])))

        all_results[n_pages] = {'mean_overlaps': mean_overlaps, 'std_overlaps': std_overlaps,
                                'sasd_empty': sasd_empty, 'ldsd_empty': ldsd_empty, 'both_empty': both_empty}
    return all_results


def compute_rank_correlation(keyword, fileindex, n=10, d=0.75, good_overlap=0.3):
    if exists(home + '/data/text-analysis/vichakshana/evaluation/rank_correlation/' +
              keyword+'_'+str(n)+'_'+str(d)+'.pickle'):
        return pickle.load(file(home + '/data/text-analysis/vichakshana/evaluation/rank_correlation/' +
                           keyword+'_'+str(n)+'_'+str(d)+'.pickle'))
    overlap_data = pickle.load(file(home+'/data/text-analysis/vichakshana/evaluation/overlap_'
                                    + keyword+'_'+str(n)+'_'+str(d)+'.pickle'))
    sasd = SASD.SASD(keyword)

    #Divide the whole set of pages into pages with good and bad overlap
    good_pages = []
    bad_pages = []
    empty_pages = set(overlap_data['sasd_empty']).union(overlap_data['ldsd_empty'])

    for i in overlap_data['overlaps']:
        if i[0] in empty_pages:
            continue
        if i[1] >= good_overlap:
            good_pages.append(i[0])
        else:
            bad_pages.append(i)

    #For pages with good overlap, compute rank correlation
    rank_correlations = {}

    progress = progressbar.ProgressBar(len(good_pages))
    count = 0
    for page in good_pages:
        count += 1
        progress.animate(count)
        sasd_res = [i[0] for i in sasd.get_related(page, n, d)]
        try:
            ldsd_dist_file = home+'/data/text-analysis/vichakshana/LDSD/'\
                            + keyword+'/distances/'+str(fileindex[page])+'.pickle'
            ldsd_res = [i[0].split('/')[-1].replace('_', ' ').lower()
                        for i in LDSD.similar_entities(ldsd_dist_file, n, d)]
        except KeyError:
            continue
        common = set(sasd_res).intersection(ldsd_res)
        a = [sasd_res.index(i) for i in common]
        b = [ldsd_res.index(i) for i in common]
        a = np.array(a)-min(a)
        b = np.array(b)-min(b)

        tau = kendalltau(a, b)
        if type(tau) is int:
            tau = (tau, 0)
        rank_correlations[page] = tau
    return {'rank_correlations': rank_correlations, 'bad_pages': bad_pages}


def choose_evalset_by_overlap(keyword, fileindex, n=10, d=0.75, good_overlap=0.3, num_required=20, seed=1):
    res = compute_rank_correlation(keyword, fileindex, n, d, good_overlap)
    g = nx.read_graphml(home+'/data/text-analysis/vichakshana/page_graphs/'+keyword+'_entitylinks_core.graphml',
                        node_type=unicode)
    pageranks = nx.pagerank(g, weight='weight')
    mean_pagerank = np.mean(pageranks.values())

    #Good overlap, bad correlation
    corel_map = [(page, val) for page, val in res['rank_correlations'].items() if page in g.nodes()]
    corel_map = sorted(corel_map, key=lambda x: x[1])
    halfway = int(len(corel_map)/2)

    popular_pages = [i[0] for i in corel_map[:halfway] if pageranks[i[0]] > mean_pagerank]
    other_pages = [i[0] for i in corel_map[:halfway] if pageranks[i[0]] <= mean_pagerank]

    random.seed(seed)
    random.shuffle(popular_pages)
    random.shuffle(other_pages)

    #quarter = int(num_required/4)
    #bad_correlated = popular_pages[:quarter]+other_pages[:quarter]
    half = int(num_required/2)
    bad_correlated = popular_pages[:half]

    #Bad overlap
    bad_pages = [page for page, val in res['bad_pages'] if page in g.nodes()]

    popular_pages = [i for i in bad_pages if pageranks[i] > mean_pagerank]
    other_pages = [i for i in bad_pages if pageranks[i] <= mean_pagerank]

    random.seed(seed)
    random.shuffle(popular_pages)
    random.shuffle(other_pages)

    #bad_overlap = popular_pages[:quarter]+other_pages[:quarter]
    bad_overlap = popular_pages[:half]

    return {'bad_correlated': bad_correlated, 'bad_overlap': bad_overlap}
