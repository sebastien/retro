import os, sys
from prevail import *

__doc__ = """\
This tests how the database recovers from errors (when something crashes)
"""

def first_run():
	# We create the storage
	storage     = Storage(reset=True)
	hello_world = storage.create( String, "Hello World" )
	pouet_pouet = storage.create( String, "Pouet pouet" )
	number      = storage.create( Float, 1.14)
	raise Exception("Here is a crash!")

def second_run():
	storage     = Storage()
	hello_world = storage.create( String, "Second" )
	pouet_pouet = storage.create( String, "Run" )
	number      = storage.create( Float, 3.14)
	pass

if __name__ == "__main__":
	if len(sys.argv)>1:
		if sys.argv[1].lower() == "first":
			first_run()
		else:
			second_run()
	else:
		print "STEP 1: Database creation, and crash"
		os.system("python %s first" % (__file__))
		print "\nSTEP 2: Database recuperation after crash"
		os.system("python %s second" % (__file__))
		print "\nSTEP 3: Reopening the DB and dump"
		storage = Storage()
		print storage.dump()
		print "OK"
