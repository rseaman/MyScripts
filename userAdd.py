import Globals
import string
import random
from Products.ZenUtils.ZenScriptBase import ZenScriptBase
from transaction import commit
from sys import argv

#This script takes user email addresses as arguments to the script.

dmd = ZenScriptBase(connect=True).dmd

#Generates a random password for the user
def passgen(size=8, chars=string.ascii_uppercase + string.digits):
	return ''.join(random.choice(chars) for x in range(size))

for i in range(1,len(argv)):
	password = passgen()
	#Password has been generated, now add the user as a ZenManager.
	dmd.ZenUsers.manage_addUser(argv[i],password,email=argv[i],roles={"ZenManager"})
	#Print the results so we can copy/paste the password to the user.
	print argv[i],password
	commit()

print "Done!"
