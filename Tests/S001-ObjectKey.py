from prevail import *

class User( PersistentObject ):

	def init( self, name ):
		self.name(name)

	@key
	@attribute(String)
	def name( self, name ):
		pass

storage   = Storage(reset=True, classes=(User,))
alice     = storage.new.user("alice")
assert alice == storage.get.user("alice")

print "OK"

