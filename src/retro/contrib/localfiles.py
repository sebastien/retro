#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Project   : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                            <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 2006-04-12
# Last mod  : 2017-07-13
# -----------------------------------------------------------------------------

# SEE:http://www.mnot.net/cache_docs/

__doc__ = """
The 'localfiles' module defines `LocalFiles` and `Library` component that can
be added to any application to serve local files and assets"""

import os, sys, stat, mimetypes, subprocess, base64
from retro import *
from retro.wsgi import SERVER_ERROR_CSS
from retro.contrib.cache import SignatureCache

FAVICON = base64.b64decode("""\
AAABAAEAEBAAAAEAIABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAAAQAAAAAAAAAAAAAAAAA
AAAAAAAAAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/
AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8A
AAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/z8/P/9/f3//b29v/w8PD/8AAAD/AAAA/w8P
D/9vb2//f39//z8/P/8AAAD/AAAA/wAAAP8AAAD/AAAA/x8fH///////j4+P/8/Pz/+vr6//AAAA
/wAAAP+vr6//z8/P/4+Pj///////Hx8f/wAAAP8AAAD/AAAA/wAAAP8/Pz//7+/v/wAAAP9PT0//
7+/v/wAAAP8AAAD/v7+//09PT/8AAAD/7+/v/z8/P/8AAAD/AAAA/wAAAP8AAAD/Hx8f/+/v7/+/
v7//n5+f//////9/f3//f39//9/f3/+fn5//v7+//+/v7/8fHx//AAAA/wAAAP8AAAD/AAAA/wAA
AP8fHx//b29v/7+/v///////f39//39/f///////v7+//39/f/8fHx//AAAA/wAAAP8AAAD/AAAA
/wAAAP8AAAD/AAAA/wAAAP9/f3///////wAAAP8AAAD//////39/f/8AAAD/AAAA/wAAAP8AAAD/
AAAA/wAAAP8AAAD/AAAA/x8fH/8/Pz//n5+f//////8/Pz//Pz8///////+fn5//Pz8//x8fH/8A
AAD/AAAA/wAAAP8AAAD/AAAA/wAAAP9/f3//////////////////////////////////////////
//9/f3//AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8/Pz///////wAAAP8AAAD/v7+/
/z8/P/8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/Pz8///////8PDw//
AAAA/7+/v/9/f3//AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/w8PD//v
7+//39/f/29vb/9/f3///////6+vr/+fn5//AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAA
AP8AAAD/Hx8f/39/f/9fX1//AAAA/19fX/9/f3//b29v/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA
/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/
AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8AAAD/AAAA/wAAAP8A
AAD/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAA==""")

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
try:
	import paml
except:
	paml = None
try:
	import pythoniccss
except:
	pythoniccss = None

LIST_DIR_CSS  = SERVER_ERROR_CSS + """
.retro-directory-listing {
	list-style-type: none;
}
.retro-directory-listing li:hover{
	background: #FFFFE0;
}
.retro-directory-listing li {
	padding: 0.5em;
	padding-top: 0.25em;
	padding-bottom: 0.25em;
	position: relative;
	display: flex;
	width: 100%;
}
.retro-directory-listing li .bullet {
	color: #AAAAAA;
	display: inline;
	position: absolute;
	left: 0.5em;
}

.retro-directory-listing li .name {
	position: relative;
	padding-left: 2.5em;
	display: block;
	padding-top: 0.10em;
	padding-bottom: 0.10em;
	flex-grow: 1;
}

.retro-directory-listing li .gz {
	opacity: 0.25;
}
.retro-directory-listing li .size {
	opacity: 0.5;
}
.retro-directory-listing .directory {
	background: #EEEEEE;
}
.retro-directory-listing .hidden, .retro-directory-listing .hidden a {
	color: #FFAAAA;
	font-style: italic;
}
.retro-directory-listing .parent {
	color: #AAAAAA;
	padding-top: 0.5em;
	padding-bottom: 0.5em;
}
"""

