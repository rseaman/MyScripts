'''
Created on May 17, 2013

@author: rseaman
'''
import boto.rds
from pprint import pprint

regions = boto.rds.regions()

for reg in regions:
    rdsconn = boto.rds.RDSConnection(region=reg)
    print '\nConnecting to ' + str(reg.name) + '\n'
    
    RDSInstances = rdsconn.get_all_dbinstances()
    
    for inst in RDSInstances:
        print 'Found Instance: ' + str(inst)
        
    RDSParamGroups = rdsconn.get_all_dbparameter_groups()
    for pg in RDSParamGroups:
        print 'Found DB Parameter Group: ' + str(pg.name)

        RDSParameters = rdsconn.get_all_dbparameters(groupname=pg.name)
        pprint(RDSParameters)