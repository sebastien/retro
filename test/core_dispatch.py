from retro.web import Dispatcher
from retro import *
import os
import sys
sys.path.insert(0, os.path.abspath(
    os.path.dirname(os.path.abspath(__file__)) + "../src"))


def Dispatcher_syntaxTest():
    EXPRESSIONS = (
        ("",						("/"),
         ("/hello", "/hello/world")),

        ("/",						("/"),
         ("/hello", "/hello/world")),

        ("/hello",					("/hello"),
         ("/", "/hello/world")),

        ("/{hello}",				("/hello", "/world", "/spam"),
         ("/", "/hello/world", "/hell0", "hello/")),

        ("/[hello]",				("/", "/hello"),
         ("/world", "/spam", "/hello/world", "/hell0", "hello/")),

        ("/[{hello}]",				("/", "/hello", "/world", "/spam"),
         ("/hello/world", "/hell0", "hello/")),

        ("/{something:string}",		("/hello", "/world", "/spam"),
         ("/", "/hello/world", "/hell0", "hello/")),

        ("/{something:string}/else",	("/hello/else", "/world/else", "/spam/else"),
         ("/", "/hello/world", "/hell0", "hello/")),

        ("/repo/{key:string}/changes",	("/repo/pouet/changes", "repo/burp/changes"),
         ()),
        ("id:{oid:integer}/{attribute:word}",	("id:1/hello", "id:10:world"),
         ("1/hello", "id:hello/world")),
        ("something?{params}",	("something", "something?a=1"))
    )
    d = Dispatcher()
    for e, a, r in EXPRESSIONS:
        print d._parseExpression(e)
    print "OK"


if __name__ == "__main__":
    Dispatcher_syntaxTest()

# EOF
