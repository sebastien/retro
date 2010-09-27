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
# Last mod  : 26-Sep-2010
# -----------------------------------------------------------------------------

__doc__ = """
The 'localfiles' module defines a LocalFiles component that can be added to
any application to serve local files."""

import os, sys, mimetypes
from retro import *
from retro.wsgi import SERVER_ERROR_CSS
from retro.contrib.cache import SignatureCache

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

	def __init__( self, root="", name=None, processors={}, optsuffix=() ):
		"""Creates a new LocalFiles, with the optional root, name and
		processors. Processors are functions that modify the content
		of the file and returned the processed data."""
		Component.__init__(self, name="LocalFiles")
		self._localRoot   = None
		self._processors  = {}
		self._optSuffixes = optsuffix
		self.setRoot(root)
		for key, value in processors.items():
			self._processors[key] = value

	def start( self, root=None ):
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
		f = file(path, 'rb') ; c=f.read() ; f.close()
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
		resolved_path = self.resolvePath(path)
		processor     = self.processorFor(resolved_path)
		if not os.path.exists(resolved_path):
			return request.respond("File not found: %s" % (resolved_path), status=404)
		elif os.path.isdir(resolved_path):
			if self.LIST_DIR:
				if request.param("format") == "json":
					return request.returns(self.directoryAsList(path, resolved_path))
				else:
					return request.respond(self.directoryAsHtml(path, resolved_path))
			else:
				return request.respond("Component does not allows directory listing" % (resolved_path), status=403)
		else:
			content, content_type = processor(self.getContent(resolved_path), resolved_path)
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

	def directoryAsList( self, path, localPath ):
		"""Returns a directory as JSON"""
		dirs  = []
		files = []
		parent = os.path.dirname(path)
		local_files = list(os.path.join(parent, p) for p in os.listdir(localPath))
		local_files.sort()
		return local_files

# ------------------------------------------------------------------------------
#
# LIBRARY SERVER COMPONENT
#
# ------------------------------------------------------------------------------

class LibraryServer(Component):
	"""Servers files from a library directory and expose them as 'lib/'. The
	library server supports the following file types:

	- CSS        ('lib/css')
	- CleverCSS  ('lib/ccss')
	- JavaScript ('lib/js')
	- Sugar      ('lib/sjs')
	- Images     ('lib/images', of type 'png', 'gif', 'jpg', 'ico' and 'svg')
	- Flash      ('lib/swf' and 'crossdomain.xml')
	- PDF        ('lib/pdf')

	The implementation is not that flexible, but it's a very good start
	for most web applications. You can specialize this class later if you
	want to change the behaviour."""


	@staticmethod
	def read( path ):
		f = file(path, 'rb')
		t = f.read()
		f.close()
		return t

	def __init__( self, library="", name="LibraryServer", cache=None ):
		Component.__init__(self, name=name)
		self.library = library
		self.cache   = cache

	def start( self ):
		self.library  = self.library or self.app().config("library.path")

	def setCache( self, cache ):
		self.cache = cache
		return self

	def _inCache( self, path ):
		path = os.path.abspath(path)
		if self.cache:
			if isinstance(self.cache, SignatureCache):
				return self.cache.has(path, SignatureCache.mtime(path))
			else:
				return self.cache.has(path)
		else:
			return False

	def _fromCache( self, path ):
		path = os.path.abspath(path)
		assert self.cache
		if isinstance(self.cache, SignatureCache):
			return self.cache.get(path, SignatureCache.mtime(path))[1]
		else:
			return self.cache.get(path)

	def _toCache( self, path, data ):
		path = os.path.abspath(path)
		if self.cache:
			if isinstance(self.cache, SignatureCache):
				return self.cache.set(path, SignatureCache.mtime(path), data)
			else:
				return self.cache.set(path, data)
		return data

	@on(GET="crossdomain.xml")
	def getCrossDomain( self, request ):
		return request.respond(
			'<?xml version="1.0"?>'
			+ '<!DOCTYPE cross-domain-policy SYSTEM "http://www.macromedia.com/xml/dtds/cross-domain-policy.dtd">'
			+ '<cross-domain-policy><allow-access-from domain="*" /></cross-domain-policy>'
		)

	@on(GET="lib/css/{css:[\w\-_\.]+\.css}")
	def getCSS( self, request, css ):
		return request.respondFile(os.path.join(self.library, "css", css))

	@on(GET="lib/css/{css:[\w\-_\.]+\.ccss}")
	@on(GET="lib/ccss/{css:[\w\-_\.]+\.ccss}")
	def getCCSS( self, request, css ):
		import clevercss
		root = self.library
		if os.path.exists(os.path.join(root, "ccss", css)):
			path = os.path.join(root, "ccss", css)
		else:
			path = os.path.join(root, "css", css)
		if not self._inCache(path):
			text = self.app().load(path)
			text = self._toCache(path, clevercss.convert(text))
		else:
			text = self._fromCache(path)
		return request.respond(text, contentType="text/css")

	@on(GET="lib/images/{image:([\w\-_]+/)*[\w\-_]+\.(png|gif|jpg|ico|svg)}")
	def getImage( self, request, image ):
		return request.respondFile(os.path.join(self.library, "images", image))

	@on(GET="lib/swf/{script:\w+\.swf}")
	def getFlash( self, request, script ):
		return request.respondFile(os.path.join(self.library, "swf", script))

	@on(GET="lib/pdf/{script:[\w\-_\.]+\.pdf}")
	def getPDF( self, request, script ):
		return request.respondFile(os.path.join(self.library, "pdf", script))

	@on(GET="lib/js/{path:rest}")
	@on(GET="lib/sjs/{path:rest}")
	def getJavaScript( self, request, path ):
		if os.path.exists(os.path.join(self.library, "sjs", path)):
			path = os.path.abspath(os.path.join(self.library, "sjs", path))
		else:
			path = os.path.abspath(os.path.join(self.library, "js", path))
		if path.startswith(os.path.abspath(self.library)):
			if path.endswith(".sjs"):
				from sugar import main as sugar
				path = path.replace("/js", "/sjs")
				data = None
				if not self._inCache(path):
					data = sugar.sourceFileToJavaScript(path, options="-L%s" % (self.library + "/sjs"))
					self._toCache(path, data)
				else:
					data = self._fromCache(path)
				return request.respond(data,contentType="text/javascript")
			else:
				return request.respondFile(path)
		else:
			# Somebody is trying to hack the API !
			# (the path is not the right path)
			return request.returns(False)

# EOF
