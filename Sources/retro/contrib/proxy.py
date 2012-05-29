#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet
# -----------------------------------------------------------------------------
# Project   : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ivy.fr>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 12-Apr-2006
# Last mod  : 17-Sep-2010
# -----------------------------------------------------------------------------

import os, sys, time
from os.path import abspath, dirname, join
from retro import *
from retro.wsgi import SERVER_ERROR_CSS

# ------------------------------------------------------------------------------
#
# PROXY COMPONENT
#
# ------------------------------------------------------------------------------

class Proxy:

	def requestAsString( self, method, server, port, uri, headers, body ):
		headers = ("%s: %s" % (h[0], h[1]) for h in headers.items() if h[1] != None)
		return (
			"%s %s:%s %s\n" 
			"%s\n\n" 
			"%s\n\n" 
		) % (method, server, port, uri, "\n".join(headers), body)

	def filterHeaders( self, headers ):
		res = {}
		for name, value in headers.items():
			if value != None:
				res[name] = value
		return res

	def proxyGET( self, request, server, port, uri, parameters ):
		#print self.requestAsString(request.method(), server, port, uri, request.headers(), request.body())
		status, headers, body = self.httpRequest(server, port, "GET", uri, headers=self.filterHeaders(request.headers()))
		return request.respond(content=body,headers=headers,status=status)

	def proxyPOST( self, request, server, port, uri ):
		#print self.requestAsString(request.method(), server, port, uri, request.headers(), request.body())
		status, headers, body = self.httpRequest(server, port, "POST", uri, body=request.body(), headers=self.filterHeaders(request.headers()))
		return request.respond(content=body,headers=headers,status=status)

	def proxyPUT( self, request, server, port, uri ):
		#print self.requestAsString(request.method(), server, port, uri, request.headers(), request.body())
		status, headers, body = self.httpRequest(server, port, "PUT", uri, body=request.body(), headers=self.filterHeaders(request.headers()))
		return request.respond(content=body,headers=headers,status=status)

	def proxyDELETE( self, request, server, port, uri ):
		#print self.requestAsString(request.method(), server, port, uri, request.headers(), request.body())
		status, headers, body = self.httpRequest(server, port, "DELETE", uri, body=request.body(), headers=self.filterHeaders(request.headers()))
		return request.respond(content=body,headers=headers,status=status)

	def hasBackend( self ):
		return True
	
	def httpRequest( self, server, port, method, url, body="", headers=None ):
		import httplib
		conn = httplib.HTTPConnection(server, int(port))
		conn.request(method, url, body, headers or {})
		resp = conn.getresponse()
		res  = resp.read()
		return resp.status, resp.getheaders(), res

# FIXME: Use Proxy properly
class ProxyService(Component, Proxy):
	"""This is the main component of the Proxy. It basically provided a wrapper
	around the 'curl' command line application that allows basic proxying of
	requests, and serving of local files."""

	def __init__( self, proxyTo, prefix="/", user=None, password=None ):
		# TODO: Add headers processing here
		"""Creates a new proxy that will proxy to the URL indicated by
		'proxyTo'."""
		Component.__init__(self, name="Proxy")
		host, port = proxyTo.split(":", 1)
		port, uri  = port.split("/",    1)
		self._host  = host
		self._port  = port
		self._uri   = "/" + uri
		self.PREFIX = prefix
		self.user   = user
		if user and password: self.user += ":" + password

	@on(GET="/{rest:rest}?{parameters}", priority="10")
	def proxyGet( self, request, rest, parameters ):
		return self._proxy(request, "GET", rest, parameters)

	@on(POST="/{rest:rest}?{parameters}", priority="10")
	def proxyPost( self, request, rest, parameters ):
		return self._proxy(request, "POST", rest, parameters)

	@on(PUT="/{rest:rest}?{parameters}", priority="10")
	def proxyPut( self, request, rest, parameters ):
		return self._proxy(request, "PUT", rest, parameters)

	@on(DELETE="/{rest:rest}?{parameters}", priority="10")
	def proxyDelete( self, request, rest, parameters ):
		return self._proxy(request, "DELETE", rest, parameters)
	
	def _proxy( self, request, method, rest, parameters ):
		uri = request.uri() ; i = uri.find(rest) ; assert i >= 0 ; uri = uri[i:]
		status, headers, body = self.httpRequest(self._host, self._port, method, self._uri + uri, body=request.body(), headers=self.filterHeaders(request.headers()))
		# TODO: We have a redirect, so we have to rewrite it
		if status == 302:
			pass
		return request.respond(content=body,headers=headers,status=status)

# ------------------------------------------------------------------------------
#
# WWW-CLIENT PROXY COMPONENT
#
# ------------------------------------------------------------------------------

class WWWClientProxy(ProxyService):

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
		components.append(ProxyService(url, prefix, user=user, password=passwd))
	return components


def run( args ):
	if type(args) not in (type([]), type(())): args = [args]
	from optparse import OptionParser
	# We create the parse and register the options
	oparser = OptionParser(version="Retro[+proxy]")
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
		import retro.contrib.localfiles
		print "Serving local files..."
		components.append(retro.contrib.localfiles.LocalFiles())
	app    = Application(components=components)
	import retro
	return retro.run(app=app,sessions=False,port=int(options.port))

# -----------------------------------------------------------------------------
#
# Main
#
# -----------------------------------------------------------------------------

if __name__ == "__main__":
	run(sys.argv[1:])

# EOF