LIST_DIR_HTML = """
<!DOCTYPE html>
<html>
<head>
	<meta charset="UTF-8" />
	<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no" />
	 <title>Content of %s</title>
	<style><!--
	%s
	--></style>
</head>
<body>
	<h1>Content of <span class="dirname">%s</span></h1>
	<ul class="retro-directory-listing">
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
	providing a directory-listing interface. This component is designed
	to be used in development environments, where you need direct access
	to local files and live file translation (using `processors`)."""

	LIST_DIR          = True
	USE_LAST_MODIFIED = True

	def __init__( self, root="", name=None, processors={}, resolver=None, optsuffix=(), lastModified=None, writable=False, prefix=None):
		"""Creates a new LocalFiles, with the optional root, name and
		processors. Processors are functions that modify the content
		of the file and returned the processed data."""
		Component.__init__(self, name="LocalFiles", prefix=prefix)
		self._lastModified = self.USE_LAST_MODIFIED if lastModified is None else lastModified
		self._localRoot    = None
		self._processors   = {}
		self._resolver     = resolver
		self._optSuffixes  = optsuffix
		self.isWritable    = writable
		self.setRoot(root or ".")
		for key, value in list(processors.items()):
			self._processors[key] = value

	def start( self, root=None ):
		if not (root is None) :
			root = os.path.abspath(root)
			self.setRoot(root or ".")
		elif self._localRoot is None:
			root = self.app.config("root")

	def setRoot( self, root ):
		"""Sets the root used by this component. This is where the
		local files will be resolved."""
		assert os.path.exists(root), "Given root doest not exist: %s" % (root)
		self._localRoot = root

	def getRoot( self, root ):
		"""Returns the root for this component"""
		return self._localRoot

	def resolvePath( self, request, path ):
		"""Forwards the call to the resolver if present or defaults to
		`_resolvePath`."""
		return self._resolver(self, request, path) if self._resolver else self._resolvePath(path)

	def _resolvePath( self, path ):
		"""Resolves the given path and returns an absolute file system
		location for the given path (which is supposed to be relative)."""
		real_path = self.app.localPath(os.path.join(self._localRoot, path))
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
		elif path.endswith(".mf"):
			return "text/cache-manifest"
		else:
			return mimetypes.guess_type(path)[0] or "text/plain"

	def getContent( self, path ):
		"""Gets the content for this file."""
		with open(path, "rt") as f:
			return f.read()

	def processorFor( self, path ):
		"""Returns the processors for the given path."""
		if isinstance(path, list) or isinstance(path, tuple): path = path[0]
		matches = sorted([_ for _ in self._processors if path.endswith(_)])
		return self._processors[matches[-1]] if matches else None

	@on(GET_POST_HEAD="/favicon.ico",priority=10)
	def favicon( self, request ):
		for p in ["favicon.ico", "lib/images/favicon.ico"]:
			rp = self.resolvePath(request, p)
			if os.path.exists(rp):
				return self.local(request, p)
		return request.respond(FAVICON, "image/x-icon")

	@on(GET_POST_HEAD="/")
	def catchall( self, request ):
		"""A catchall that will display the content of the current
		directory."""
		return self.local(request, ".")

	@on(GET_POST_HEAD="/{path:any}")
	def local( self, request, path ):
		"""Serves the files located in the `Library` grand parent directory. This will
		look for a .gz version if the file is not already there.

		If `path` is a list or tuple, it will aggregate all the responses
		together and use the first content type.
		"""
		resolved_path = self.resolvePath(request, path)
		multi_paths   = None
		processor     = self.processorFor(resolved_path)
		if isinstance(resolved_path, list) or isinstance(resolved_path, tuple):
			multi_paths   = resolved_path
			resolved_path = resolved_path[0]
		elif not os.path.exists(resolved_path):
			# If the file is not found we're still going to look for a .gz
			if path.endswith(".gz"):
				return request.respond("File not found: %s" % (resolved_path), status=404)
			else:
				res = self.local(request, path + ".gz")
				if res.status >= 200 and res.status < 300:
					res.setHeader("Content-Type", request.guessContentType(path)).setHeader("Content-Encoding", "gzip")
				return res
		elif os.path.isdir(resolved_path):
			if self.LIST_DIR:
				if request.param("format") == "json":
					return request.returns(self.directoryAsList(path, resolved_path))
				else:
					return request.respond(self.directoryAsHtml(path, resolved_path))
			else:
				return request.respond("Component does not allows directory listing" % (resolved_path), status=403)
		if processor and not request.has("raw"):
			return self._respondWithProcessor( request, processor, resolved_path, multi_paths  )
		elif request.has("raw"):
			return request.respondFile(resolved_path, contentType="text/plain", lastModified=self._lastModified)
		else:
			return request.respondFile(resolved_path, lastModified=self._lastModified)

	def _respondWithProcessor( self, request, processor, resolvedPath=None, multiPaths=None):
		if not multiPaths:
			try:
				content, content_type = processor(self.getContent(resolvedPath), resolvedPath, request)
				return request.respond(content=content, contentType=content_type)
			except Exception as e:
				return request.fail(status=500, content=str(e))
		else:
			try:
				content, content_type = processor(None, multiPaths, request)
				return request.respond(content=content, contentType=content_type)
			except Exception as e:
				return request.fail(status=500, content=str(e))

	@on(PUT_PATCH="/{path:any}")
	def write( self, request, path ):
		if self.isWritable:
			# NOTE: We don't use self.resolvePath, as we want to bypass resolvers
			local_path = self._resolvePath(path)
			dirname = os.path.dirname(local_path)
			if not os.path.exists(dirname): os.makedirs(dirname)
			request.load()
			data = request.data()
			self.app.save(local_path, ensureBytes(data))
			return request.returns(True)
		else:
			return self.local(request, path)

	@on(DELETE="/{path:any}")
	def delete( self, request, path ):
		if self.isWritable:
			# NOTE: We don't use self.resolvePath, as we want to bypass resolvers
			local_path = self._resolvePath(path)
			if os.path.exists(local_path):
				os.unlink(local_path)
				return request.returns(True)
			else:
				return request.returns(False)
		else:
			return self.local(request, path)

	def directoryAsHtml( self, path, localPath ):
		"""Returns a directory as HTML"""
		dirs  = []
		files = []
		dot_files = []
		parent = os.path.dirname(path)
		if path and path not in ("/", "."):
			dirs.append("<li class='previous dir'><span class='bullet'>&hellip;</span><a class='parent' href='%s/%s'>(parent)</a></li>" % (self.PREFIX, parent))
		local_files = os.listdir(localPath)
		local_files.sort()
		for file_name in local_files:
			file_path = localPath + "/" + file_name
			ext       = os.path.splitext(file_path)[1].replace(".", "_")
			if file_name.startswith("."): ext +=" hidden"
			file_url = self.PREFIX + ("/" + path + "/" +file_name).replace("//","/")
			if os.path.isdir(file_path):
				dirs.append(
					"<li class='directory %s'>"
					"<span class='bullet'>&fnof;</span>"
					"<a class='name' href='%s'>%s</a>"
					"</li>" % (
					ext, file_url, file_name
				))
			else:
				try:
					size = os.stat(file_path)[stat.ST_SIZE]
				except Exception as e:
					size = 0
				unit = None
				if size < 1000:
					unit = "b"
					size = size
				elif size < 1000000:
					unit = "kb"
					size = size / 1000.0
				else:
					unit = "mb"
					size = size / 1000000.0
				if size == int(size):
					size = "{0:d}{1}".format(int(size),unit)
				else:
					size = "{0:0.2f}{1}".format(size,unit)
				group = dot_files if file_name.startswith(".") else files
				if file_name.endswith(".gz"):
					group.append(
						"<li class='file compressed %s'>"
						"<span class='bullet'>&mdash;</span>"
						"<a class='name' href='%s'>%s<span class=gz>.gz</span></a>"
						"<span class='size'>%s</span>"
						"</li>" % (
							ext,
							file_url[:-3], file_name[:-3],
							size,
					))
				else:
					group.append(
						"<li class='file %s'>"
						"<span class='bullet'>&mdash;</span>"
						"<a class='name' href='%s'>%s</a>"
						"<span class='size'>%s</span>"
						"</li>" % (
						ext, file_url, file_name, size,
					))
		return LIST_DIR_HTML % (path, LIST_DIR_CSS, path, "".join(dirs) + "".join(files + dot_files))

	def directoryAsList( self, path, localPath ):
		"""Returns a directory as JSON"""
		dirs  = []
		files = []
		parent = os.path.dirname(path)
		local_files = list(os.path.join(parent, p) for p in os.listdir(localPath))
		local_files.sort()
		return [self._describePath(_) for _ in local_files]

	def _describePath( self, path ):
		s = os.stat(path)
		return {
			"name" : os.path.basename(path),
			"path" : path,
			"isDirectory" : os.path.isdir(path),
			"isFile" : os.path.isfile(path),
			"isLink" : os.path.islink(path),
			"mtime"  : s[stat.ST_MTIME],
			"atime"  : s[stat.ST_ATIME],
			"mode"   : s[stat.ST_MODE],
			"size"   : s[stat.ST_SIZE],
			"uid"    : s[stat.ST_UID],
			"gid"    : s[stat.ST_GID],
		}

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
	- PythonicCSS('lib/pcss')
	- JavaScript ('lib/js')
	- Sugar      ('lib/sjs')
	- Images     ('lib/images', of type 'png', 'gif', 'jpg', 'ico' and 'svg')
	- PDF        ('lib/pdf')
	- Fonts      ('lib/fonts')
	- XSL        ('lib/xsl')

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

	def __init__( self, library="", name="LibraryServer", cache=None,
			commands=dict(), minify=False, compress=False, cacheAggregates=True,
			cacheDuration=24*60*60, prefix=None ):
		Component.__init__(self, name=name, prefix=prefix)
		self.library  = library
		self.cache    = cache
		self.minify   = minify
		self.compress = compress
		self.commands = dict(sugar="sugar")
		self.commands.update(commands)
		self.cacheAggregates = cacheAggregates
		self.cacheDuration   = cacheDuration

	def start( self ):
		self.library  = self.library or self.app.config("library.path")

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

	@on(GET_HEAD="lib/fonts/{path:rest}")
	def getFonts( self, request, path ):
		if path.endswith(".css"):
			return self._getFromLibrary(request, "fonts", path, "text/css; charset=utf-8")
		else:
			return request.respondFile(os.path.join(self.library, "fonts", path)).cache(seconds=self.cacheDuration)

	@on(GET_HEAD="lib/images/{image:([\w\-_]+/)*[\w\-_]+(\.png|\.gif|\.jpg|\.ico|\.svg)*}")
	def getImage( self, request, image ):
		content_type = self.CONTENT_TYPES.get(image.rsplit(".",1)[-1])
		# NOTE: I had to add the content type as not adding it blocks the system in production in some circumstances...
		return request.respondFile(self._guessPath("images", image, extensions=(".png", ".gif", ".jpg", ".ico", ".svg")), content_type).cache(seconds=self.cacheDuration)

	@on(GET_HEAD="lib/pdf/{script:[^/]+\.pdf}")
	def getPDF( self, request, script ):
		return request.respondFile(os.path.join(self.library, "pdf", script)).cache(seconds=self.cacheDuration)

	@on(GET_HEAD="lib/{script:[^/]+\.mf}")
	def getManifest( self, request, script ):
		return request.respondFile(os.path.join(self.library,script), "text/cache-manifest").cache(seconds=self.cacheDuration)

	@on(GET_HEAD="lib/css/{paths:rest}")
	def getCSS( self, request, paths ):
		return self._getFromLibrary(request, "css", paths, "text/css; charset=utf-8")

	@on(GET_HEAD="lib/ccss/{paths:rest}")
	def getCCSS( self, request, paths ):
		return self._getFromLibrary(request, "ccss", paths, "text/css; charset=utf-8")

	@on(GET_HEAD="lib/pcss/{paths:rest}")
	def getPCSS( self, request, paths ):
		return self._getFromLibrary(request, "pcss", paths, "text/css; charset=utf-8")

	@on(GET_HEAD="lib/xsl/{paths:rest}")
	def getXSL( self, request, paths ):
		return self._getFromLibrary(request, "xsl", paths, "text/xsl; charset=utf-8")

	@on(GET_HEAD="lib/{prefix:(js|sjs)}/{paths:rest}")
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
					if not os.path.exists(path):
						return request.notFound()
					data = self._processPath(path)
					if data is None:
						raise Exception("Processing path {0} returned None".format(path))
					self._toCache(path, data)
				else:
					data = self._fromCache(path)
				# FIXME: Maybe we should do UTF8?
				result.append(ensureBytes(data))
			response_data = b"\n".join(result)
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
		elif path.endswith(".pcss"): return self._processPCSS(path)
		elif path.endswith(".css"):  return self._processCSS(path)
		elif path.endswith(".paml"): return self._processPAML(path)
		elif path.endswith(".xsl"):  return self._processXSL(path)
		else: raise Exception("Format not supported: " + path)

	def _processCSS( self, path ):
		"""Processes a CSS file, minifyiing it if `cssmin` is installed."""
		data = self.app.load(path)
		if self.minify and cssmin: data = cssmin.cssmin(data)
		return data

	def _processCCSS( self, path ):
		"""Processes a CCSS file, minifying it if `cssmin` is installed.
		Requires `clevercss`"""
		data = self.app.load(path)
		data = clevercss.convert(data)
		if self.minify and cssmin: data = cssmin.cssmin(data)
		return data

	def _processPCSS( self, path ):
		"""Processes a PCSS file, minifying it if `cssmin` is installed.
		Requires `clevercss`"""
		data   = None
		tries  = 0
		# TODO: This does not work yet, but it is the best for an application
		# Right now, we default to piping
		# data = self.app.load(path)
		# data = pythoniccss.convert(data)
		while (not data) and tries < 3:
			command = "%s %s" % (self.commands.get("pythoniccss", "pythoniccss"), path)
			cmd     = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
			data    = cmd.stdout.read()
			tries  += 1
			cmd.wait()
		if data:
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

	def _processPAML( self, path ):
		"""Processes a JS file, minifying it if `jsmin` is installed."""
		data = self.app.load(path)
		return paml.process(data)

	def _processXSL( self, path ):
		"""Processes a JS file, minifying it if `jsmin` is installed."""
		return self.app.load(path)

	def _processJS( self, path ):
		"""Processes a JS file, minifying it if `jsmin` is installed."""
		data = self.app.load(path)
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
