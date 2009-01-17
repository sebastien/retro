#!/usr/bin/python
# Encoding: ISO-8859-1
# vim: tw=80 ts=4 sw=4 fenc=latin-1 noet
# -----------------------------------------------------------------------------
# Project           :   Railways                   <http://www.ivy.fr/railways>
# -----------------------------------------------------------------------------
# Author            :   Sebastien Pierre                     <sebastien@ivy.fr>
# License           :   Revised BSD License
# -----------------------------------------------------------------------------
# Creation date     :   20-Mar-2005
# Last mod.         :   17-Jan-2008
# -----------------------------------------------------------------------------

import sys, os
from distutils.core import setup

VERSION     = os.popen("""grep __version__ Sources/railways/__init__.py | head -n1 | cut -d'"' -f2""").read().split("\n")[0]
SUMMARY     = "Lightweight Declarative Web Toolkit"
DESCRIPTION = """\
Railways is a lightweight declarative web toolkit designed to make it easier to
develop web services and Web applications in Python. Railways uses WSGI and
provide a set of decorators that make it very easy to turn your existing code
into a web application or to write new ones.
"""

# ------------------------------------------------------------------------------
#
# SETUP DECLARATION
#
# ------------------------------------------------------------------------------

setup(
    name        = "Railways",
    version     = VERSION,
    author      = "Sebastien Pierre", author_email = "sebastien@type-z.org",
    description = SUMMARY, long_description = DESCRIPTION,
    license     = "Revised BSD License",
    keywords    = "web, lightweight, framework, http, ajax, declarative",
    url         = "http://www.github.com/sebastien/railways",
    download_url= "http://www.ivy.fr/railways/railways-%s.tar.gz" % (VERSION) ,
    package_dir = { "": "Sources" },
    packages    = ["railways"],
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
# EOF
