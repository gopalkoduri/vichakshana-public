#!/usr/bin/python
from flup.server.fcgi import WSGIServer
from evaluation.jazz.jazz_survey import app

if __name__ == '__main__':
    WSGIServer(app, bindAddress='/tmp/vichakshana-jazzmusic.sock').run()
