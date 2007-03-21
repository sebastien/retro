# -----------------------------------------------------------------------------
# Project           :   Prevail
# Author            :   Sebastien Pierre
# License           :   BSD License (revised)
# -----------------------------------------------------------------------------
# Creation date     :   10-Feb-2006
# Last mod.         :   10-Feb-2006

import os, sys, re

TEST_FILE  = re.compile("([SU][0-9]+)\-(\w+)\.py")
TEST_FILES = {}

DIR  = os.path.dirname(__file__)
def do():
	# We populate the test files hash table
	this_dir = os.path.abspath(os.path.dirname(__file__))
	for path in os.listdir(this_dir):
		m = TEST_FILE.match(path)
		if not m: continue
		f = TEST_FILES.setdefault(m.group(1), [])
		f.append((m.group(2), os.path.join(this_dir, path)))

	# And now execute the tests
	groups = TEST_FILES.keys() ; groups.sort()
	files  = []
	for group in groups:
		for test, test_path in TEST_FILES[group]:
			print "%4s:%20s " % (group, test),
			out = os.popen("python "+ test_path).read()
			out = filter(lambda l:l, out.split("\n"))
			if out and out[-1].strip() == "OK": print "[OK]"
			else: print "[FAILED]", out

if __name__ == "__main__":
	if len(sys.argv) == 1:
		do()

# EOF
