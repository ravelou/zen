# -*- encoding:utf-8 -*-
"""
TBW module :
information to get for the website running
"""
from collections import OrderedDict
import io
import os
import datetime
import pytz
import requests

from zen.cmn import loadJson, dumpJson, logMsg
from zen.chk import loadConfig


ROOT = os.path.abspath(os.path.dirname(__file__))
NAME = os.path.splitext(os.path.basename(__file__))[0]


def loadForge():
    """Function to get information about forging. You get :
    --rewards : total rewards for the delegate
    --forged  : total token delegate has forged
    --success : True or False depends on the blockchain request
    --fees    : fees that you have been forging
    Returns:
        [dict] -- [JSON data]
    """
    return loadJson(os.path.join(ROOT, NAME+".forge"))


def dumpForge(forge):
    """Function to flush informations about forging delegate
    in a file at /pathToModule/zen/twb.forge
    --rewards : total rewards for the delegate
    --forged  : total token delegate has forged
    --success : True or False depends on the blockchain request
    --fees    : fees that you have been forging

    Arguments:
        forge {[dict]} -- [JSON format]
    """
    dumpJson(forge, os.path.join(ROOT, NAME+".forge"))


def loadTBW():
    """Load JSON date for weight information about each voters
    file Format : voter's address: amount due at the time
    """
    return loadJson(os.path.join(ROOT, NAME+".weight"))


def dumpTBW(tbw):
    """Flush JSON data for weight information for each voters into
    /pathToModule/zen/twb.weight
    Arguments:
        tbw {[dict]} -- [JSON data {voter_address : amount_of_token}]
    """
    dumpJson(tbw, os.path.join(ROOT, NAME+".weight"))


def loadParam():
    """Load application parameters from /pathToModule/zen/twb.json file
    """
    return loadJson(os.path.join(ROOT, NAME+".json"))


def dumpParam(param):
    """Dump application parameters to /pathToModule/zen/twb.json file

    Arguments:
        param {[dict]} -- [JSON data format]
    """
    dumpJson(param, os.path.join(ROOT, NAME+".json"))


def get():
    """[summary]

    Returns:
        [OrderedDict] -- [empty orderdict if publicKey is not defined
        Sorted dict as JSON data format : 
        ]
    """
    param = loadParam()
    config = loadConfig()
    forge = loadForge()
    seed = config["peer"]

    if config.get("publicKey", False):
        resp = requests.get(
            seed+"/api/delegates/forging/getForgedByAccount?generatorPublicKey="+
            config["publicKey"]).json()
        if not bool(forge):
            reward = 0
            dumpForge(resp)
        else:
            reward = (int(resp["rewards"]) - int(forge["rewards"]))/100000000.
            dumpForge(resp)

        if reward > 0.:
            voters = requests.get(
                seed+"/api/delegates/voters?publicKey="+
                config["publicKey"]).json().get("accounts", [])
            voters = dict([v["address"], float(v["balance"])]
                          for v in voters if v["address"] not in param.get("excludes", []))
            total_balance = sum(voters.values())
            pairs = [[a, b/total_balance*reward] for a, b in voters.items()
                     if a not in param.get("excludes", []) and b > param.get("minvote", 0)]
            return OrderedDict(sorted(pairs, key=lambda e: e[-1], reverse=True))

    return OrderedDict()


def spread():
    """[summary]
    """
    rewards = get()
    tbw = loadTBW()

    if bool(rewards):
        out = io.open(os.path.join(ROOT, NAME+".log"), "a")
        all_addresses = list(rewards.keys())
        cowards = set(tbw.keys()) - set(all_addresses)
        if bool(cowards):
            logMsg("down-voted by : %s" % ", ".join(cowards), stdout=out)
            # reward_back = int(sum([tbw.get(a, 0.) for a in cowards]))*100000000
            # forged = loadForge()
            # forged["rewards"] = "%r" % (int(forged["rewards"])-reward_back)
            # dumpForge(forged)
        newcomers = set(all_addresses) - set(tbw.keys())
        if bool(newcomers):
            logMsg("up-voted by : %s" % ", ".join(newcomers), stdout=out)
        dumpTBW(OrderedDict(sorted([[a, tbw.get(a, 0.)+rewards[a]]
                                    for a in rewards.keys()], key=lambda e: e[-1], reverse=True)))
        out.close()


def extract():
    param = loadParam()
    data = OrderedDict(sorted(
        [[a, w] for a, w in loadTBW().items()], key=lambda e: e[-1], reverse=True))

    threshold = param.get("threshold", 0.)
    tbw = OrderedDict([a, w] for a, w in data.items() if w >= threshold)
    amount = sum(tbw.values())
    saved = sum(w for w in data.values() if w < threshold)

    now = datetime.datetime.now(tz=pytz.UTC)
    dumpJson(
        {
            "timestamp": "%s" % now,
            "saved": saved,
            "amount": param.get("share", 1.0)*amount,
            "weight": OrderedDict(sorted([[a, w/amount] for a, w in tbw.items()],
                                         key=lambda e: e[-1], reverse=True))
        },
        os.path.join(ROOT, "%s.tbw" % now.strftime("%Y-%m-%d"))
    )
    dumpTBW(OrderedDict([a, 0. if a in tbw else w] for a, w in data.items()))


def forgery():
    """[summary]
    
    """
    logMsg("Distributed token : %.0f" % sum(loadTBW().values()))


def adjust(value):
    """Function to make the shared amount exactly as the number in TBW website
    
    Arguments:
        value {[float]} -- [the value you want to put in the application]
    """
    data = loadTBW()
    total = sum(data.values())
    dumpTBW(OrderedDict(sorted(
        [[a, v/total*value] for a, v in data.items()], key=lambda e: e[-1], reverse=True)))
