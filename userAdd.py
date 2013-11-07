#!/usr/bin/env python

import Globals
import string
import random
from Products.ZenUtils.ZenScriptBase import ZenScriptBase
from transaction import commit
from sys import argv

#This script takes user email addresses as arguments to the script in the form test@zenoss.com,GroupName OR test@zenoss.com,'Group Name'

dmd = ZenScriptBase(connect=True).dmd

#Generates a random password for the user
def passgen(size=8, chars=string.ascii_uppercase + string.digits):
	return ''.join(random.choice(chars) for x in range(size))

for i in range(1,len(argv)):
	password = passgen()
	
	#Var for referenceable list
	j = argv[i].split(",")
	
	#Var for user's ID. If this is None, we'll add the user and add them to the group after the comma. If the group name has a space, enclose the group name in quotes.
	k = dmd.ZenUsers.getUser(str(j[0]))

	if k is None:
		#Password has been generated, now add the user as a ZenManager.
		if len(j) == 1:
			#If only the email address is entered, make ZenUser and don't add to groups.
			dmd.ZenUsers.manage_addUser(str(j[0]),password,email=str(j[0]))
			#Print the results so we can copy/paste the password to the user.
			print argv[i],password
		elif len(j) == 2:
			if str(j[1]).startswith('Zen') == True:
				#Add to ROLE INSTEAD
				dmd.ZenUsers.manage_addUser(str(j[0]),password,email=str(j[0]),roles=str(j[1]))
			else:
				dmd.ZenUsers.manage_addUser(str(j[0]),password,email=str(j[0]))
				print "Adding user to group..."
				dmd.ZenUsers.manage_addUsersToGroups(str(j[0]),str(j[1]))
		elif len(j) == 3:
			dmd.ZenUsers.manage_addUser(str(j[0]),password,email=str(j[0]),roles=str(j[1]))
			dmd.ZenUsers.manage_addUsersToGroups(str(j[0]),str(j[2]))
		else:
			print "Syntax Error"
			print "Please use the format email@email.com OR email@email.com,ZenManager OR"
			print "email@email.com,GroupName OR email@email.com,ZenManager,GroupName."
			print "Role options are ZenUser, ZenManager, or ZenOperator."
			print "If a group name has a space in it, be sure to enclose it in quotes."
		commit()
	else:
		print "User already exists! Skipping..."


print "Done!"
