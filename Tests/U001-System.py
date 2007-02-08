from prevail import *

__doc__ = """\
Sets up a whole persistent system with different types, and illustrates how they
can be manipulated. Here, we will create a simple del.icio.us-like model, with
the following elements:

 - URLs that represent web sites
 - Tags, which can be associated to URLs
 - Entry, which binds a url with a set of tags along with a description

"""
# -----------------------------------------------------------------------------
#
# MODEL
#
# -----------------------------------------------------------------------------

# URL and Tags are persistent string
class URL( PersistentObject ):
	SINGULAR = "url" ; PLURAL = "urls" ; ALL = None

	def init( self, name ):
		self.value(name)

	@attribute(ConstantString)
	def value( self, name ): pass

	def __repr__(self):
		return "URL(%s):%s" % (id(self), self.value())

class Tag( PersistentObject ):
	SINGULAR = "tag" ; PLURAL = "tags" ; ALL = None

	def init( self, name ):
		self.name(name)

	@attribute(ConstantString)
	def name( self, name ): pass

	def __repr__(self):
		return "Tag(%s):'%s'" % (id(self), self.name())
	
	def __eq__(self, a):
		if type(a) in (str,unicode):
			return self.name() == a
		else:
			return id(a) == id(self)

# The entry object has an URL, a description, and can be related to many tags
class Entry( PersistentObject ):
	SINGULAR = "entry" ; PLURAL = "entries" ; ALL = None

	def init( self, url=None, description=None, tags=() ):
		if url: self.url(url)
		if description: self.description(description)
		for tag in tags: self.taggedBy(tag)

	@attribute(URL)
	def url( self, url ): pass

	@attribute(String)
	def description( self, text ): pass

	def tags( self, *tags ):
		for t in tags:
			if type(t) in (tuple, list): self.tags(*t)
			else: self.taggedBy(t)

	def taggedBy( self, tag ):
		self.relate("tag", tag)

	def untag( self, tag ):
		self.unrelate("tag", tag)

	def __repr__(self):
		return "Entry(%s):%s,%s" % (id(self), self.url(),
		self.description())

# -----------------------------------------------------------------------------
#
# STORAGE
#
# -----------------------------------------------------------------------------

# We create the storage (we reset it each time)
storage = Storage(reset=True, classes=(URL, Tag, Entry))

# We ensure that the type registration was made properly
assert storage.classForName("url") == storage.classForName("urls") == storage.classForName("URLs") == URL
assert storage.classForName("tag") == storage.classForName("tags") == storage.classForName("Tags") == Tag
assert storage.classForName("entry") == storage.classForName("entries") == storage.classForName("Entries") == Entry

# -----------------------------------------------------------------------------
#
# DATA
#
# -----------------------------------------------------------------------------

# Now we can populate the data
# We start by adding tags
python        = storage.new.tag("Python")
programming   = storage.new.tag("Programming")
documentation = storage.new.tag("Documentation")
reference     = storage.new.tag("Reference")
articles      = storage.new.tag("Articles")
web           = storage.new.tag("Web")

assert python.name()        == "Python"
assert programming.name()   == "Programming"
assert documentation.name() == "Documentation"
assert reference.name()     == "Reference"
assert articles.name()      == "Articles"
assert web.name()           == "Web"

# And now we can add entries
entries      = (
	storage.new.entry(
		url="http://www.python.org", description="Python website",
		tags = (python, web, programming))
	,
	storage.new.entry(
		url="http://effbot.org/", description="Fredrik Lundh's effbot.org",
		tags = (python, programming, articles))
	,
	storage.new.entry(
		url="http://www.htmlhelp.com/", description="HTML help website",
		tags = (web, programming, reference))
)

# -----------------------------------------------------------------------------
#
# And now we can do some queries
#
# -----------------------------------------------------------------------------

# We expect to have three entries
assert len(storage.get.entries) == 3, str(storage.get.entries)
assert len(storage.get.tags)    == 6

# We ensure that the tags are the one we actually inserted
a = storage.get.tag(lambda t:t=="Python")[0]
b = python

assert storage.get.tag(lambda t:t=="Python")[0]      == python
assert storage.get.tag(lambda t:t=="Programming")[0] == programming
objects = map(lambda x:x[0], storage.related())

# And we can now query by relation
# Here, we have 3 entries related to programming
assert len(storage.related(object=programming))         == 3
# Here, we have 2 entries related to python and programming 
assert len(storage.related(objects=(python, programming))) == 2
# Here, we have 9 relations named "tags" (3 tag per entry, 3 entries)
assert len(storage.related(name="tags")) == 9
# Here, we get the relations that the first entry has (which are three tags)
assert len(storage.related(subject=entries[0])) == 3

print "OK"

# EOF
