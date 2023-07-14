from flask import Flask, request, jsonify

app = Flask(__name__)

conversations = {}

@app.post("/group")
def addGroup():
    if  request.is_json:
        groupId = request.get_json()["id"]
        print(groupId)
        conversations[groupId] = []
        return {"id": groupId, "conv": conversations[groupId]}, 201
    return {"error": "Request must be JSON"}, 415

@app.post("/group/<groupId>")
def getReply(groupId):
    groupId = int(groupId)
    if  request.is_json:
        message = request.get_json()["string"]
        conversations[groupId].append(message)
        print(conversations)
        #getReply
        return {"temp":"temp", "conv": conversations[groupId]}, 200
    return {"error": "Request must be JSON"}, 415