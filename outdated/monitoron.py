import boto
import sys
from boto.ec2.connection import EC2Connection
import boto.ec2.cloudwatch
from pprint import pprint

regions = boto.ec2.regions()
print regions

cw = boto.ec2.cloudwatch.connect_to_region('us-east-1')
print cw
sns = boto.connect_sns()
print sns

metrics = cw.list_metrics(metric_name='StatusCheckFailed')
pprint(metrics)

#for m in metrics:	
#	print m.name, m.dimensions

m = metrics[2]
print m.dimensions

#alarm = boto.ec2.cloudwatch.MetricAlarm(name='test', namespace='AWS/EC2', metric='StatusCheckFailed', statistic='Maximum', comparison='>=', threshold='1', period='300', evaluation_periods='2', dimensions=m.dimensions)
#m.create_alarm(alarm)


topics = sns.get_all_topics()

#pprint(topics)



for reg in regions:

		conn = boto.ec2.connect_to_region(reg.name)
		filters = {'instance-state-name':'running'}

		instances = conn.get_all_instances(filters=filters)

		for resv in instances:

			for inst in resv.instances:
				
				metrics = cw.list_metrics(metric_name='StatusCheckFailed')
				
				for m in metrics:
					if 'InstanceId' in m.dimensions:
					
						if str(m.dimensions['InstanceId'][0]) == str(inst.id):
							pprint('Found a match for ' + inst.id)
							#pprint()
					
						#print conn.monitor_instance(inst.id)
							
							for t in topics['ListTopicsResponse']['ListTopicsResult']['Topics']:
								#pprint(t['TopicArn'])
								#print type(t['TopicArn'])
								if 'StatusCheck' in t['TopicArn']:
									#pprint(t['TopicArn'])
									#pprint(inst.tags.get('Name'))
									m.create_alarm(name='awsec2-' + inst.tags.get('Name') + '-High-Status-Check-Failed-Any', statistic='Maximum', comparison='>=', threshold='1', period='300', evaluation_periods='2', alarm_actions=t['TopicArn'], dimensions=m.dimensions)
									print 'Creating alarm for instance: ' + inst.tags.get('Name'), inst.id
