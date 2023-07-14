from flask import Flask, request, jsonify
import os

app = Flask(__name__)

apiKey = os.environ.get('API_KEY')
if(apiKey == None):
    print("ERROR: Expected OpenAI API KEY as Environment Variable API_KEY")




#a dict of groupIds (ints)
#each id maps to a dict with the following components
#   conv - an array of sequential messages, basically the groups chat history
#   mode - the reply mode of the bots. This can be either
#       "rp": the bots are meant to reply "in-character"
#       "player": the bots are meant to reply as if they were the player controlling the bot character
conversations = {}

@app.post("/group")
def postGroup():
    if  request.is_json:
        groupId = request.get_json()["id"]
        mode = request.get_json().get("mode")
        registerGroup(groupId,mode)
        return {"id": groupId, "conv": conversations[groupId]}, 201
    return {"error": "Request must be JSON"}, 415

@app.post("/group/<groupId>")
def getReply(groupId):
    groupId = int(groupId)
    if  request.is_json:
        message = request.get_json().get("string")
        context = request.get_json().get("context")

        group = conversations.get(groupId)
        if(group==None):
            return {"error": "Group with id "+ groupId +" is not registered."}, 400

        conversations[groupId]["conv"].append(message)

        makeReply(conversations[groupId], context)

        ##just for debugging purposes
        return {"temp":"temp", "conv": conversations[groupId]["conv"]}, 200
    return {"error": "Request must be JSON"}, 415

def registerGroup(groupId, mode="player"):
    mode = "player" if mode==None else mode
    conversations[groupId] = {"mode" : mode, "conv" : []}


def makeReply(conv, context):
    print(context)
    print(conv["conv"])

#debug
registerGroup(1234, "player")