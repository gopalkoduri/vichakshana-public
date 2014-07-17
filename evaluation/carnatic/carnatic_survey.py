import MySQLdb as sql
from flask import Flask, render_template, request, url_for
app = Flask(__name__)

USER = 'root'
PASS = 'compmusic123'
DB = 'sasd_carnatic_music'


#Functions that are used by web-app, but not exposed to the user

def add_user(user_info):
    """
    This function checks for the email address of the user, and returns the userid.
    If the user is not found, a new user is created and the id is returned.
    """
    conn = sql.connect('localhost', USER, PASS, DB)
    with conn:
        cur = conn.cursor()
        query = """
        SELECT email from Users where email='{0}'
        """.format(user_info['email'])
        cur.execute(query)
        res = cur.fetchall()
        if res:
            #there is another row with same email!
            return False

        #Add new user
        query = """
        INSERT INTO Users VALUES('{0}', '{1}', '{2}', '{3}', '{4}')
        """.format(user_info['email'], user_info['name'], user_info['age'], user_info['place'], user_info['expertise'])
        cur.execute(query)
        return True


# def get_terms(user_info):
#     #TODO: use the userinfo to customize the suggestions
#     conn = sql.connect('localhost', USER, PASS, DB)
#     with conn:
#         #Get the pages and their impressions to date
#         cur = conn.cursor()
#         query = """
#         SELECT query_page, COUNT(DISTINCT(email)) as impressions
#         FROM `Recommenders`
#         GROUP BY query_page
#         ORDER BY impressions DESC
#         """
#         cur.execute(query)
#         page_impressions = dict(cur.fetchall())
#
#         #Get all the pages
#         all_pages = [page.strip() for page in codecs.open('data/all_pages.txt', 'r', 'utf-8').readlines()]
#         selected_pages = []
#         for page in all_pages:
#             if page not in page_impressions.keys() or page_impressions[page] < 3:
#                 selected_pages.append(page)
#         return selected_pages

def get_terms():
    conn = sql.connect('localhost', USER, PASS, DB)
    with conn:
        cur = conn.cursor()
        query = """
        SELECT DISTINCT(`query_page`)
        FROM `Recommendations`
        ORDER BY `type`, `query_page`
        """
        cur.execute(query)
        terms = cur.fetchall()
        return terms


def get_recommendations(term):
    conn = sql.connect('localhost', USER, PASS, DB)
    with conn:
        cur = conn.cursor()
        query = """
        SELECT `recommendations`, `recommender`
        FROM `Recommendations`
        WHERE `query_page`='{0}'
        """.format(term)
        cur.execute(query)
        res = cur.fetchall()
        return res


def get_type(term):
    conn = sql.connect('localhost', USER, PASS, DB)
    with conn:
        cur = conn.cursor()
        query = """
        SELECT DISTINCT(`type`)
        FROM `Recommendations`
        WHERE `query_page`='{0}'
        ORDER BY `type`, `query_page`
        """.format(term)
        cur.execute(query)
        term_type = cur.fetchone()
        return term_type[0]


def rate_recommender(email, term, recommender):
    conn = sql.connect('localhost', USER, PASS, DB)
    with conn:
        cur = conn.cursor()
        query = """
        INSERT INTO `Recommenders`
        VALUES ("{0}", "{1}", "{2}")
        """.format(email, term, recommender)
        cur.execute(query)


def mark_pages(email, query_page, ldsd_pages, sasd_pages):
    conn = sql.connect('localhost', USER, PASS, DB)
    with conn:
        cur = conn.cursor()
        for page in ldsd_pages:
            query = """INSERT INTO `Pages` VALUES ("{0}", "{1}", "{2}", "{3}");""".format(email, query_page, page, 'ldsd')
            cur.execute(query)

        for page in sasd_pages:
            query = """INSERT INTO `Pages` VALUES ("{0}", "{1}", "{2}", "{3}");""".format(email, query_page, page, 'sasd')
            cur.execute(query)

#The following are the functions exposed to the user

@app.route('/')
def start():
    message = ''
    user_info = {'name': '', 'age': '', 'email': '', 'place': '', 'expertise': ''}
    return render_template('index.html', message=message, user_info=user_info)


@app.route('/answer-start', methods=['GET', 'POST'])
def answer_start():
    user_info = {'name': request.form['name'], 'age': request.form['age'],
                 'email': request.form['email'], 'place': request.form['place'],
                 'expertise': request.form['expertise']}
    added = add_user(user_info)

    if added:
        #Start the survey amd loop it until the end.
        terms = [i[0] for i in get_terms()]
        cur_index = 0
        next_index = cur_index+1
        term = terms[cur_index]
        recommendations = get_recommendations(term)
        recommendations = {i[1]: i[0].split('###') for i in recommendations}

        return render_template('answer.html', term=term, recommendations=recommendations,
                               type=get_type(term), next_index=next_index, terms=terms, email=user_info['email'])
    else:
        message = 'Another user had registered his/her responses with that email address. Please try again.'
        return render_template('index.html', message=message, user_info=user_info)


@app.route('/answer-loop', methods=['GET', 'POST'])
def answer_loop():
    #data to continue looping
    terms = request.form.getlist('terms')
    cur_index = int(request.form['next_index'])
    email = request.form['email']

    #data to be recorded to database
    term_type = request.form['type']
    if term_type == 'bad_overlap':
        ldsd_pages = request.form.getlist('ldsd_pages')
        sasd_pages = request.form.getlist('sasd_pages')
        mark_pages(email, terms[cur_index-1], ldsd_pages, sasd_pages)

    try:
        rated_recommender = request.form['rated_recommender']
    except:
        rated_recommender = 'pass'
    rate_recommender(email, terms[cur_index-1], rated_recommender)

    #Break it when it's time
    if cur_index >= len(terms):
        return render_template('thankyou.html')
    next_index = cur_index+1

    #Next one in the loop
    term = terms[cur_index]
    recommendations = get_recommendations(term)
    recommendations = {i[1]: i[0].split('###') for i in recommendations}

    return render_template('answer.html', term=term, recommendations=recommendations,
                           type=get_type(term), next_index=next_index, terms=terms, email=email)


@app.route('/dummy', methods=['GET', 'POST'])
def dummy():
    terms = ['Electronic Tanpura', 'T M Krishna']
    email = 'gopala.koduri@upf.edu'

    term = 'Koteeswara Iyer'
    recommendations = get_recommendations(term)
    recommendations = {i[1]: i[0].split('###') for i in recommendations}

    return render_template('answer.html', term=term, recommendations=recommendations,
                           type='bad_correlated', next_index=1, terms=terms, email=email)


if __name__ == '__main__':
    app.run(debug=True)