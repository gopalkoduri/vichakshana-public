from __future__ import division
from os.path import expanduser
from os import chdir
import pickle
import sys


home = expanduser('~')
chdir(home+'/workspace/vichakshana/vichakshana/')


def generate_shell_script(keyword):
    fileindex = pickle.load(file(home+'/data/text-analysis/fileindex/'+keyword+'_fileindex.pickle'))
    print """
    #!/bin/bash
    #$ -N {2}_SASD
    #$ -t 1-{0}:1
    #$ -cwd
    #$ -q default.q
    source ~/.virtualenv/PhD/bin/activate
    python {1} ${{SGE_TASK_ID}} {2}
    """.format(len(fileindex)-1, __file__, keyword)


def run(page_index, keyword):
    import SASD
    sasd = SASD.SASD(keyword)
    sasd.get_sasd_cluster(page_index)

if __name__ == '__main__':
    page_index = sys.argv[1]
    keyword = sys.argv[2]
    run(int(page_index), keyword)