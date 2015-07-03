#!/usr/bin/env python3
import logging
import asyncio
import os
import json

from aiotg import TgBot
from math import ceil

LEAFLY_HEADERS = {
    "app_id": os.environ["LEAFLY_APP_ID"],
    "app_key": os.environ["LEAFLY_APP_KEY"]
}

bot = TgBot(os.environ["API_TOKEN"])
logger = logging.getLogger("StonerBot")


def format_strain(strain):
    def names(section):
        return (i["Name"] for i in strain[section])

    stars = "⭐" * ceil(strain["Rating"]/2)
    positive = ", ".join(names("Tags"))
    negative = ", ".join(names("NegativeEffects"))
    symptoms = ", ".join(names("Symptoms"))

    text = "%s (%s)\n" % (strain["Name"], strain["Category"])
    if stars != "":
        text += "     %s\n" % stars
    if positive != "":
        text += "👍 %s\n" % positive
    if negative != "":
        text += "👎 %s\n" % negative
    if symptoms != "":
        text += "🏥 %s\n" % symptoms
    text += strain["permalink"]

    return text


@asyncio.coroutine
def leafly_strains(text):
    url = "http://data.leafly.com/strains"
    params = {
        "search": text,
        "page": 0,
        "take": 5,
        "sort": "rating"
    }
    data = json.dumps(params)

    response = yield from bot.session.post(url, headers=LEAFLY_HEADERS, data=data)

    if response.status != 200:
        response.close()
        logger.error("leafly returned %d for '%s'", 200, text)
        return
    else:
        res = (yield from response.json())
        return list(map(format_strain, res["Strains"]))


def format_store(store):
    features = {
        "delivery": "🚚",
        "storefront": "💵",
        "creditCards": "💳",
        "atm": "🏧",
        "medical": "🏥"
    }
    flist = "".join(e for k, e in features.items() if store[k])
    tmpl = "{name} ({0})\n{locationLabel}\n{address}\n{phone}\n{hours}"
    return tmpl.format(flist, **store)


@asyncio.coroutine
def leafly_locations(loc):
    url = "http://data.leafly.com/locations"
    params = {
        "page": 0,
        "take": 5
    }
    params.update(loc)

    response = yield from bot.session.post(url, headers=LEAFLY_HEADERS, data=params)
    assert response.status == 200
    res = (yield from response.json())

    return list(map(format_store, res.get("stores", [])))


def format_username(user):
    parts = ["first_name", "last_name", "username"]
    title = " ".join(filter(None, (user.get(part) for part in parts)))
    return title


@asyncio.coroutine
def search_strains(message, text):
    strains = yield from leafly_strains(text)
    results = len(strains or [])

    user = format_username(message["from"])
    logger.info("%s searched for '%s', found %d", user, text, results)

    if not strains:
        reply = "I have problems contacting my dealer, please come back later :("
    elif results == 0:
        reply = "No strains were found :("
    else:
        reply = "\n\n".join(strains)

    yield from bot.reply_to(message, reply)


@bot.command(r"/strains (.*)")
def strains(message, match):
    return search_strains(message, match.group(1))


@bot.default
def default(message):
    return search_strains(message, message["text"])


@bot.command("(/start|/?help)")
def usage(message, match):
    text = """
Hi! Did you know that robots like cannabis too?

Use "/strains name" to get info on specific strains or
send me your location and I will find stores near you.

Powered by Leafly API (https://www.leafly.com)
If you like this bot, please rate it at: https://telegram.me/storebot?start=stonerbot

Peace ✌️
    """
    return bot.reply_to(message, text)


@bot.location
@asyncio.coroutine
def locations(message):
    loc = message["location"]
    stores = yield from leafly_locations(loc)
    if len(stores) == 0:
        yield from bot.reply_to(message, "There are no stores around:(")
    else:
        yield from bot.reply_to(message, "\n\n".join(stores))


def main():
    logging.basicConfig(level=logging.INFO, filename="stonerbot.log")

    loop = asyncio.get_event_loop()
    loop.run_until_complete(bot.loop())
    bot.session.close()


if __name__ == '__main__':
    main()
