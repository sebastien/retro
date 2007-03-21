import prevail as Prevail

__doc__ = """\
This tests the composite datatypes of Prevail: Sequence and Objects.
"""

storage = Prevail.Storage(reset=True)

# Creation of persisted values returns the same persisted values
sequence = storage.create(type=Prevail.Sequence)
assert sequence != None
assert sequence.length() == 0
p_1 = sequence.add(10)
assert sequence.length() == 1
p_2 = sequence.add(20)
assert sequence.length() == 2
p_3 = sequence.add(30)
assert sequence.length() == 3

# We ensure that the values are correct
assert sequence.get(0) == p_1
assert sequence.get(1) == p_2
assert sequence.get(2) == p_3

# We remove values
sequence.remove(1)
assert sequence.length() == 2
assert sequence.get(0) == p_1
assert sequence.get(1) == p_3

# Until the sequence is empty
sequence.remove(1)
assert sequence.length() == 1
assert sequence.get(0) == p_1

# And we ensure it
sequence.remove(0)
assert sequence.length() == 0

# Now we popualte with different data
sequence.add(1, 0.1, "Pouet", sequence)
storage.dump()
p_id = storage.id(sequence)
del sequence

# We restore the sequence
sequence = storage.restore(Prevail.Sequence, p_id)
assert sequence.get(0) == 1, sequence.get(0)
assert sequence.get(1) == 0.1
assert sequence.get(2).value() == "Pouet"
assert sequence.get(3).id() == sequence.id()

class CustomObject(Prevail.PersistentObject):
	pass

storage.registerClass(CustomObject, "customobject")
p_object = storage.create(CustomObject)
p_object.slot("one",   1)
p_object.slot("two",   1.123)
p_object.slot("two",   4.123)
p_object.slot("three", sequence.get(2))
p_object.slot("three", "POUETPOUET")

assert p_object.slot("one") == 1
assert p_object.slot("two") == 4.123, p_object.slot("two")
assert p_object.slot("three") == "POUETPOUET", p_object.slot("three")

print storage.dump()

print "OK"
