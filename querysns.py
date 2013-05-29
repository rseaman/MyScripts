'''
Created on May 6, 2013

@author: rseaman
'''
import boto
import pdb

sns = boto.connect_sns()

topics = sns.get_all_topics()
#pdb.set_trace()
topic_arn = topics['TopicArn']

print topic_arn
