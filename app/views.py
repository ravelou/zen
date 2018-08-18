# -*- encoding:utf-8 -*-
import os
import re
import datetime
import sys
import json
import requests
import flask


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import app.opt as opt

from app.viewsfunc import getFilesFromDirectory, search, connect
from flask_bootstrap import Bootstrap
from collections import OrderedDict
from zen import tfa, crypto
from zen.cmn import loadConfig, loadJson
from zen.chk import getNextForgeRound
from zen.tbw import loadTBW, spread, loadParam

from app import appweb

ROOT = os.path.abspath(os.path.dirname(__file__))
# load all information
CONFIG = loadConfig()

PARAM = loadParam()
LOCAL_API = "http://localhost:%(port)s/api/" % CONFIG
# LOCAL_API = "http://167.114.29.52:%(port)s/api/" % CONFIG

# show index


@appweb.route("/")
def render():
    global CONFIG, PARAM

    # spread()

    weight = loadTBW()
    tokens = sum(weight.values())
    c = float(sum(weight.values()))
    items = [[k, v/max(1.0, c)*100] for k, v in weight.items()]

    return flask.render_template(
        "bs-layout.html",
        next_block="NaN",  # getNextForgeRound(CONFIG["peer"], **CONFIG),
        items=sorted(items, key=lambda e: e[-1], reverse=True),
        tokens=tokens,
        username=PARAM.get("username", "_"),
        share=PARAM.get("share", 1.),
        threshold=PARAM.get("threshold", 0.),
        symbol=PARAM.get("symbol", "token"),
        explorer=CONFIG["explorer"]
    )


@appweb.route("/history/<string:field>/<string:value>/<int:start>/<int:number>")
def render_history(field, value, start, number):
    global CONFIG, PARAM
    if value:
        if getattr(flask.g, "search_field", None) != field:
            flask.g.rows = search(**{field: value, "table": "transactions"})
            flask.g.search_field = field

        return flask.render_template(
            "bs-history.html",
            field=field,
            value=value,
            start=start,
            number=number,
            explorer=CONFIG["explorer"],
            symbol=PARAM.get("symbol", "token"),
        )


@appweb.route("/stats")
def get_stats():
    return flask.render_template(
        "bs-stats.html",
        username=PARAM.get("username", "_"),
        payments=getFilesFromDirectory("archive", ".tbw", 'json')
    )


@appweb.route("/logs")
def get_logs():
    # check if logged in from cookies
    if not flask.session.get("logged", False):
        # if not logged in return to login page
        return flask.redirect(flask.url_for("login"))
    else:
        # render manage page
        return flask.render_template(
            "bs-logs.html",
            username=PARAM.get("username", "_"),
            payments=getFilesFromDirectory("..", ".log")
        )


@appweb.route("/optimize/<string:blockchain>/<int:vote>/<string:usernames>/<string:offsets>/<int:delta>")
def optimize(blockchain, vote, usernames, offsets, delta):
    delta = max(delta, 10)
    pool = loadJson(os.path.join(ROOT, "pool.%s.json" % blockchain))
    if not bool(pool):
        return "No public pool defined on %s blockchain !" % blockchain
    # configure delegate behaviour according to blockchain parameters
    opt.Delegate.configure(
        blocktime=CONFIG["blocktime"],
        delegates=CONFIG["delegates"],
        reward=float(requests.get(
            LOCAL_API+"blocks/getReward").json().get("reward", 0))/100000000
    )
    # separate usernames
    delegates = [
        d for d in requests.get(LOCAL_API+"delegates").json().get("delegates", [])
        if d["username"] in (pool.keys() if usernames == "all" else usernames.split(","))
    ]
    # create delegate object for the solver
    delegates = [
        opt.Delegate(d["username"], pool[d["username"]]["share"], float(
            d["vote"])/100000000, float(pool[d["username"]]["exclude"])/100000000)
        for d in delegates if d["username"] in pool
    ]
    # remove curent vote given in username order in offsets
    if usernames != "all":
        i = 0
        for offset in [int(s) for s in offsets.split(",")]:
            delegates[i].vote -= offset
            i += 1
    # resolve best vote spread
    if len(delegates):
        return json.dumps(OrderedDict(sorted(
            [(k, v) for k, v in opt.solve(
                vote, delegates, step=delta).items() if v > 0],
            key=lambda e: e[-1],
            reverse=True
        )), indent=2)
    else:
        return "No public pool available !"


