#!/usr/bin/env python
# Encoding: iso-8859-1
# -----------------------------------------------------------------------------
# Project   : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                            <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 12-Apr-2006
# Last mod  : 08-Jan-2016
# -----------------------------------------------------------------------------

import os, sys, time
from os.path import abspath, dirname, join
from retro import *
from retro.wsgi import SERVER_ERROR_CSS

DEFAULT_PORT = 8000

# ------------------------------------------------------------------------------
#
# PROXY COMPONENT
#
# ------------------------------------------------------------------------------

class Proxy:
	"""A basic (forwarding) proxy implementation that is used by the
	ProxyService in this module."""

	THROTTLING = 0

	def requestAsString( self, method, server, port, uri, headers, body ):
		headers = ("%s: %s" % (h[0], h[1]) for h in list(headers.items()) if h[1] != None)
		return (
			"%s %s:%s %s\n"
			"%s\n\n"
			"%s\n\n"
		) % (method, server, port, uri, "\n".join(headers), body)

	def filterHeaders( self, headers ):
		res = {}
		for name, value in list(headers.items()):
			if value != None:
				res[name] = value
		return res

	def proxyGET( self, request, server, port, uri, parameters ):
		#print self.requestAsString(request.method(), server, port, uri, request.headers, request.body())
		status, headers, body = self.httpRequest(server, port, "GET", uri, headers=self.filterHeaders(request.headers))
		return request.respond(content=body,headers=headers,status=status)

	def proxyPOST( self, request, server, port, uri ):
		#print self.requestAsString(request.method(), server, port, uri, request.headers, request.body())
		status, headers, body = self.httpRequest(server, port, "POST", uri, body=request.body(), headers=self.filterHeaders(request.headers))
		return request.respond(content=body,headers=headers,status=status)

	def proxyPUT( self, request, server, port, uri ):
		#print self.requestAsString(request.method(), server, port, uri, request.headers, request.body())
		status, headers, body = self.httpRequest(server, port, "PUT", uri, body=request.body(), headers=self.filterHeaders(request.headers))
		return request.respond(content=body,headers=headers,status=status)

	def proxyDELETE( self, request, server, port, uri ):
		#print self.requestAsString(request.method(), server, port, uri, request.headers, request.body())
		status, headers, body = self.httpRequest(server, port, "DELETE", uri, body=request.body(), headers=self.filterHeaders(request.headers))
		return request.respond(content=body,headers=headers,status=status)

	def hasBackend( self ):
		return True

	def httpRequest( self, server, port, method, url, body="", headers=None ):
		# NOTE: This is not fast at all, but it works!
		import wwwclient, wwwclient.defaultclient
		s    = wwwclient.Session(client=wwwclient.defaultclient.HTTPClient)
		url  = "http://{0}:{1}{2}".format(server, port, url)
		print ("[PROXY] {0}".format(url))
		t    = getattr(s,method.lower())(url)
		data = t.data()
		if self.THROTTLING > 0:
			bytes_per_second = int(self.THROTTLING * 1000.0)
			def throttling_wrapper():
				i      = 0
				while i < len(data):
					if i > 0:
						time.sleep(1)
					j = min(len(data), i + bytes_per_second)
					yield data[i:j]
					i = j
			res = throttling_wrapper()
		return 200, t.headers, data

	# NOTE: This does not  seem to work properly..., so disabled for now
	#def _httpRequest( self, server, port, method, url, body="", headers=None ):
	#	import httplib
	#	conn = httplib.HTTPConnection(server, int(port))
	#	conn.request(method, url, body, headers or {})
	#	print "[PROXY] {0} {1}:{2}{3}".format(method, server, port, url)
	#	resp = conn.getresponse()
	#	data = resp.read()
	#	res  = data
	#	if self.THROTTLING > 0:
	#		bytes_per_second = int(self.THROTTLING * 1000.0)
	#		def throttling_wrapper():
	#			i      = 0
	#			while i < len(data):
	#				if i > 0:
	#					time.sleep(1)
	#				j = min(len(data), i + bytes_per_second)
	#				yield data[i:j]
	#				i = j
	#		res = throttling_wrapper()
	#	return resp.status, resp.getheaders(), res

