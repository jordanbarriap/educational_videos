from gensim.test.utils import datapath
from gensim.models.word2vec import Text8Corpus
from gensim.models.phrases import Phrases, Phraser

import csv
import re

line = 0
with open('./data/section_wise_vocab_no_filter.csv') as file:
    for row in csv.reader(file):
        section_name = row[1]
        f = open('./data/iir-concepts-per-section/'+section_name+'.txt', 'w+')
        str_concepts = row[2]
        str_concepts = re.sub('[{\'}]', '', str_concepts)
        concept_list = str_concepts.split(',')
        for str_concept in concept_list:
            concept = str_concept.strip()
            f.write(concept)
        line = line + 1
        f.close()


