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
# Last mod  : 03-Jul-2007
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

	def __init__( self, proxyTo, prefix="/" ):
		# TODO: Add headers processing here
		"""Creates a new proxy that will proxy to the URL indicated by
		'proxyTo'."""
		Component.__init__(self, name="Proxy")
		self._proxyTo = proxyTo
		self.PREFIX   = prefix

	def start( self ):
		"""Starts the component, checking if the 'curl' utility is available."""
		if not self.hasCurl():
			raise Exception("Curl is required.")

	@on(GET="/{rest:rest}", priority="10")
	def proxyGet( self, request, rest ):
		rest   = request.uri()[len("/ojibwe/api/"):]
		result, ctype, code = self._curl(self._proxyTo, "GET", rest)
		# TODO: Add headers processing here
		return request.respond(content=result,headers=[("Content-Type",ctype)],status=code)

	@on(POST="/{rest:rest}", priority="10")
	def proxyPost( self, request, rest ):
		rest   = request.uri()[len("/ojibwe/api/"):]
		result, ctype, code = self._curl(self._proxyTo, "POST", rest, body=request.body())
		# TODO: Add headers processing here
		return request.respond(content=result,headers=[("Content-Type",ctype)],status=code)

	# CURL WRAPPER
	# ____________________________________________________________________________

	def hasCurl( self ):
		"""Tells if the 'curl' command-line utility is avialable."""
		result = os.popen("curl --version").read() or ""
		return result.startswith("curl") and result.find("http") != -1

	def _curl( self, server, method, url, body="" ):
		"""This function uses os.popen to communicate with the 'curl'
		command-line client and to GET or POST requests to the given server."""
		if method == "GET":
			result = os.popen("curl -s -w '\n\n%{content_type}\n\n%{http_code}'" +
			" '%s/%s'" % (server, url)).read()
		else:
			result = os.popen("curl -s -w '\n\n%{content_type}\n\n%{http_code}'" +
			" '%s/%s' -d '%s'" % (server, url, body)).read()
		code_start  = result.rfind("\n\n")
		code        = result[code_start+2:]
		result      = result[:code_start]
		ctype_start = result.rfind("\n\n")
		ctype       = result[ctype_start+2:]
		result      = result[:ctype_start]
		return result, ctype, code
# EOF