# FIXME: Use Proxy properly
class ProxyService(Component, Proxy):
	"""This is the main component of the Proxy. It basically provided a wrapper
	around the 'curl' command line application that allows basic proxying of
	requests, and serving of local files."""

	def __init__( self, proxyTo, prefix="/", user=None, password=None, throttling=0):
		# TODO: Add headers processing here
		"""Creates a new proxy that will proxy to the URL indicated by
		'proxyTo'."""
		Component.__init__(self, name="Proxy")
		# NOTE: parseURL is actually urllib3.util.parse_url, which is much
		# better than urlparse.urlparse.
		url          = parseURL(proxyTo)
		self._scheme = url.scheme or "http"
		self._host   = url.host   or "localhost"
		self._port   = url.port   or 80
		self._uri    = url.path   or "/"
		self.PREFIX  = prefix
		self.user    = user
		self.THROTTLING = int(throttling)
		if user and password: self.user += ":" + password

	@on(GET="?{parameters}", priority="10")
	@on(GET="{rest:rest}?{parameters}", priority="10")
	def proxyGet( self, request, rest=None, parameters=None ):
		return self._proxy(request, "GET", rest, parameters)

	@on(POST="?{parameters}", priority="10")
	@on(POST="{rest:rest}?{parameters}", priority="10")
	def proxyPost( self, request, rest=None, parameters=None ):
		return self._proxy(request, "POST", rest, parameters)

	@on(PUT="?{parameters}", priority="10")
	@on(PUT="{rest:rest}?{parameters}", priority="10")
	def proxyPut( self, request, rest=None, parameters=None ):
		return self._proxy(request, "PUT", rest, parameters)

	@on(DELETE="?{parameters}", priority="10")
	@on(DELETE="{rest:rest}?{parameters}", priority="10")
	def proxyDelete( self, request, rest=None, parameters=None):
		return self._proxy(request, "DELETE", rest, parameters)

	def _proxy( self, request, method, rest, parameters ):
		rest     = rest or ""
		dest_uri = self._uri + rest
		while dest_uri.endswith("//"): dest_uri=dest_uri[:-1]
		# We get the parameters as-is from the request URI (parameters is ignored
		uri_params = request.uri().split("?",1)
		if len(uri_params) == 2:
			if not dest_uri.endswith("?"): dest_uri += "?"
			dest_uri += uri_params[1]
		status, headers, body = self.httpRequest(self._host, self._port, method, dest_uri, body=request.body(), headers=self.filterHeaders(request.headers))
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
		wwwclient.browse.Session(self._proxyTo, client=wwwclient.curlclient.HTTPClient).get(uri)
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

def createProxies( args, options=None ):
	"""Create proxy components from a list of arguments like

	>    {prefix}={url}
	>    {prefix}={user}:{password}@{url}
	"""
	components = []
	options    = options or {}
	throttling = int(options.get("throttling") or DEFAULT_PORT)
	for arg in args:
		prefix, url = arg.split("=",1)
		if url.find("@") != -1:
			user, url = url.split("@",1)
			user, passwd = user.split(":",1)
			print("Proxying %s:%s@%s as %s" % (user, passwd, url, prefix))
		else:
			user, passwd = None, None
			print("Proxying %s as %s" % (url, prefix))
		components.append(ProxyService(url, prefix, user=user, password=passwd, throttling=throttling))
	return components


def run( args ):
	if type(args) not in (type([]), type(())): args = [args]
	from optparse import OptionParser
	# We create the parse and register the options
	oparser = OptionParser(version="Retro[+proxy]")
	oparser.add_option("-p", "--port", action="store", dest="port",
		help=OPT_PORT, default=DEFAULT_PORT)
	oparser.add_option("-f", "--files", action="store_true", dest="files",
		help="Server local files", default=None)
	oparser.add_option("-t", "--throttle", action="store", dest="throttling",
		help="Throttles connection speed (in Kbytes/second)", default=0)
	# We parse the options and arguments
	options, args = oparser.parse_args(args=args)
	if len(args) == 0:
		print("The URL to proxy is expected as first argument")
		return False
	components = createProxies(args, dict(port=options.port,throttling=options.throttling,files=options.files))
	if options.files:
		import retro.contrib.localfiles
		print("Serving local files...")
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

# EOF - vim: tw=80 ts=4 sw=4 noet
