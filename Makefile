# Retro makefile
# -----------------
#
# Revision 1.5.1 (24-Mar-2006)
#
# Distributed under BSD License
# See www.type-z.org/copyleft.html
# (c) S�bastien Pierre - http://www.type-z.org, 2003 - 2006
#
#  This Makefile is intendended for developers only. It allows to automate
#  common tasks such as checking the code, getting statistics, listing the TODO,
#  FIXME, etc, generating the documentation, packaging a source tarball and so
#  on.
#
#  On of the main advantage is that this Makefile can "prepare" the development
#  environment quickly by creating a symblink from the main package to the
#  proper location in Python site-packages, so that testing can be done without
#  having to run 'setup.py install' each time.
#  
#  For that reason, end-users will use the setup.py, while developers will
#  typically want to use this makefile, by first running "make prepare".


# Project variables___________________________________________________________

# Project name. Do not put spaces.
PROJECT         = retro
PROJECT_VERSION = $(shell grep __version__ Sources/retro/__init__.py | head -n1 | cut -d'"' -f2)
PROJECT_STATUS  = DEVELOPMENT

DOCUMENTATION   = Documentation
SOURCES         = Sources
TESTS           = Tests
SCRIPTS         = 
LIBRARY         = Library
RESOURCES       =
DISTRIBUTION    = Distribution
API             = $(DOCUMENTATION)/retro-api.html
DISTROCONTENT   = $(DOCUMENTATION) $(SOURCES) $(SCRIPTS) $(TESTS) $(RESOURCES) \
                  Makefile README setup.py

# Project files_______________________________________________________________

PACKAGE         = retro
MAIN            = __init__.py
MODULES         = retro retro.core retro.web \
                  retro.contrib.cache\
                  retro.contrib.localfiles retro.contrib.proxy retro.contrib.query retro.contrib.record retro.contrib.session

TEST_MAIN       = 
SOURCE_FILES    = $(shell find $(SOURCES) -name "*.py")
TEST_FILES      = $(shell find $(TESTS) -name "*.py")
CHECK_BLACKLIST = 

# Tools_______________________________________________________________________

PYTHON          = $(shell which python)
PYTHONHOME      = $(shell $(PYTHON) -c \
 "import sys;print filter(lambda x:x[-13:]=='site-packages',sys.path)[0]")
SDOC            = $(shell which sdoc)
PYCHECKER       = $(shell which pychecker)
CTAGS           = $(shell which ctags)
JSJOIN          = $(SCRIPTS)/jsjoin.py

# Useful variables____________________________________________________________

CURRENT_ARCHIVE = $(PROJECT)-$(PROJECT_VERSION).tar.gz
# This is the project name as lower case, used in the install rule
project_lower   = $(shell echo $(PROJECT) | tr "A-Z" "a-z")
# The installation prefix, used in the install rule
prefix          = /usr/local

# Rules_______________________________________________________________________

.PHONY: help info preparing-pre clean check dist doc tags todo

help:
	@echo
	@echo " $(PROJECT) development make rules:"
	@echo
	@echo "    prepare - prepares the project, may require editing this file"
	@echo "    check   - executes pychecker"
	@echo "    clean   - cleans up build files"
	@echo "    test    - executes the test suite"
	@echo "    doc     - generates the documentation"
	@echo "    info    - displays project information"
	@echo "    tags    - generates ctags"
	@echo "    todo    - view TODO, FIXMES, etc"
	@echo "    dist    - generates distribution"
	@echo
	@echo "    Look at the makefile for overridable variables."

all: prepare clean check test doc dist
	@echo "Making everything for $(PROJECT)"

info:
	@echo "$(PROJECT)-$(PROJECT_VERSION) ($(PROJECT_STATUS))"
	@echo Source file lines:
	@wc -l $(SOURCE_FILES)

todo:
	@grep  -R --only-matching "TODO.*$$"  $(SOURCE_FILES)
	@grep  -R --only-matching "FIXME.*$$" $(SOURCE_FILES)

