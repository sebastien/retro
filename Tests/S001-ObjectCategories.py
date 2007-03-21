from prevail import *
from prevail.core import PersistentValueError

class Person( PersistentObject ):
	PLURAL = "people"

	def init( self, name ):
		self.name(name)

	@key
	@attribute(String)
	def name( self, name ):
		pass

# Creates the storage and objects
storage   = Storage(reset=True, classes=(Person,))
alice     = storage.new.person("alice")
bob       = storage.new.person("bob")
oscar     = storage.new.person("oscar")

# Creates collections and assign objects to them
storage.createCollections("hacker", "user")
alice.setisa("user")
bob.setisa("user")
oscar.setisa("hacker")

# We cannot assign an object a collection twice
try:
	alice.setisa("user")
	error = False
except PersistentValueError, e:
	error = True
assert error

assert alice in storage.get.users
assert bob in storage.get.users
assert oscar not in storage.get.users

assert alice not in storage.get.hackers
assert bob not in storage.get.hackers
assert oscar in storage.get.hackers

# Close the storage and creates a new one
storage.close()
print "Closing and re-opening the database..."
storage   = Storage(reset=False, classes=(Person,), collections=('user', 'hacker'))
alice     = storage.get.person("alice")
bob       = storage.get.person("bob")
oscar     = storage.get.person("oscar")

assert alice in storage.get.users
assert bob in storage.get.users
assert oscar not in storage.get.users

assert alice not in storage.get.hackers
assert bob not in storage.get.hackers
assert oscar in storage.get.hackers

print "OK"

