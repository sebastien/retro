# -----------------------------------------------------------------------------
# Project   : Retro - Declarative Python Web Framework
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 14-Jun-2011
# Last mod  : 14-Jun-2011
# -----------------------------------------------------------------------------

__doc__ = """
To run this service under GUnicorn, cd into the directory that contains this
file and type:

>	gunicorn -kevenltet GUnicornService

"""

import os
import sys
import StringIO
from retro import *
from retro.contrib.localfiles import LocalFiles

# ------------------------------------------------------------------------------
#
# LOCALFILES SUBCLASS
#
# ------------------------------------------------------------------------------

PING = Event()
PONG = RendezVous(expect=0)


class Main(LocalFiles):

    @on(GET="/ping")
    def servePing(self, request):
        PING.trigger()
        return request.respond("ping")

    @on(GET="/pong")
    def servePong(self, request):
        def stream():
            while True:
                yield RendezVous(expect=1).joinEvent(PING)
                yield "pong"
        return request.respond(stream())

# ------------------------------------------------------------------------------
#
# Main
#
# ------------------------------------------------------------------------------


# Gunicorn expects an 'application' symbol to be available
application = run(
    app=Application(Main()),
    name=os.path.splitext(os.path.basename(__file__))[1],
    method=WSGI,
)

# EOF