@appweb.route("/dashboard/share/<string:address>/<int:period>")
def compute_share(address, period):
    username = PARAM["username"]

    excludes = 0
    for addr in PARAM["excludes"]:
        excludes += float(requests.get(LOCAL_API+"accounts/getBalance?address=" +
                                       addr).json().get("balance", 0))/100000000

    reward = float(requests.get(
        LOCAL_API+"blocks/getReward").json().get("reward", 0))/100000000
    balance = float(requests.get(
        LOCAL_API+"accounts/getBalance?address="+address).json().get("balance", 0))/100000000
    vote = float(requests.get(LOCAL_API+"delegates/get?username=" +
                              username).json().get("delegate", {}).get("vote", 0))/100000000

    forged = (period * 3600 * 24) / \
        (CONFIG['blocktime'] * CONFIG['delegates']) * reward
    weight = balance/max(1, vote+balance-excludes)  # avoid ZeroDivisioError :)

    return flask.render_template(
        "bs-dashboard.html",
        username=username,
        info={
            "walletAddress": address,
            "walletAmount": balance,
            "walletAddressRatio": weight,
            "reward": forged * weight * PARAM["share"],
            "period": period,
            "vote": vote
        }
    )


@appweb.teardown_appcontext
def close(*args, **kw):
    if hasattr(flask.g, "database"):
        flask.g.database.close()


@appweb.context_processor
def override_url_for():
    return dict(url_for=dated_url_for)


# Identification
@appweb.route("/login", methods=["GET", "POST"])
def login():
    global CONFIG, PARAM
    # enable session lifetime to 10 min
    flask.session["permanent"] = True
    # if POST method send from login page or any POST containing a signature field
    if flask.request.method == "POST":
        flask.session.pop("logged", None)
        # check signature match (signature must be sent as hexadecimal string)
        try:
            check = tfa.check(CONFIG["publicKey"], crypto.unhexlify(
                flask.request.form["signature"]))
        except:
            check = False
        if check:
            # store the logged state
            flask.session["logged"] = True
            # go to manage page
            return flask.redirect(flask.url_for("manage"))
        else:
            # store the logged state
            flask.session["logged"] = False
            # return to index
            return flask.redirect(flask.url_for("render"))
    # if classic access render login page
    else:
        return flask.render_template("bs-login.html")


@appweb.route("/logout")
def logout():
    # store the logged state
    flask.session["logged"] = False
    # return to index
    return flask.redirect(flask.url_for("render"))


@appweb.route("/manage")
def manage():
    # check if logged in from cookies
    if not flask.session.get("logged", False):
        # if not logged in return to login page
        return flask.redirect(flask.url_for("login"))
    else:
        # render manage page
        return flask.render_template("manage.html")

def dated_url_for(endpoint, **values):
    if endpoint == 'static':
        filename = values.get('filename', None)
        if filename:
            file_path = os.path.join(appweb.root_path,
                                     endpoint, filename)
            values['q'] = int(os.stat(file_path).st_mtime)
    return flask.url_for(endpoint, **values)

def format_datetime(value, size='medium'):
    if size == 'full':
        fmt = "%A, %d. %B %Y at %H:%M"
    elif size == 'minimal':
        fmt = "%a, %d.%m.%y"
    elif size == 'medium':
        fmt = "%a, %d.%m.%y %H:%M"
    # the [:-6] permits to delete the +XX:YY at the end of the timestamp
    tuple_date = datetime.datetime.strptime(value[:-6], "%Y-%m-%d %H:%M:%S.%f")
    return datetime.datetime.strftime(tuple_date, fmt)
appweb.jinja_env.filters['datetime'] = format_datetime

def replace_regex(value, pattern, repl):
    appweb.logger.info("Valeur : %s, pattern : %s, repl : %s" %
                       (value, pattern, repl))
    appweb.logger.info("retour : %s" % re.sub(pattern, repl, value))
    return re.sub(pattern, repl, value)
appweb.jinja_env.filters['replace_regex'] = replace_regex
