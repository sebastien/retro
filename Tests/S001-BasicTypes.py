import prevail as Prevail

__doc__ = """\
This tests the basic datatypes of Prevail: Integers, Floats and Strings.
"""

storage = Prevail.Storage(reset=True)

# Some Python values can be stored
assert storage.isStorable(1)
assert storage.isStorable(1.1)
assert storage.isStorable("hello")

# But they are not persisted (yet)
assert storage.isPersisted(1)
assert storage.isPersisted(1.1)
assert not storage.isPersisted("hello")

# We create persisted values from python values
p_int    = storage.create(value=1)
p_float  = storage.create(value=1.1)
p_string = storage.create(value="hello")

# Persisted values content are equal to their original Python values
assert p_int   == 1
assert p_float == 1.1
assert p_string.value() == "hello", repr(p_string)

# Persisted values are storable
assert storage.isStorable(p_int)
assert storage.isStorable(p_float)
assert storage.isStorable(p_string)

# Persisted values are persisted
assert storage.isPersisted(p_int)
assert storage.isPersisted(p_float)
assert storage.isPersisted(p_string)

# Creation of persisted values returns the same persisted values
assert storage.create(value=p_int)    == p_int
assert storage.create(value=p_float)  == p_float
assert storage.create(value=p_string) == p_string

# Now we go through store/restore cycles
o_int = 1
p_int = storage.create(value=o_int)
del p_int
p_int = storage.restore(Prevail.Integer, o_int)
assert p_int == o_int

# We test the floats
o_float = 1.1
p_float = storage.create(value=o_float)
del p_float
p_float = storage.restore(Prevail.Float,o_float)
assert p_float == o_float

# And now the strings
o_string = "Hello, World !"
p_string = storage.create(value=o_string)
p_id     = storage.id(p_string)
del p_string
p_string = storage.restore(Prevail.String, p_id)
assert p_string.value() == o_string, repr(p_string.value())

# Now we mutate the string
o_string2 = "Pouet pouet !"
p_string.set(o_string2)
del p_string
p_string = storage.restore(Prevail.String, p_id)
assert p_string.value() != o_string
assert p_string.value() == o_string2

# We test the immutable strings
i_string  = "I am immutable"
pi_string1 = storage.create(type=Prevail.ConstantString, value=i_string)
pi_string2 = storage.create(type=Prevail.ConstantString, value=i_string)
assert pi_string1.value() == pi_string2.value()
assert pi_string1.id()  == pi_string2.id()
del pi_string1
pi_string1 = storage.restore(Prevail.ConstantString, pi_string2.id())
assert pi_string1.value() == pi_string2.value()
assert pi_string1.id()  == pi_string2.id()
print storage.dump()

print "OK"

# EOF
