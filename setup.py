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
# Last mod.         :   21-Nov-2007
# -----------------------------------------------------------------------------

import sys
from distutils.core import setup

VERSION     = "0.4.1"
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
    keywords    = "web, framework, http, ajax, declarative",
    url         = "http://www.ivy.fr/railways",
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
