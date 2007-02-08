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
# Last mod  : 07-Nov-2006
# -----------------------------------------------------------------------------

__doc__ = """
This script starts a Railways/Py web server that provides test data to run the
test cases provided by in this distribution."""

import os, sys, time, webbrowser
from os.path import abspath, dirname, join

# Directories for Railways client and server distributions
CLIENT_DIR = abspath(join(dirname(abspath(__file__)), ".."))
SERVER_DIR = join(CLIENT_DIR, "Server", "Reference")

# This is the temporary Ojibwe API server (it will change)
OJIBWE_API_SERVER  = "http://aj/api"
ACCOUNT_API_SERVER = "http://localhost:8000/api"
PORT               = 8080

# We are now ready to proceed with the importation
try:
	from railways import *
except ImportError, e:
	server_path = join(SERVER_DIR, "Sources")
	if os.environ.has_key("PYTHONPATH"):
		os.environ["PYTHONPATH"] = server_path + ":" + os.environ["PYTHONPATH"]
	else:
		os.environ["PYTHONPATH"] = server_path
	sys.path.insert(0, server_path)
	from railways import *

# ------------------------------------------------------------------------------
#
# PROXY CLASS
#
# ------------------------------------------------------------------------------

class Main(Component):
	"""This is the main component of the Proxy. It basically provided a wrapper
	around the 'curl' command line application that allows basic proxying of
	requests, and serving of local files."""
	
	def start( self ):
		"""Starts a webbrowser pointing at this server, and also starts the 
		Accounts example."""
		if not self.hasCurl():
			raise Exception("Curl is required.")
		def helper():
			time.sleep(1)
			webbrowser.open("http://localhost:%s" % (PORT))
			accounts_example = "%s/Examples/Accounts/Accounts.py" % (SERVER_DIR)
			if not os.path.exists(accounts_example):
				raise Exception("Unable to locate Railways/Py Accounts example:"
				+ " was expected at " + accounts_example)
			os.system("python %s" % ( accounts_example))
		thread.start_new_thread(helper, ())

	@on(GET="/")
	def main( self, request ):
		return self.local(request, "index.html")

	@on(GET="/ojibwe/api/{rest:rest}", priority="10")
	def ojapi( self, request, rest ):
		rest   = request.uri()[len("/ojibwe/api/"):]
		result, ctype, code = self._curl(OJIBWE_API_SERVER, "GET", rest)
		return request.respond(result,[("Content-Type",ctype)],code)

	@on(POST="/ojibwe/api/{rest:rest}", priority="10")
	def ojapiPost( self, request, rest ):
		rest   = request.uri()[len("/ojibwe/api/"):]
		result, ctype, code = self._curl(OJIBWE_API_SERVER, "POST", rest, body=request.body())
		return request.respond(result,[("Content-Type",ctype)],code)

	@on(GET="/account/api/{rest:rest}", priority="10")
	def acapi( self, request, rest ):
		rest   = request.uri()[len("/account/api/"):]
		result, ctype, code = self._curl(ACCOUNT_API_SERVER, "GET", rest)
		return request.respond(result,[("Content-Type",ctype)],code)

	@on(POST="/account/api/{rest:rest}", priority="10")
	def acapiPost( self, request, rest ):
		rest   = request.uri()[len("/account/api/"):]
		result, ctype, code = self._curl(ACCOUNT_API_SERVER, "POST", rest, body=request.body())
		return request.respond(result,[("Content-Type",ctype)],code)
	
	@on(GET="/delay/{duration:int}/{rest:rest}", priority="10")
	def delayedGet( self, request, duration, rest ):
		time.sleep(duration)
		return self.local(request, rest)

	# RESOURCES
	# ____________________________________________________________________________

	@on(GET_POST="/{path:any}")
	def local( self, request, path ):
		"""Serves the files located in the `Library` grand parent directory."""
		try:
			return request.localfile(self.app().localPath(path))
		except:
			return request.respond(status=404)
		
	# CURL WRAPPER
	# ____________________________________________________________________________
	
	def hasCurl( self ):
		result = os.popen("curl --version").read() or ""
		return result.startswith("curl") and result.find("http") != -1
		
	def _curl( self, server, method, url, body="" ):
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
		print "==================================="
		print "RESPONSE:", url
		print result
		return result, ctype, code

if __name__ == "__main__":
	main = Main()
	main.start()
	run(
		app        = Application(main),
		name       = os.path.splitext(os.path.basename(__file__))[1],
		method     = STANDALONE,
		sessions   = False,
		port       = PORT
	)

# EOF
