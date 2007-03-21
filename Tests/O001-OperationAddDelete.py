from prevail.core import *

class User( PersistentObject ):
	ALL       = []

	def init( self, name ):
		self.name(name)

	@attribute(String)
	def name( self, name ):
		pass


storage = Storage(reset=True, classes=(User,))
alice = storage.new.user("alice")
bob   = storage.new.user("bob")
storage.commit()
assert len(storage.get.users) == 2
assert storage.get.users[0]  == alice 
assert storage.get.users[1]  == bob 
assert storage.get.users[-1] == bob 
bob.delete()
assert len(storage.get.users) == 1
assert storage.get.users[0]  == alice 
assert storage.get.users[-1] == alice
storage.close()

# We restart the storage
User.ALL = None
storage   = Storage(classes=(User,))
assert len(storage.get.users) == 1
alice = storage.get.users[0]
assert alice.name() == "alice"
assert storage.get.users[0]  == alice 
assert storage.get.users[-1] == alice
alice.delete()
storage.close()


# We restart the storage again
User.ALL = None
storage   = Storage(classes=(User,))
assert len(storage.get.users) == 0

print "OK"
