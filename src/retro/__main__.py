#!/usr/bin/env python
# encoding=utf8

import sys
import retro
from   retro.contrib.localfiles import LocalFiles

# -----------------------------------------------------------------------------
#
# APPLICATION
#
# -----------------------------------------------------------------------------

def application():
	return retro.Application((
		LocalFiles()
	))

def run(args=None):
	if args is None: args = sys.argv[1:]
	import argparse
	# We create the parse and register the options
	p = argparse.ArgumentParser(prog="retro", description=(
		"Development webserver that allows to browse local files"
	))
	p.add_argument("-p", "--port", dest="port", default=8000,
		help="Sets the port to which the webserver will be bound")
	p.add_argument("-D", "--def", action="append", dest="defs",
		help="Adds a variable as NAME=VALUE to the runtime environment of the web server")
	args = p.parse_args(args)
	defs = dict((k.strip(), v.strip()) for k,v in (_.split("=",1) for _ in args.defs)) if args.defs else {}
	try:
		import reporter
	except ImportError as e:
		import logging
		logging.basicConfig(level=logging.INFO)
	retro.run(application(), method=retro.AIO, port=args.port)

if __name__ == "__main__":
	run()

# EOF - vim: ts=4 sw=4 noet