prepare:
	@echo "WARNING : You may required root priviledges to execute this rule."
	@echo "Preparing python for $(PROJECT)"
	ln -snf $(PWD)/$(SOURCES)/$(PACKAGE) \
		  $(PYTHONHOME)/$(PACKAGE)
	@echo "Preparing done."

clean:
	@echo "Cleaning $(PROJECT)."
	@find . -name "*.pyc" -or -name "*.sw?" -or -name ".DS_Store" -or -name "*.bak" -or -name "*~" -exec rm '{}' ';'
	@rm -rf $(DOCUMENTATION)/API build dist

check:
	@echo "Checking $(PROJECT) sources :"
ifeq ($(shell basename spam/$(PYCHECKER)),pychecker)
	@$(PYCHECKER) -b $(CHECK_BLACKLIST) $(SOURCE_FILES)
	@echo "Checking $(PROJECT) tests :"
	@$(PYCHECKER) -b $(CHECK_BLACKLIST) $(TEST_FILES)
else
	@echo "You need Pychecker to check $(PROJECT)."
	@echo "See <http://pychecker.sf.net>"
endif
	@echo "done."

libs: 
	@echo "Making JavaScript libraries"
	@$(JSJOIN) $(LIBRARY)/prototype/prototype.js \
						 $(LIBRARY)/prototype/extend.js \
						 $(LIBRARY)/prototype/eip.js  \
						 $(LIBRARY)/prototype/effects.js \
						 $(LIBRARY)/prototype/validation.js > $(LIBRARY)/prototype.js
	@$(JSJOIN) $(LIBRARY)/retro/retro.js \
						$(LIBRARY)/retro/html.js \
						$(LIBRARY)/retro/ui.js > $(LIBRARY)/retro.js
	@$(JSJOIN) $(LIBRARY)/narrativejs/narcissus_jsdefs.js \
						$(LIBRARY)/narrativejs/narcissus_jsparse.js \
						$(LIBRARY)/narrativejs/NjsCompiler.js \
						$(LIBRARY)/narrativejs/NjsRuntime.js \
						$(LIBRARY)/narrativejs/NjsScriptWriter.js > $(LIBRARY)/narrative.js

test: $(SOURCE_FILES) $(TEST_FILES)
	@echo "Testing $(PROJECT)."
	@$(PYTHON) $(TEST_MAIN)

dist:
	@echo "Creating archive $(DISTRIBUTION)/$(PROJECT)-$(PROJECT_VERSION).tar.gz"
	@mkdir -p $(DISTRIBUTION)/$(PROJECT)-$(PROJECT_VERSION)
	@cp -r $(DISTROCONTENT) $(DISTRIBUTION)/$(PROJECT)-$(PROJECT_VERSION)
	@make -C $(DISTRIBUTION)/$(PROJECT)-$(PROJECT_VERSION) clean
	@make -C $(DISTRIBUTION)/$(PROJECT)-$(PROJECT_VERSION) doc
	@tar cfz $(DISTRIBUTION)/$(PROJECT)-$(PROJECT_VERSION).tar.gz \
	-C $(DISTRIBUTION) $(PROJECT)-$(PROJECT_VERSION)
	@rm -rf $(DISTRIBUTION)/$(PROJECT)-$(PROJECT_VERSION)

man: README
	texto -m -ilatin-1 README  Documentation/manual.html

doc: man
	@echo "Generating $(PROJECT) documentation"
ifeq ($(shell basename spam/$(SDOC)),sdoc)
	@$(SDOC) -mtexto -cp$(SOURCES) $(MODULES) $(API)
else
	@echo "Sdoc is required to generate $(PROJECT) documentation."
	@echo "Please see <http://www.ivy.fr/sdoc>"
endif

tags:
	@echo "Generating $(PROJECT) tags"
ifeq ($(shell basename spam/$(CTAGS)),ctags)
	@$(CTAGS) -R
else
	@echo "Ctags is required to generate $(PROJECT) tags."
	@echo "Please see <http://ctags.sf.net>"
endif

release:
	python setup.py sdist
	python setup.py register

#EOF
