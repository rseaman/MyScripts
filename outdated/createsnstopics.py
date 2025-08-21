import boto.sns
from pprint import pprint

regions = boto.sns.regions()


for reg in regions:
    pprint(reg.name)
    snsconn = boto.sns.connect_to_region(reg.name)
    topics = snsconn.get_all_topics()
    #pprint(topics['ListTopicsResponse']['ListTopicsResult']['Topics'])
    
    for t in topics['ListTopicsResponse']['ListTopicsResult']['Topics']:
        if 'StatusCheck' in t['TopicArn']:
            pprint(t['TopicArn'])
            print "This is a StatusCheck topic!"
            
            snsconn.subscribe(topic=t['TopicArn'],protocol='email',endpoint='zenoss@zenoss.pagerduty.com')
            #snsconn.create_topic('StatusCheck')