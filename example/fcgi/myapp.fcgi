#!/usr/bin/env python
from retro import *
from retro.contrib.localfiles import LocalFiles
print "Retro: Starting FCGI"
run(
	app        = Application(LocalFiles()),
	name       = os.path.splitext(os.path.basename(__file__))[1],
	method     = FCGI,
	sessions   = False
)
# EOF
