from os.path import expanduser
from os import chdir

import MySQLdb as sql
import pickle


home = expanduser('~')
chdir(home+'/workspace/vichakshana/vichakshana/')
import SASD
import LDSD
reload(SASD)
reload(LDSD)

USER = 'root'
PASS = 'compmusic123'


def create_tables(database):
    """
    NOTE: Don't run this function. Copy the contents and run it on phpmyadmin.
    Somehow the primary keys and foreign key references aren't working with MySQLdb.
    """
    conn = sql.connect('localhost', USER, PASS, database)
    with conn:
        cur = conn.cursor()

        #Users table
        #Table for pages picked as especially relevant to the query page (in each recommended group)
        #Table for marking recommender choices
        #Table with recommendation data
        if database == 'sasd_carnatic_music' or database == 'sasd_hindustani_music' or database == 'sasd_flamenco':
            query = """
            CREATE TABLE Users (
            email VARCHAR(50) PRIMARY KEY,
            name VARCHAR(50),
            age INT,
            place VARCHAR(50),
            expertise VARCHAR(100));
            """
            cur.execute(query)
            cur.close()

            cur = conn.cursor()
            query = """
            CREATE TABLE Pages (
            email VARCHAR(50) NOT NULL,
            query_page VARCHAR(50) NOT NULL,
            recommended_page VARCHAR(50) NOT NULL,
            recommender VARCHAR(50) NOT NULL,
            FOREIGN KEY (email)
                REFERENCES Users(email)
                ON DELETE CASCADE
                );
            """
            cur.execute(query)
            cur.close()

            cur = conn.cursor()
            query = """
            CREATE TABLE Recommenders (
            email VARCHAR(50) NOT NULL,
            query_page VARCHAR(50) NOT NULL,
            recommender VARCHAR(50) NOT NULL,
            FOREIGN KEY (email)
                REFERENCES Users(email)
                ON DELETE CASCADE
                );
            """
            cur.execute(query)
            cur.close()

            cur = conn.cursor()
            query = """
            CREATE TABLE Recommendations (
            query_page VARCHAR(50) NOT NULL,
            type VARCHAR(20) NOT NULL,
            recommender VARCHAR(50) NOT NULL,
            recommendations TEXT NOT NULL);
            """
            cur.execute(query)
            cur.close()

        elif database == 'sasd_jazz_music' or database == 'sasd_baroque_music':
            query = """
            CREATE TABLE Users (
            email VARCHAR(50) PRIMARY KEY,
            name VARCHAR(50),
            age INT,
            expertise VARCHAR(100));
            """
            cur.execute(query)
            cur.close()

            cur = conn.cursor()
            query = """
            CREATE TABLE Pages (
            email VARCHAR(50) NOT NULL,
            query_page VARCHAR(50) NOT NULL,
            recommended_page VARCHAR(50) NOT NULL,
            recommender VARCHAR(50) NOT NULL,
            FOREIGN KEY (email)
                REFERENCES Users(email)
                ON DELETE CASCADE
                );
            """
            cur.execute(query)
            cur.close()

            cur = conn.cursor()
            query = """
            CREATE TABLE Recommenders (
            email VARCHAR(50) NOT NULL,
            query_page VARCHAR(50) NOT NULL,
            recommender VARCHAR(50) NOT NULL,
            FOREIGN KEY (email)
                REFERENCES Users(email)
                ON DELETE CASCADE
                );
            """
            cur.execute(query)
            cur.close()

            cur = conn.cursor()
            query = """
            CREATE TABLE Recommendations (
            query_page VARCHAR(50) NOT NULL,
            type VARCHAR(20) NOT NULL,
            recommender VARCHAR(50) NOT NULL,
            recommendations TEXT NOT NULL);
            """
            cur.execute(query)
            cur.close()
    return


def put_pages(keyword, fileindex, n, d):
    data = pickle.load(file(home+'/data/text-analysis/vichakshana/evaluation/selected_pages/'+keyword+'.pickle'))
    sasd = SASD.SASD(keyword)
    conn = sql.connect('localhost',  USER, PASS, 'sasd_'+keyword)

    #bad_correlations
    for page in data['bad_correlated']:
        sasd_res = [i[0] for i in sasd.get_related(page, n, d)]

        ldsd_dist_file = home+'/data/text-analysis/vichakshana/LDSD/'\
                         + keyword+'/distances/'+str(fileindex[page])+'.pickle'
        ldsd_res = [i[0].split('/')[-1].replace('_', ' ').lower()
                    for i in LDSD.similar_entities(ldsd_dist_file, n, d)]

        common = set(sasd_res).intersection(ldsd_res)
        sasd_ranks = [(i.title(), sasd_res.index(i)) for i in common]
        ldsd_ranks = [(i.title(), ldsd_res.index(i)) for i in common]

        sasd_ranks = sorted(sasd_ranks, key=lambda x: x[1])
        ldsd_ranks = sorted(ldsd_ranks, key=lambda x: x[1])

        with conn:
            cur = conn.cursor()
            query = """
            INSERT INTO `Recommendations` VALUES ('{0}', '{1}', '{2}', '{3}');
            """.format(page.title().encode('utf-8'), 'bad_correlated', 'sasd', '###'.join([i[0].encode('utf-8') for i in sasd_ranks]))
            cur.execute(query)

            query = """
            INSERT INTO `Recommendations` VALUES ('{0}', '{1}', '{2}', '{3}');
            """.format(page.title().encode('utf-8'), 'bad_correlated', 'ldsd', '###'.join([i[0].encode('utf-8') for i in ldsd_ranks]))
            cur.execute(query)

    #bad overlaps
    for page in data['bad_overlap']:
        sasd_res = [i[0].title().encode('utf-8') for i in sasd.get_related(page, n, d)]

        ldsd_dist_file = home+'/data/text-analysis/vichakshana/LDSD/'\
                         + keyword+'/distances/'+str(fileindex[page])+'.pickle'
        ldsd_res = [i[0].split('/')[-1].replace('_', ' ').title().encode('utf-8')
                    for i in LDSD.similar_entities(ldsd_dist_file, n, d)]

        with conn:
            cur = conn.cursor()
            query = """
            INSERT INTO `Recommendations` VALUES ('{0}', '{1}', '{2}', '{3}');
            """.format(page.title().encode('utf-8'), 'bad_overlap', 'sasd', '###'.join(sasd_res))
            cur.execute(query)

            query = """
            INSERT INTO `Recommendations` VALUES ('{0}', '{1}', '{2}', '{3}');
            """.format(page.title().encode('utf-8'), 'bad_overlap', 'ldsd', '###'.join(ldsd_res))
            cur.execute(query)
