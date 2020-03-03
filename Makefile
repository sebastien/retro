VERSION=$(shell grep __version__ Sources/retro/__init__.py | head -n1 | cut -d'"' -f2)
SOURCES_PY=$(wildcard src/retro/*.py src/retro/*/*.py  src/retro/*/*/*.py)
MANIFEST    = $(SOURCES_PY) $(wildcard *.py api/*.* AUTHORS* README* LICENSE*)
PRODUCT     = MANIFEST

.PHONY: all doc clean check tests

all: $(PRODUCT)

release: $(PRODUCT)
	git commit -a -m "Release $(VERSION)" ; true
	git tag $(VERSION) ; true
	git push --all ; true
	python setup.py clean sdist register upload

clean:
	@rm -rf api/ build dist MANIFEST ; true

check:
	pychecker -100 $(SOURCES)

test:
	python tests/all.py

MANIFEST: $(MANIFEST)
	echo $(MANIFEST) | xargs -n1 | sort | uniq > $@

#EOF
