from prevail import *

__doc__ = """\
This tests the object type, by creating specific object class, and instanciating
them.
"""

class Person( PersistentObject ):
	PLURAL    = "people"

	@key
	@attribute(String)
	def name( self, name ):
		pass

	@attribute(String)
	def firstName( self, age ):
		pass

	@attribute(Integer)
	def age( self, age ):
		pass
	
	@attribute(Sequence)
	#@readonly
	def incomes( self ):
		pass

	def worksFor( self, company, salary ):
		# We should use a relation instead
		income = self.incomes()
		company.employees().add(self)

class  Company( PersistentObject ):
	PLURAL    = "companies"

	@key
	@attribute(String)
	def name( self, name ):
		pass

	@attribute(Sequence)
	def employees( self ):
		pass

# We create the storage
storage = Storage(reset=True, classes=(Company, Person))

# And populate the storage with data
john = storage.create( Person )
john.firstName("John")
john.name("Difool")
john.age(34)
assert john.firstName() == "John"
assert john.name() == "Difool"
assert john.age() == 34

bigco = storage.create( Company )
bigco.name("Big, Corp.")

assert john.refcount() == 0
john.worksFor(bigco, 10000)
assert john.refcount() == 1
assert bigco.employees().length() == 1
assert bigco.employees().get(0).name() == "Difool"

assert len(Company.ALL) == 1
assert len(Person.ALL)  == 1
assert bigco.refcount() == 0
assert john.refcount()  == 1

storage.close()

# Now that the storage was closed, we re-create it from the existing data
# And we use different mappings for the people and companies inventories

PreviousPeople    = Person.ALL
PreviousCompanies = Company.ALL
Person.ALL        = None
Company.ALL       = None
storage = Storage(classes=(Person, Company))
print storage.dump()

print PreviousPeople
print Person.ALL

assert Person.ALL  == PreviousPeople
assert Company.ALL == PreviousCompanies

# We assert that the categorisations work well
# 
# isa_tags = storage.related(name="isa", object=storage.constant("tag"))
# isa_tags_tags = map(lambda x:x[0], isa_tags)
# print storage.get.tags()
# print storage.get.isa_tags()
# assert isa_tags_tags == storage.get.tags()

print "OK"
