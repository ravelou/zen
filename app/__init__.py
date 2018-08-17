# -*- encoding:utf-8 -*-
import os
from flask import Flask
from flask_bootstrap import Bootstrap

ROOT = os.path.abspath(os.path.dirname(__file__))

# create the application instance
appweb = Flask(__name__)
Bootstrap(appweb)
appweb.config.update(
    # 300 seconds = 5 minutes lifetime session
    PERMANENT_SESSION_LIFETIME=300,
    # used to encrypt cookies
    # secret key is generated each time app is restarted
    SECRET_KEY=os.urandom(24),
    # JS can't access cookies
    SESSION_COOKIE_HTTPONLY=True,
    # bi use of https
    SESSION_COOKIE_SECURE=False,
    # update cookies on each request
    # cookie are outdated after PERMANENT_SESSION_LIFETIME seconds of idle
    SESSION_REFRESH_EACH_REQUEST=True
)

import app.views
