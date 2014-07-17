#!/usr/bin/python
from flup.server.fcgi import WSGIServer
from evaluation.flamenco.flamenco_survey import app

if __name__ == '__main__':
    WSGIServer(app, bindAddress='/tmp/vichakshana-flamenco.sock').run()
