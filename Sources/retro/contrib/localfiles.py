#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet
# -----------------------------------------------------------------------------
# Project   : Retro - Declarative Python Web Framework
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ivy.fr>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 12-Apr-2006
# Last mod  : 02-Jul-2009
# -----------------------------------------------------------------------------

__doc__ = """
The 'localfiles' module defines a LocalFiles component that can be added to
any application to serve local files."""

import os, sys, mimetypes
from retro import *
from retro.wsgi import SERVER_ERROR_CSS

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

	def __init__( self, root="", name = None, processors={}, optsuffix=() ):
		"""Creates a new LocalFiles, with the optional root, name and
		processors. Processors are functions that modify the content
		of the file and returned the processed data."""
		Component.__init__(self, name="LocalFiles")
		self._localRoot   = root
		self._processors  = {}
		self._optSuffixes = optsuffix
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
		real_path = self.app().localPath(os.path.join(self._localRoot, path))
		if not os.path.exists(real_path):
			for s in self._optSuffixes:
				if os.path.exists(real_path + s):
					return real_path + s
		return real_path

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
		resolved_path = self.resolvePath(os.path.join(self._localRoot, path))
		processor     = self.processorFor(resolved_path)
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
		local_files = os.listdir(localPath)
		local_files.sort()
		for file_name in local_files:
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

# ------------------------------------------------------------------------------
#
# FILE SERVER COMPONENT
#
# ------------------------------------------------------------------------------

class FileServer(Component):
	"""Serves local files, should be replaced in production by another server."""

	def init( self ):
		self.DIR_LIBRARY = self.app().config("library.path")
		self.CACHE       = None

	def setCache( self, cache ):
		self.CACHE = cache
		return self

	@on(GET="crossdomain.xml")
	def getCrossDomain( self, request ):
		return request.respond(
			'<?xml version="1.0"?>'
			+ '<!DOCTYPE cross-domain-policy SYSTEM "http://www.macromedia.com/xml/dtds/cross-domain-policy.dtd">'
			+ '<cross-domain-policy><allow-access-from domain="*" /></cross-domain-policy>'
		)

	@on(GET="lib/css/{css:[\w\-_\.]+\.css}")
	def getCss( self, request, css ):
		return request.respondFile(os.path.join(self.DIR_LIBRARY, "css", css))

	@on(GET="lib/images/{image:[\w\-_]+\.(png|gif|jpg)}")
	def getImage( self, request, image ):
		return request.respondFile(os.path.join(self.DIR_LIBRARY, "images", image))

	@on(GET="lib/swf/{script:\w+\.swf}")
	def getFlash( self, request, script ):
		# TODO: Rewrite respondFile
		return request.respondFile(os.path.join(self.DIR_LIBRARY, "swf", script))

	@on(GET="lib/js/{path:rest}")
	@on(GET="lib/sjs/{path:rest}")
	def getJavaScript( self, request, path ):
		path = os.path.abspath(os.path.join(self.DIR_LIBRARY, "js", path))
		if path.startswith(self.DIR_LIBRARY):
			if path.endswith(".sjs"):
				from sugar import main as sugar
				# FIXME: Cache this
				path = path.replace("/js", "/sjs")
				if self.CACHE:
					timestamp         = CACHE.filemod(path)
					has_changed, data = CACHE.get(path,timestamp)
				else:
					has_changed = True
				if has_changed:
					data = sugar.sourceFileToJavaScript(path, options="-L%s" % (self.DIR_LIBRARY + "/sjs"))
					if self.CACHE:
						CACHE.put(path,timestamp,data)
				return request.respond(data,contentType="text/javascript")
			else:
				return request.respondFile(path)
		else:
			# Somebody is trying to hack the API !
			# (the path is not the right path)
			return request.returns(False)

# EOF
