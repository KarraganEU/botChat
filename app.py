from flask import Flask, request, jsonify
import os
import openai
import argparse

app = Flask(__name__)

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    #parser.add_argument("--replyMode", help="Whether the bot should reply in-character or out of character", choices=['rpshort', 'rp', 'player'], default='rpshort')
    parser.add_argument("--key")
    args = parser.parse_args()
    apiKey = args.key   
    openai.api_key = apiKey
    """apiKey = os.environ.get('API_KEY')
    if(apiKey == None):
        print("ERROR: Expected OpenAI API KEY as Environment Variable API_KEY")
    print(apiKey)"""

    systemBase = """You are taking on the role of characters played by NPCs/Bots in a World of Warcraft - Wrath of the Lich King Party."""
    tempContext = """The Party consists of the real Player Karragan, the male Human Protection Warrior; and the following Bots/NPCs:
Bromos, the male Dwarf Holy Paladin;
Osborne, the male Human Rogue;
Anetta, the female Human Frost Mage, and 
Elira, the female Night Elf Hunter.
All members of the party are Level 26."""
    postContext = """Do not inject statements about the party and characters that you can not infer from context or game knowledge.
Each reply should start on a new line and be formatted like this: <Speakername>: <text>. 
Unless specific bots are addressed, you may speak as multiple of the bots in one message, as long as the formatting fits the above. 
If bots are addressed directly, only these specific characters may reply. 
Otherwise, replies from multiple bots are optional. A reply from one bot is sufficient.
You may not speak as the real player, Karragan."""


    #Try to tonally match the races of the speakers (for example like a stereotypical dwarf for dwarves, elvish verbiage for night elves, etc). 
    settingsMap = {
        "replyMode": {
            "player" : "You should reply out-of-character, i.e. as if you were the player controlling the character.",
            "rp" : "You should reply in-character, i.e. as if you were the speaking character themselves. Try to tonally match the races of the speakers (for example like a stereotypical dwarf for dwarves, elvish verbiage for night elves, etc). ",
            "rpshort": "You should reply in-character, i.e. as if you were the speaking character themselves, but do not be overly verbose.  Try to tonally match the races of the speakers (for example like a stereotypical dwarf for dwarves, elvish verbiage for night elves, etc). But be succinct, do not ramble."
        }
    }

    #a dict of groupIds (ints)
    #each id maps to a dict with the following components
    #   conv - an array of sequential messages, basically the groups chat history
    #   mode - the reply mode of the bots. This can be either
    #       "rp": the bots are meant to reply "in-character"
    #       "player": the bots are meant to reply as if they were the player controlling the bot character
    conversations = {}

    # -------------------------- ROUTES -----------------------------------------

    @app.post("/group")
    def postGroup():
        if  request.is_json:
            groupId = request.get_json()["id"]
            mode = request.get_json().get("mode")
            registerGroup(groupId,mode)
            return {"id": groupId, "conv": conversations[groupId]}, 201
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
    @app.post("/group/<groupId>")
    def getReply(groupId):
        groupId = int(groupId)

        

        if  request.is_json:
            message = request.get_json().get("string")
            context = request.get_json().get("context")

             #args.replyMode
            #print(sysQuery)

            group = conversations.get(groupId)
            if(group==None):
                return {"error": "Group with id "+ groupId +" is not registered."}, 400

            conversations[groupId]["history"].append(message)

            replies = makeReply(conversations[groupId], context)

            ##just for debugging purposes
            return replies, 200
        return {"error": "Request must be JSON"}, 415

    def registerGroup(groupId, mode="rpshort"):
        mode = "rpshort" if mode==None else mode
        conversations[groupId] = {"mode" : mode, "history" : []}


    def makeReply(groupConversation, context):
        modeString = settingsMap["replyMode"][groupConversation["mode"]]
        sysQuery = systemBase + "\n" + getContextString(context) + "\n" + postContext + "\n" + modeString
        sysObj = {"role":"system", "content": sysQuery}

        history = ""
        for message in groupConversation["history"]:
            history += message
            history += "\n"
        historyObj = {"role":"user", "content": history}
        reply = getReplies(sysObj, historyObj)
        print("--------------------------------------------------")
        print("OpenAI API Response: ",reply)
        print("---------------------------------------------------")
        replies = reply.split("\n")
        res = {"replies" : []}
        for rep in replies:
            stripped = rep.strip()
            if stripped=="":
                continue
            speakerMessage = stripped.split(":")
            res["replies"].append({"speaker" : speakerMessage[0].strip(), "message": speakerMessage[1].strip()})
            #TODO put in local history


        #print("My Response:\n", res)
        return res

        #format replies, split by newLine, then by colon, return that way for easy calling and put the combined in the history
        #print("history: ", history)
        #print("sysMessage: ", sysQuery)

    def getContextString(context):
        #print(context)
        return tempContext;

    def getReplies(sysMessage, historyMessage):
        response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-0613",
        messages=[sysMessage, historyMessage],
        temperature=1,
        max_tokens=382,
        top_p=1,
        frequency_penalty=0.35,
        presence_penalty=0,
        stop=["Karragan:"]
        )
        return response['choices'][0]['message']['content']

    #debug
    registerGroup(1234)
    app.run(debug=True)

