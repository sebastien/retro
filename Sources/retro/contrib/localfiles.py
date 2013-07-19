#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Project   : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                            <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 12-Apr-2006
# Last mod  : 19-Jul-2013
# -----------------------------------------------------------------------------

# SEE:http://www.mnot.net/cache_docs/

__doc__ = """
The 'localfiles' module defines `LocalFiles` and `Library` component that can
be added to any application to serve local files and assets"""

import os, sys, mimetypes, subprocess
from retro import *
from retro.wsgi import SERVER_ERROR_CSS
from retro.contrib.cache import SignatureCache

try:
	import jsmin
except:
	jsmin = None
try:
	import cssmin
except:
	cssmin = None
try:
	import clevercss
except:
	clevercss = None

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
	"""The 'LocalFiles' component serves local files from the file system,
	providing a directory-listing interface."""

	LIST_DIR = True

	def __init__( self, root="", name=None, processors={}, optsuffix=() ):
		"""Creates a new LocalFiles, with the optional root, name and
		processors. Processors are functions that modify the content
		of the file and returned the processed data."""
		Component.__init__(self, name="LocalFiles")
		self._localRoot   = None
		self._processors  = {}
		self._optSuffixes = optsuffix
		self.setRoot(root or ".")
		for key, value in processors.items():
			self._processors[key] = value

	def start( self, root=None ):
		if not (root is None) :
			root = os.path.abspath(root)
			self.setRoot(root or ".")
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
		if path.endswith(".json"):
			return "application/json"
		else:
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
		return None

	@on(GET_POST_HEAD="/")
	def catchall( self, request ):
		"""A catchall that will display the content of the current
		directory."""
		return self.local(request, ".")

	@on(GET_POST_HEAD="/{path:any}")
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
		if processor:
			content, content_type = processor(self.getContent(resolved_path), resolved_path, request)
			return request.respond(content=content, contentType=content_type)
		else:
			return request.respondFile(resolved_path)

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
	- Fonts      ('lib/fonts')

	The implementation is not that flexible, but it's a very good start
	for most web applications. You can specialize this class later if you
	want to change the behaviour."""

	CONTENT_TYPES = dict(
		svg  = "image/svg+xml",
		ico  = "image/vnd.microsoft.icon",
		png  = "image/png",
		gif  = "image/gif",
		jpg  = "image/jpeg",
		jpeg = "image/jpeg",
	)

	def __init__( self, library="", name="LibraryServer", cache=None, commands=dict(), minify=False, compress=False, cacheAggregates=True, cacheDuration=24*60*60 ):
		Component.__init__(self, name=name)
		self.library  = library
		self.cache    = cache
		self.minify   = minify
		self.compress = compress
		self.commands = dict(sugar="sugar")
		self.commands.update(commands)
		self.cacheAggregates = cacheAggregates
		self.cacheDuration   = cacheDuration

	def start( self ):
		self.library  = self.library or self.app().config("library.path")

	def setCache( self, cache ):
		self.cache = cache
		return self

	def _inCache( self, path ):
		if self.cache:
			if isinstance(self.cache, SignatureCache):
				return self.cache.has(path, SignatureCache.mtime(path))
			else:
				return self.cache.has(path)
		else:
			return False

	def _fromCache( self, path ):
		assert self.cache
		if isinstance(self.cache, SignatureCache):
			return self.cache.get(path, SignatureCache.mtime(path))[1]
		else:
			return self.cache.get(path)

	def _toCache( self, path, data ):
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
		).cache(years=1)

	@on(GET="lib/fonts/{path:rest}")
	def getFonts( self, request, path ):
		return request.respondFile(os.path.join(self.library, "fonts", path)).cache(seconds=self.cacheDuration)

	@on(GET="lib/images/{image:([\w\-_]+/)*[\w\-_]+(\.png|\.gif|\.jpg|\.ico|\.svg)*}")
	def getImage( self, request, image ):
		content_type = self.CONTENT_TYPES.get(image.rsplit(".",1)[-1])
		# NOTE: I had to add the content type as not adding it blocks the system in production in some circumstances...
		return request.respondFile(self._guessPath("images", image, extensions=(".png", ".gif", ".jpg", ".ico", ".svg")), content_type).cache(seconds=self.cacheDuration)

	@on(GET="lib/swf/{script:[^/]+\.swf}")
	def getFlash( self, request, script ):
		return request.respondFile(os.path.join(self.library, "swf", script)).cache(seconds=self.cacheDuration)

	@on(GET="lib/pdf/{script:[^/]+\.pdf}")
	def getPDF( self, request, script ):
		return request.respondFile(os.path.join(self.library, "pdf", script)).cache(seconds=self.cacheDuration)

	@on(GET="lib/css/{paths:rest}")
	def getCSS( self, request, paths ):
		return self._getFromLibrary(request, "css", paths, "text/css; charset=utf-8")

	@on(GET="lib/ccss/{paths:rest}")
	def getCCSS( self, request, paths ):
		return self._getFromLibrary(request, "ccss", paths, "text/css; charset=utf-8")

	@on(GET="lib/{prefix:(js|sjs)}/{paths:rest}")
	def getJavaScript( self, request, prefix, paths ):
		return self._getFromLibrary(request, prefix, paths, "text/javascript; charset=utf-8")

	def _getFromLibrary( self, request, prefix, paths, contentType ):
		"""Gets the `+` separated list of files given in `paths`, relative to
		this library's `root` and `prefix`, returning a concatenated result of
		the given contentType."""
		cache_path = prefix + paths
		if not self.cacheAggregates or not self._inCache(cache_path) or cache_path.find("+") == -1:
			result = []
			for path in paths.split("+"):
				root = self.library
				path = os.path.join(root, prefix, path)
				if not self._inCache(path):
					data = self._processPath(path)
					self._toCache(path, data)
				else:
					data = self._fromCache(path)
				result.append(data)
			response_data = "\n".join(result)
			self._toCache(cache_path, response_data)
		else:
			response_data = self._fromCache(cache_path)
		return request.respond(response_data, contentType=contentType).compress(self.compress).cache(seconds=self.cacheDuration)

	def _processPath( self, path ):
		"""Processes the file at the given path using on of the dedicated
		file processor."""
		if   path.endswith(".sjs"):  return self._processSJS(path)
		elif path.endswith(".js"):   return self._processJS(path)
		elif path.endswith(".ccss"): return self._processCCSS(path)
		elif path.endswith(".css"):  return self._processCSS(path)
		else: raise Exception("Format not supported: " + path)

	def _processCSS( self, path ):
		"""Processes a CSS file, minifyiing it if `cssmin` is installed."""
		data = self.app().load(path)
		if self.minify and cssmin: data = cssmin.cssmin(data)
		return data

	def _processCCSS( self, path ):
		"""Processes a CCSS file, minifying it if `cssmin` is installed.
		Requires `clevercss`"""
		data = self.app().load(path)
		data = clevercss.convert(data)
		if self.minify and cssmin: data = cssmin.cssmin(data)
		return data

	def _processSJS( self, path ):
		"""Processes a Sugar JS file, minifying it if `jsmin` is installed.
		Requires `sugar`"""
		data    = ""
		tries   = 0
		# NOTE: For some reason, sugar sometimes fails, so we add a
		# number of retries so that we increase the "chances" of the
		# file to be properly loaded
		while (not data) and tries < 3:
			command = "%s -cljs %s %s" % (self.commands["sugar"], "-L%s" % (self.library + "/sjs"), path)
			cmd     = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
			data    = cmd.stdout.read()
			tries  += 1
			cmd.wait()
		if data:
			if self.minify and jsmin: data = jsmin.jsmin(data)
		return data

	def _processJS( self, path ):
		"""Processes a JS file, minifying it if `jsmin` is installed."""
		data = self.app().load(path)
		if self.minify and jsmin: data = jsmin.jsmin(data)
		return data

	def _guessPath( self, parent, filename, extensions ):
		"""Tries to locate the file with the given `filename` in the `parent` directory of this
		library, appending the given `extensions` if the file is not found."""
		path = os.path.join(self.library, parent, filename)
		if os.path.exists(path):
			return path
		for ext in extensions:
			p = path + ext
			if os.path.exists(p):
				return p
		return None

# EOF - vim: tw=80 ts=4 sw=4 noet
