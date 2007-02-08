from prevail.core import *

class Note(PersistentObject):

	@attribute(String)
	def text( self, text=None ):
		pass

class Link(PersistentObject):

	@attribute(String)
	def url( self, text=None ):
		pass

class Paste(PersistentObject):

	@attribute(Sequence)
	def content( self ):
		pass

# We create the storage
storage = Storage()
# And register our custom classes
storage.register(Note,  "note", "notes")
storage.register(Link,  "link", "links")
storage.register(Paste, "paste", "pastes")

import time
count = 0
for i in range(1000):
	t = time.time()
	for i in range(1000):
		p = storage.create(Paste)
		count += 1
		for k in range(5):
			n = storage.create(Note)
			n.text("Some note text")
			p.content().add(n)
			count += 1
		for k in range(5):
			l = storage.create(Link)
			l.url("http://www.python.org")
			p.content().add(l)
			count += 1
	storage._commit()
	t = time.time() - t
	size = os.popen("du -ks world.db").read().split("\n")[0].split()[0]
	print count, ";", t, ";", size
	


