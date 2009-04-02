#!/usr/bin/env python
from railways import *
from railways.contrib.localfiles import LocalFiles
print "Railways: Starting FCGI"
run(
	app        = Application(LocalFiles()),
	name       = os.path.splitext(os.path.basename(__file__))[1],
	method     = FCGI,
	sessions   = False
)
# EOF
