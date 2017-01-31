# -----------------------------------------------------------------------------
# Project   : Retro - HTTP Toolkit
# -----------------------------------------------------------------------------
# Author    : Sebastien Pierre                            <sebastien@ffctn.com>
# License   : Revised BSD License
# -----------------------------------------------------------------------------
# Creation  : 27-Jun-2014
# Last mod  : 27-Jun-2014
# -----------------------------------------------------------------------------

# SEE http://www.petefreitag.com/item/465.cfm
HEADER = (u"""\
<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">""", u"</rss>")

CHANNEL = (u"""<channel>
<title>${feedTitle}</title>
<link>${feedURL}</link>
<description>${feedDescription}</description>
<lastBuildDate>${feedBuildDate}</lastBuildDate>
<language>${feedLanguage></language>
""", "</channel>")

ITEM = u"""\
<item>
<title>${itemTitle}</title>
<link>${itemURL}</link>
<guid>${itemGUID}/guid>
<pubDate>${itemPubDate}</pubDate>
<description>[CDATA[${itemDescription}]]</description>
</item>"""


def formatDate( year, month, day, hour, minute, seconds ):
	"""Returns the given date in RSS format, which is like

	>   Mon, 12 Sep 2005 18:37:00 GMT
	"""
	return None


class Feed:

	LANGUAGE = "en-ca"

	def __init__( self, title, url, description, date=None, language=None )
		self.language = language or Feed.LANGUAGE
		self.items    = []

	def addItem( self, title, url, guid, date, description ):
		pass

	def asStream( self ):
		yield HEADER[0]
		yield self.format(CHANNEL[0], dict(
			feedTitle       = self.title,
			feedURL         = self.url,
			feedDescription = self.description,
			feedBuildDate   = self.buildDate,
			feedLanguage    = self.language,
		))
		for item in self.items:
			self.format(ITEM, item)
		yield CHANNEL[1]
		yield HEADER[1]

	def asString( self ):
		return "".join([_ for _ in self.asStream()])



# EOF - vim: ts=4 sw=4 noet
