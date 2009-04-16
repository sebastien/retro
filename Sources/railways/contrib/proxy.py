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
# Last mod  : 16-Apr-2009
# -----------------------------------------------------------------------------

import os, sys, time, webbrowser
from os.path import abspath, dirname, join
from railways import *
from railways.wsgi import SERVER_ERROR_CSS

# ------------------------------------------------------------------------------
#
# PROXY COMPONENT
#
# ------------------------------------------------------------------------------

class Proxy(Component):
	"""This is the main component of the Proxy. It basically provided a wrapper
	around the 'curl' command line application that allows basic proxying of
	requests, and serving of local files."""

	def __init__( self, proxyTo, prefix="/", user=None, password=None ):
		# TODO: Add headers processing here
		"""Creates a new proxy that will proxy to the URL indicated by
		'proxyTo'."""
		Component.__init__(self, name="Proxy")
		self._proxyTo = proxyTo
		self.PREFIX   = prefix
		self.user     = user
		if user and password: self.user += ":" + password

	def start( self ):
		"""Starts the component, checking if the 'curl' utility is available."""
		if not self.hasCurl():
			raise Exception("Curl is required.")

	@on(GET="/{rest:rest}?{parameters}", priority="10")
	def proxyGet( self, request, rest, parameters ):
		uri = request.uri() ; i = uri.find(rest) ; assert i >= 0 ; uri = uri[i:]
		result, ctype, code = self._curl(self._proxyTo, "GET", uri)
		# TODO: Add headers processing here
		return request.respond(content=result,headers=[("Content-Type",ctype)],status=code)

	@on(POST="/{rest:rest}", priority="10")
	def proxyPost( self, request, rest ):
		uri = request.uri() ; i = uri.find(rest) ; assert i >= 0 ; uri = uri[i:]
		result, ctype, code = self._curl(self._proxyTo, "POST", uri, body=request.body())
		# TODO: Add headers processing here
		return request.respond(content=result,headers=[("Content-Type",ctype)],status=code)

	# CURL WRAPPER
	# ____________________________________________________________________________

	def hasCurl( self ):
		"""Tells if the 'curl' command-line utility is avialable."""
		result = os.popen("curl --version").read() or ""
		return result.startswith("curl") and result.find("http") != -1

	def _curlCommand( self ):
		base = "curl "
		if self.user: base += " --anyauth -u%s " % (self.user)
		base += " -s -w"
		return base

	def _curl( self, server, method, url, body="" ):
		"""This function uses os.popen to communicate with the 'curl'
		command-line client and to GET or POST requests to the given server."""
		c = self._curlCommand()
		if method == "GET":
			command = c + "'\n\n%{content_type}\n\n%{http_code}'" + " '%s/%s'" % (server, url)
			result = os.popen(command).read()
		else:
			command = c + "'\n\n%{content_type}\n\n%{http_code}'" + " '%s/%s' -d '%s'" % (server, url, body)
			result = os.popen(command).read()
		code_start  = result.rfind("\n\n")
		code        = result[code_start+2:]
		result      = result[:code_start]
		ctype_start = result.rfind("\n\n")
		ctype       = result[ctype_start+2:]
		result      = result[:ctype_start]
		return result, ctype, code

# ------------------------------------------------------------------------------
#
# WWW-CLIENT PROXY COMPONENT
#
# ------------------------------------------------------------------------------

class WWWClientProxy(Proxy):

	def start( self ):
		"""Starts the component, checking if the 'curl' utility is available."""
		if not self.hasCurl():
			raise Exception("wwwclient is required.")

	@on(GET="/{rest:rest}?{parameters}", priority="10")
	def proxyGet( self, request, rest, parameters ):
		uri = request.uri() ; i = uri.find(rest) ; assert i >= 0 ; uri = uri[i:]
		wwwclient.browse.Session(self._proxyTo).get(uri)
		# TODO: Add headers processing here
		return request.respond(content=result,headers=[("Content-Type",ctype)],status=code)

	@on(POST="/{rest:rest}", priority="10")
	def proxyPost( self, request, rest ):
		uri = request.uri() ; i = uri.find(rest) ; assert i >= 0 ; uri = uri[i:]
		result, ctype, code = self._curl(self._proxyTo, "POST", uri, body=request.body())
		# TODO: Add headers processing here
		return request.respond(content=result,headers=[("Content-Type",ctype)],status=code)

	# CURL WRAPPER
	# ____________________________________________________________________________

	def hasWWWClient( self ):
		"""Tells if the 'curl' command-line utility is avialable."""
		import wwwclient
		return wwwclient

	def _curlCommand( self ):
		base = "curl "
		if self.user: base += " --anyauth -u%s " % (self.user)
		base += " -s -w"
		return base

	def _curl( self, server, method, url, body="" ):
		"""This function uses os.popen to communicate with the 'curl'
		command-line client and to GET or POST requests to the given server."""
		c = self._curlCommand()
		if method == "GET":
			command = c + "'\n\n%{content_type}\n\n%{http_code}'" + " '%s/%s'" % (server, url)
			result = os.popen(command).read()
		else:
			command = c + "'\n\n%{content_type}\n\n%{http_code}'" + " '%s/%s' -d '%s'" % (server, url, body)
			result = os.popen(command).read()
		code_start  = result.rfind("\n\n")
		code        = result[code_start+2:]
		result      = result[:code_start]
		ctype_start = result.rfind("\n\n")
		ctype       = result[ctype_start+2:]
		result      = result[:ctype_start]
		return result, ctype, code

# ------------------------------------------------------------------------------
#
# MAIN
#
# ------------------------------------------------------------------------------

def createProxies( args ):
	"""Create proxy components from a list of arguments like
	
	>    {prefix}={url}
	>    {prefix}={user}:{password}@{url}
	"""

	components = []
	for arg in args:
		prefix, url = arg.split("=",1)
		if url.find("@") != -1:
			user, url = url.split("@",1)
			user, passwd = user.split(":",1)
			print "Proxying %s as  %s:%s@%s" % (prefix, user, passwd, url)
		else:
			user, passwd = None, None
			print "Proxying %s as %s" % (prefix, url)
		components.append(Proxy(url, prefix, user=user, password=passwd))
	return components


def run( args ):
	if type(args) not in (type([]), type(())): args = [args]
	from optparse import OptionParser
	# We create the parse and register the options
	oparser = OptionParser(version="Railways[+proxy]")
	oparser.add_option("-p", "--port", action="store", dest="port",
		help=OPT_PORT, default="8000")
	oparser.add_option("-f", "--files", action="store_true", dest="files",
		help="Server local files", default=None)
	# We parse the options and arguments
	options, args = oparser.parse_args(args=args)
	if len(args) == 0:
		print "The URL to proxy is expected as first argument"
		return False
	components = self.createProxies(args)
	if options.files:
		import railways.contrib.localfiles
		print "Serving local files..."
		components.append(railways.contrib.localfiles.LocalFiles())
	app    = Application(components=components)
	import railways
	return railways.run(app=app,sessions=False,port=int(options.port))

# -----------------------------------------------------------------------------
#
# Main
#
# -----------------------------------------------------------------------------

if __name__ == "__main__":
	run(sys.argv[1:])

# EOF
