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
# Last mod.         :   09-Nov-2006
# -----------------------------------------------------------------------------

import sys ; sys.path.insert(0, "Sources")
from tahchee import main
from distutils.core import setup

SUMMARY     = "Declarative Web Framework"
DESCRIPTION = """\
\
"""
# ------------------------------------------------------------------------------
#
# SETUP DECLARATION
#
# ------------------------------------------------------------------------------

setup(
    name        = "Railways",
    version     = main.__version__,
    author      = "Sebastien Pierre", author_email = "sebastien@type-z.org",
    description = SUMMARY, long_description = DESCRIPTION,
    license     = "Revised BSD License",
    keywords    = "web, framework, http, ajax, declarative",
    url         = "http://www.ivy.fr/railways",
    download_url= "http://www.ivy.fr/railways/railways-%s.tar.gz" % (main.__version__) ,
    package_dir = { "": "Sources" },
    packages    = ["railways", "prevail"],
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
