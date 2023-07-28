from flask import Flask, request, jsonify
import logging
from util import appendAndSave, changeAndPersistSetting, makeReply, init, registerGroup
import db
import os

app = Flask(__name__)

validModes = ["rpshort", "rp", "player"]

debugReply = {"replies": [
        {
        "message": "Aye, lad! I think it be a grand idea. Stratholme has long been plagued by the Scourge, and it's our duty to cleanse it. I am ready to smite some undead with the Light!",
                    "speaker": "Valgar"
            },
            {
            "message": "Sounds like a plan. Stratholme is a hot spot for valuable loot too. Count me in for a piece of the action.",
            "speaker": "Osborne"
            },
            {
            "message": "Cleansing Stratholme could also provide us with some valuable research on necromancy and the Scourge. Plus, the dark atmosphere there will give me a chance to test some of my frost spells.",
            "speaker": "Anetta"
            },
            {
            "message": "The Plaguelands are filled with ancient ruins and hidden treasures. Exploring Stratholme will give me a chance to showcase my hunting skills while lending a hand in purging the Scourge.",
            "speaker": "Elira"
            },
            {
            "message": "Aye, lad! It appears we all agree then. Let us prepare ourselves and make our way to Stratholme together. We shall bring light, justice, and steel down upon the undead scum!",
            "speaker": "Bromos"
            }
    ]}

#a dict of leaderIds (ints)
#each id maps to a dict with the following components
#   history - an array of sequential messages, basically the groups chat history
#   mode - the reply mode of the bots. This can be either
#       "rp": the bots are meant to reply "in-character"
#       "rpshort":  the bots are meant to reply "in-character" but are explicitly told to not be verbose
#       "player": the bots are meant to reply as if they were the player controlling the bot character
cache = {}

if __name__ == "__main__":
    debug, port = init(cache)
    logger = logging.getLogger()

    # -------------------------- ROUTES -----------------------------------------

    @app.post("/group")
    def postGroup():
        if  request.is_json:
            leaderId = request.get_json()["id"]
            mode = request.get_json().get("mode")
            registerGroup(leaderId, cache, mode)
            return {"id": leaderId, "conv": cache[leaderId]}, 201
        return {"error": "Request must be JSON"}, 415

    # the message entry should be a simple String in the format "<<Sender>>: <<messagetext>>"
    #
    # the context should be a dict with two elements
    #   players - an array of all the players in the group
    #   bots    - an array of all the bots in the group
    #
    # the elements in both arrays should have identical structure, describing the character in question via the following members
    #   name    - name of the character
    #   level   - level of the character - can be omitted for bots
    #   race    - race of the character (Gnome, Orc, etc)
    #   class   - class of the character (Mage, Warlock, etc)
    #   gender  - gender of the character
    @app.post("/group/<leaderId>")
    def getReply(leaderId):
        leaderId = int(leaderId)

        if  request.is_json:
            message = request.get_json().get("string")
            context = request.get_json().get("context")

            if(cache.get(leaderId)==None):
                registerGroup(leaderId, cache)

            message = context["players"][0]["name"] +": " + message
            logger.debug(message);
            appendAndSave(message, leaderId, cache)
            replies = makeReply(context,leaderId, cache)

            return replies, 200
        return {"error": "Request must be JSON"}, 415

    @app.get("/")
    def testEndpoint():
        logger.info("Called testendpoint")
        return cache, 200        
    
    @app.post("/group/<leaderId>/mode")
    def setChatMode(leaderId):
        leaderId = int(leaderId)

        if  request.is_json:
            newMode = request.get_json().get("mode")

            if(cache.get(leaderId)==None):
                return {"error": "Group with id "+ str(leaderId) +" is not registered."}, 400

            isValid = any(newMode==allowedMode for allowedMode in validModes)
            if(not(isValid)):
                 return {"error": f"{newMode} is not a valid conversation mode. Valid Modes: {validModes}"}, 400

            logger.info(f"Setting chat mode {newMode} for group with leaderId {leaderId}")
            changeAndPersistSetting(leaderId, "mode", newMode, cache)
            return newMode, 200
        return {"error": "Request must be JSON"}, 415
    
    @app.post("/group/<leaderId>/history")
    def eraseHistory(leaderId):
        leaderId = int(leaderId)

        group = cache.get(leaderId)
        if(group==None):
            return {"error": "Group with id "+ str(leaderId) +" is not registered."}, 400

        logger.info(f"Erasing History for group with leaderId {leaderId}")
        cache[leaderId]["history"] = []
        db.eraseHistory(leaderId)

        return "erased history", 200
    
    #debug
    if(debug):
        registerGroup(999999, cache)
        registerGroup(1, cache)
    app.run(debug=debug, port=port)

