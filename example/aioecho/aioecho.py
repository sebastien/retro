#!/usr/bin/env python
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
import retro

# ------------------------------------------------------------------------------
#
# COMPONENT
#
# ------------------------------------------------------------------------------


class Main(retro.Component):
    @retro.on(GET_POST_UPDATE_DELETE="{path:any}")
    async def echo(self, request, path):
        body = await request.body()
        sys.stdout.write(retro.ensureString(body))
        sys.stdout.write("\n\n")
        sys.stdout.flush()
        return request.respond(body)


# ------------------------------------------------------------------------------
#
# Main
#
# ------------------------------------------------------------------------------


if __name__ == "__main__":
    main = Main()
    retro.run(
        app=retro.Application(main),
        name=os.path.splitext(os.path.basename(__file__))[1],
        method=retro.STANDALONE,
        port=8000,
        asynchronous=True,
    )

# EOF - vim: tw=80 ts=4 sw=4 noet
