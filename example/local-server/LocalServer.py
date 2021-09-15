#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet
# -----------------------------------------------------------------------------
# Project   : Retro - Declarative Python Web Framework
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 12-Apr-2006
# Last mod  : 05-Jan-2007
# -----------------------------------------------------------------------------

__doc__ = """
This script starts a Retro/Py web server that acts as a local proxy to the
current filesystem or given directory ."""

import os
import sys
import StringIO
from retro import *
from retro.contrib.localfiles import LocalFiles

PORT = 8080

# ------------------------------------------------------------------------------
#
# LOCALFILES SUBCLASS
#
# ------------------------------------------------------------------------------


class Main(LocalFiles):
    pass

# ------------------------------------------------------------------------------
#
# Main
#
# ------------------------------------------------------------------------------


if __name__ == "__main__":
    main = Main()
    run(
        app=Application(main),
        name=os.path.splitext(os.path.basename(__file__))[1],
        method=STANDALONE,
        sessions=False,
        port=PORT
    )

# EOF
