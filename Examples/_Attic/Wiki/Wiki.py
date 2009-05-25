#!/usr/bin/env python
# Encoding: iso-8859-1
# vim: tw=80 ts=4 sw=4 noet
# -----------------------------------------------------------------------------
# Project   : Wiki Example
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                               <sebastien@ivy.fr>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 07-Aug-2006
# Last mod  : 19-Sep-2006
# -----------------------------------------------------------------------------

from retro import *
import os, re, shutil
try:
	import kiwi.core
	import kiwi.inlines
	import kiwi.kiwi2html
except ImportError, e:
	print "Kiwi is required for this example to run."
	print "You can get kiwi at <http://www.ivy.fr/kiwi>"
	print
	raise e

__doc__ = """\
This example shows how to do a file upload with a progress bar.
"""

# ------------------------------------------------------------------------------
#
# MAIN COMPONENT
#
# ------------------------------------------------------------------------------


BLANK_PAGE = """\
This is a blank page. Click on the text to edit it.
"""
class Main(Component):

	def init( self ):
		self.parser = kiwi.core.Parser(
			self.app().localPath('data'),
			self.app().config("charset"), 
			self.app().config("charset")
		)
		# Sets up the Kiwi parser to parse wiki markup
		wiki_page1 = kiwi.inlines.InlineParser("wikiPage", re.compile("([A-Z]+[a-z]+([A-Z]+[a-z]+)+)"))
		wiki_page2 = kiwi.inlines.InlineParser("wikiPage", re.compile("wiki:([A-Za-z]+)"))
		self.parser.inlineParsers.append(wiki_page1)
		self.parser.inlineParsers.append(wiki_page2)
		# And we also register processors to convert the XML to HTML
		self.processor = kiwi.kiwi2html.processor
		self.processor.registerElementProcessor( self._processWikiPageMarkup, 'wikiPage' )

	def _processWikiPageMarkup( self, element ):
		"""This function is invoked by the Kiwi2HTML processor when `wikiPage`
		elements are encountered. We simply expand them to links to edit the
		pages."""
		page = element.childNodes[0].data
		if self.hasPage(page):
			return "<span class='wikiPageLink'><a class='broken' " \
			+ "href='/pages/%s'>%s</a></span>" % (page, page)
		else:
			return "<span class='wikiPageLink'><a " \
			+ "href='/pages/%s'>%s</a></span>" % (page, page)

	def hasPage( self, page ):
		"""Tells if the given page exists."""
		return os.path.exists(os.path.join("data", page))

	def loadPage( self, page ):
		"""Loads the given page and returns its content. If the page does not
		exists, it returns the `BLANK_PAGE` value."""
		p = os.path.join("data", page)
		if not os.path.exists(p): return BLANK_PAGE
		f = file(p, 'r')
		c = f.read()
		f.close()
		return c

	def savePage( self, page, content ):
		"""Saves the given text content as the markup for the given page."""
		data_dir = os.path.dirname(self.pagePath(page))
		print data_dir
		if not os.path.isdir(data_dir): os.makedirs(data_dir)
		self.backupPage(page)
		f = file(self.pagePath(page), 'w')
		c = f.write(content)
		f.close()
		return content

	def pagePath( self, page):
		page = page.lower()
		return os.path.abspath(os.path.join("data", page))

	def backupPath( self, page):
		suffix = ".v"
		count  = 1
		page = page.lower()
		path = os.path.abspath(os.path.join("data", "history", page))
		while os.path.exists(path+suffix+str(count)):
			count += 1
		return path + suffix + str(count)

	def backupPage( self, page ):
		"""Backs up this page and saves it to the history folder."""
		if not os.path.exists(self.pagePath(page)): return
		hist_dir = os.path.dirname(self.backupPath(page))
		if not os.path.isdir(hist_dir): os.makedirs(hist_dir)
		shutil.copyfile(self.pagePath(page), self.backupPath(page))

	def renderMarkup( self, markup ):
		"""Renders the given markup to an HTML document fragment (body only)."""
		xml_document = self.parser.parse(unicode(markup.decode("latin-1")), offsets=True)
		result       = self.processor.generate(xml_document, True, {}).encode(self.app().config("charset"))
		return result

	def _parsePagePath( self, page ):
		"""Returns the elements within this page path"""
		elems = page.split("/")
		elems = map(lambda x:x.strip().lower(), elems)
		return elems

	@on(GET="/pages/{page:wiki}")
	def displayPage( self, request, page ):
		"""Displays a Wiki page or its source"""
		if self.hasPage(page):
			if os.path.isdir(self.pagePath(page)):
				pages = os.listdir(self.app().localPath(self.pagePath(page)))
				print "pages at", self.pagePath(page),self.app().localPath(self.pagePath(page))
				print pages
				return request.display("pages", pages=pages)
			else:
				return request.display("page", markup=self.loadPage(page), title=page)
		else:
			markup = self.savePage(page, "Edit this page")
			return request.display("page", markup=markup, title=page)

	@on(GET="/pages")
	@on(GET="/pages/")
	@on(GET="/pages/list")
	def listPages( self, request ):
		"""Displays the list of pages."""
		pages = os.listdir(self.app().localPath(self.pagePath("")))
		return request.display("pages", pages=pages)

	@on(POST="/pages/{page:wiki}")
	def saveEditedPage( self, request, page ):
		"""Saves the given page and returns the processed HTML data."""
		markup = self.savePage(page, request.get("content"))
		return request.respond(kiwi.main.text2htmlbody(markup))

	@on(POST="/pages/{page:wiki}/{start:int}-{end:int}")
	def saveEditedFragment( self, request, page, start, end ):
		"""Saves the given page and returns the processed HTML data."""
		markup  = request.get("content") or ""
		content = self.loadPage(page)
		content = content[:start] + markup + content[end:]
		content = self.savePage(page, content )
		return request.respond(self.renderMarkup(content))

	@on(GET="/pages/{page:wiki}/source")
	def displaySource( self, request, page ):
		return request.respond(self.loadPage(page), [('Content-Type','text/plain')])

	@on(GET="/pages/{page:wiki}/render")
	def renderSource( self, request, page ):
		return request.respond(self.renderMarkup(self.loadPage(page)))

	@on(GET="/pages/{page:wiki}/source/{start:int}-{end:int}")
	def displaySourceFragment( self, request, page, start, end ):
		content = self.loadPage(page)
		return request.respond(content[start:end], [('Content-Type','text/plain')])

	# MAIN
	# ____________________________________________________________________________

	@on(GET="lib/{path:any}")
	def lib( self, request, path ):
		"""Serves the files located in the `Library` grand parent directory."""
		return request.respondFile(self.app().localPath("../../Library/" + path))

	@on(GET="/")
	@display("index")
	def main( self, request ):
		"""Serves the main template file"""

def start(prefix=""):
	"""This is the main function that should be called by FCGI handlers or
	whatever else."""
	# We register a "wiki" pattern in the dispatcher pattern. This wiki pattern
	# is used in the `on` decorators in the Main component.
	Dispatcher.PATTERNS["wiki"] = (r'\w+(/\w+)*', str)
	run(
		app        = Application(prefix="",components=[Main()]),
		name       = os.path.splitext(os.path.basename(__file__))[0],
		method     = STANDALONE
	)

if __name__ == "__main__":
	start()

# EOF
