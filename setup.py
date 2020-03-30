#!/usr/bin/python
# Encoding: utf8
# -----------------------------------------------------------------------------
# Project           :   Retro             ttp://www.github.com/sebastien/retro>
# -----------------------------------------------------------------------------
# Author            :   Sebastien Pierre                  <sebastien@ffctn.com>
# License           :   Revised BSD License
# -----------------------------------------------------------------------------
# Creation date     :   20-Mar-2005
# Last mod.         :   17-Jan-2008
# -----------------------------------------------------------------------------

import sys, os
from distutils.core import setup

VERSION     = os.popen("""grep __version__ src/retro/__init__.py | head -n1 | cut -d'"' -f2""").read().split("\n")[0]
SUMMARY     = "Lightweight Declarative Web Toolkit"
DESCRIPTION = """\
Retro is a lightweight declarative web toolkit designed to make it easier to
develop web services and Web applications in Python. Retro uses WSGI and
provide a set of decorators that make it very easy to turn your existing code
into a web application or to write new ones.
"""

# ------------------------------------------------------------------------------
#
# SETUP DECLARATION
#
# ------------------------------------------------------------------------------

setup(
	name        = "Retro",
	version     = VERSION,
	author      = "Sebastien Pierre", author_email = "sebastien.pierre@gmail.com",
	description = SUMMARY, long_description = DESCRIPTION,
	license     = "Revised BSD License",
	keywords    = "web lightweight framework http declarative".split(),
	url         = "http://www.github.com/sebastien/retro",
	download_url= "http://github.com/sebastien/retro/tarball/%s" % (VERSION) ,
	package_dir = { "": "src" },
	packages    = ["retro", "retro.contrib"],
	classifiers = [
		"Development Status :: 4 - Beta",
		"Environment :: Web Environment",
		"Intended Audience :: Developers",
		"Intended Audience :: Information Technology",
		"License :: OSI Approved :: BSD License",
		"Natural Language :: English",
		"Topic :: Internet :: WWW/HTTP",
		"Operating System :: POSIX",
		"Operating System :: Microsoft :: Windows",
		"Programming Language :: Python",
	]
)
# EOF - vim: tw=80 ts=4 sw=4 fenc=latin-1 noet
