#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet
# -----------------------------------------------------------------------------
# Project   : Accounts
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ivy.fr>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 31-Jul-2006
# Last mod  : 30-Oct-2006
# -----------------------------------------------------------------------------

from railways import *
import re
try:
	from prevail     import *
	from prevail.web import expose
except ImportError, e:
	print "Prevail is required by this example."
	print "Download Prevail from <http://www.ivy.fr/prevail>"
	raise e

# ------------------------------------------------------------------------------
#
# DOMAIN OBJECTS
#
# ------------------------------------------------------------------------------

class User(PersistentObject):
	"""This uses the Prevail persistence layer to define a persistent object
	that will be made accessible to Railways through a PrevailedWeb
	component."""

	def init( self, login, password ):
		self.login(login)
		self.password(password)

	@key
	@attribute(String)
	def login(self, login):
		"""This is the login of the user. It is also its key, so users can be
		identifierd by their login (which is then unique)."""
		user = storage.get.users(login)

	@classmethod
	def loginValidator( self, login ):
		"""Validator for the login field."""
		if not re.compile("^[\w]+$").match(login):
			raise ValidationError("Invalid user name")

	@attribute(String)
	def password(self, password):
		"""This is the user password. The body of this method contains a
		validator that works only when the password has a length greater than
		10."""
		if len(password) < 10:
			raise ValidationError("Password too short")

	# EXPOSED TAKES A LIST OF PARAMETERS TYPES, and an optional name
	# TODO: Add method (GET or POST)
	@exposed()
	def friends( self ):
		return ["bob", "alice"]

# ------------------------------------------------------------------------------
#
# USER COMPONENT
#
# ------------------------------------------------------------------------------

class Main(Component):
	"""This is the main component for the railways application. It simply grants
	access to fiels located in ../../Library and serves the main `index.kid`
	template locate in the `templates` subdirectory."""

	@on(GET="lib/{path:any}")
	def lib( self, request, path ):
		"""Serves the files located in the `Library` grand parent directory."""
		# This is really only useful when running standalone, as with normal
		# setups, this data should be served by a more poweful web server, with
		# caching and load balancing.
		return request.localfile(self.app().localPath("../../Library/" + path))

	@on(GET="/")
	@display("index")
	def main( self, request ):
		"""Serves the main template file"""
		pass

# ------------------------------------------------------------------------------
#
# Main
#
# ------------------------------------------------------------------------------

if __name__ == "__main__":
	# Init the storage, and create sample data
	storage = Storage(reset=True, classes=(User,))
	storage.new.user("alice", "alice's password")
	storage.new.user("bob",   "bob's password")
	storage.new.user("oscar", "oscar's password")
	# Here we use the PrevailedWeb.expose method to automatically create
	# wrappers for the objects present in the storage.
	run(
		app        = Application(components=(Main(), expose(storage))),
		name       = os.path.splitext(os.path.basename(__file__))[1],
		method     = STANDALONE
	)

# EOF
