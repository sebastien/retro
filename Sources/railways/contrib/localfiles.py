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
# Last mod  : 11-Feb-2008
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
.directoryListing li:hover{
	background: #FFFFE0;
}
.directoryListing .bullet {
	color: #AAAAAA;
	padding-right: 20px;
}
.directoryListing .directory {
	background: #EEEEEE;
}
.directoryListing .hidden, .directoryListing .hidden a {
	color: #FFAAAA;
	font-style: italic;
}
.directoryListing .parent {
	color: #AAAAAA;
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

	def __init__( self, root="", name = None, processors={} ):
		"""Creates a new LocalFiles, with the optional root, name and
		processors. Processors are functions that modify the content
		of the file and returned the processed data."""
		Component.__init__(self, name="LocalFiles")
		self._localRoot = root
		self._processors  = {}
		for key, value in processors.items():
			self._processors[key] = value

	def init( self, root=None ):
		if not (root is None) :
			root = os.path.abspath(root)
			self.setRoot(root)
		elif self._localRoot is None:
			root = self.app().config("root")

	def setRoot( self, root ):
		"""Sets the root used by this component. This is where the
		local files will be resolved."""
		assert os.path.exists(root), "Given root doest not exist: %s" % (root)
		self._localRoot = root

	def getRoot( self, root ):
		"""Returns the root for this component"""
		return self._localRoot

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

	def processorFor( self, path ):
		"""Returns the processors for the given path."""
		ext = os.path.splitext(path)[1][1:]
		for key, value in self._processors.items():
			if ext == key:
				return value
		return lambda x,p:(x, self.getContentType(path))

	@on(GET_POST="/")
	def catchall( self, request ):
		"""A catchall that will display the content of the current
		directory."""
		return self.local(request, ".")

	@on(GET_POST="/{path:any}")
	def local( self, request, path ):
		"""Serves the files located in the `Library` grand parent directory."""
		resolved_path = self.app().localPath(os.path.join(self._localRoot, path))
		processor = self.processorFor(path)
		if not os.path.exists(resolved_path):
			return request.respond("File not found: %s" % (resolved_path), status=404)
		elif os.path.isdir(resolved_path):
			if self.LIST_DIR:
				return request.respond(self.directoryAsHtml(path, resolved_path))
			else:
				return request.respond("Component does not allows directory listing" % (resolved_path), status=403)
		else:
			content, content_type = processor(self.getContent(resolved_path), path)
			return request.respond(content=content, contentType=content_type)

	def directoryAsHtml( self, path, localPath ):
		"""Returns a directory as HTML"""
		dirs  = []
		files = []
		parent = os.path.dirname(path)
		if path and path not in ("/", "."):
			dirs.append("<li class='previous dir'><span class='bullet'>&hellip;</span><a class='parent' href='%s/%s'>(parent)</a></li>" % (self.PREFIX, parent))
		for file_name in os.listdir(localPath):
			file_path = localPath + "/" + file_name
			ext       = os.path.splitext(file_path)[1].replace(".", "_")
			if file_name.startswith("."): ext +=" hidden"
			file_url = ("/" + path + "/" +file_name).replace("//","/")
			if os.path.isdir(file_path):
				dirs.append("<li class='directory %s'><span class='bullet'>&fnof;</span><a href='%s'>%s</a></li>" % (
					ext, file_url, file_name
				))
			else:
				files.append("<li class='file %s'><span class='bullet'>&mdash;</span><a href='%s'>%s</a></li>" % (
					ext, file_url, file_name
				))
		return LIST_DIR_HTML % (path, LIST_DIR_CSS, path, "".join(dirs) + "".join(files))

# EOF
