"""WSGI application to be used with WSGI program so you can use it in
	production
"""
#import os
#import sys
import app
#sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
#print(sys.path)

if __name__ == "__main__":
	app.appweb.run()
