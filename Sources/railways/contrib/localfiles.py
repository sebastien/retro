#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet
# -----------------------------------------------------------------------------
# Project   : Railways - Declarative Python Web Framework
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ivy.fr>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 12-Apr-2006
# Last mod  : 22-Mar-2007
# -----------------------------------------------------------------------------

__doc__ = """
The 'localfiles' module defines a LocalFiles component that can be added to
any application to serve local files."""

import os, sys, mimetypes
from railways import *
from railways.wsgi import SERVER_ERROR_CSS

LIST_DIR_CSS  = SERVER_ERROR_CSS + """
.directoryListing {
	list-style-type: none;
}
.directoryListing .directory {
	background: #EEEEEE;
}
"""

LIST_DIR_HTML = """
<html>
<head>
	<title>Content of %s</title>
	<style><!--
	%s
	--></style>
</head>
<body>
	<h1>Content of <span class="dirname">%s</span></h1>
	<ul class="directoryListing">
	%s
	</ul>
</body>
</html>
"""
# ------------------------------------------------------------------------------
#
# LOCAL FILE COMPONENT
#
# ------------------------------------------------------------------------------

class LocalFiles(Component):
	"""The 'LocalFiles' component serves local files from the file system."""

	LIST_DIR = True

	def init( self, root=None ):
		if not root or not os.path.exists(root):
			root = self.app().config("root")
		else:
			root = os.path.abspath(root)
		self._localRoot = root

	def setRoot( self, root ):
		"""Sets the root used by this component. This is where the
		local files will be resolved."""
		assert os.path.exists(root), "Given root doest not exist: %s" % (root)
		self._localRoot = root

	def resolvePath( self, path ):
		"""Resolves the given path and returns an absolute file system
		location for the given path (which is supposed to be relative)."""
		resolved = self.app().localPath(os.path.join(self._localRoot, path))
		return resolved

	def getContentType( self, path ):
		"""A function that returns the mime type from the given file
		path."""
		return mimetypes.guess_type(path)[0] or "text/plain"

	def getContent( self, path ):
		"""Gets the content for this file."""
		f = file(path, 'r') ; c=f.read() ; f.close()
		return c

	@on(GET_POST="/")
	def catchall( self, request ):
		"""A catchall that will display the content of the current
		directory."""
		return self.local(request, ".")

	@on(GET_POST="/{path:any}")
	def local( self, request, path ):
		"""Serves the files located in the `Library` grand parent directory."""
		resolved_path = self.app().localPath(os.path.join(self._localRoot, path))
		if not os.path.exists(resolved_path):
			return request.respond("File not found: %s" % (resolved_path), status=404)
		elif os.path.isdir(resolved_path):
			if self.LIST_DIR:
				return request.respond(self.directoryAsHtml(path, resolved_path))
			else:
				return request.respond("Component does not allows directory listing" % (resolved_path), status=403)
		else:
			return request.respond(content=self.getContent(resolved_path), contentType=self.getContentType(resolved_path))

	def directoryAsHtml( self, path, localPath ):
		"""Returns a directory as HTML"""
		dirs  = []
		files = []
		parent = os.path.dirname(path)
		if parent:
			dirs.append("<li class='previous dir'><a href='%s/%s'>..</a></li>" % (self.PREFIX, parent))
		for file_name in os.listdir(localPath):
			file_path = localPath + "/" + file_name
			ext       = os.path.splitext(file_path)[1]
			if os.path.isdir(file_path):
				dirs.append("<li class='directory %s'><a href='%s/%s'>%s</a></li>" % (
					ext, os.path.basename(path), file_name, file_name
				))
			else:
				files.append("<li class='file %s'><a href='%s/%s'>%s</a></li>" % (
					ext, os.path.basename(path), file_name, file_name
				))
		return LIST_DIR_HTML % (path, LIST_DIR_CSS, path, "".join(dirs) + "".join(files))

# EOF
