from flask import Flask, request, jsonify
import os
import openai
import argparse

app = Flask(__name__)

#TODO get all this junk out of the main function, maybe classify it or seperate module

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
You may not speak as the real player, """

tempReply = {"replies": [
        {
        "message": "Aye, lad! I think it be a grand idea. Stratholme has long been plagued by the Scourge, and it's our duty to cleanse it. I am ready to smite some undead with the Light!",
                    "speaker": "Bromos"
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
#   conv - an array of sequential messages, basically the groups chat history
#   mode - the reply mode of the bots. This can be either
#       "rp": the bots are meant to reply "in-character"
#       "player": the bots are meant to reply as if they were the player controlling the bot character
conversations = {}

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    #parser.add_argument("--replyMode", help="Whether the bot should reply in-character or out of character", choices=['rpshort', 'rp', 'player'], default='rpshort')
    parser.add_argument("--key")
    args = parser.parse_args()
    apiKey = args.key   
    #apiKey = os.environ.get('API_KEY')
    if(apiKey == None):
        print("ERROR: Expected OpenAI API KEY as Environment Variable API_KEY")
    
    openai.api_key = apiKey

    settingsMap = {
        "replyMode": {
            "player" : "You should reply out-of-character, i.e. as if you were the player controlling the character.",
            "rp" : "You should reply in-character, i.e. as if you were the speaking character themselves. Try to tonally match the races of the speakers (for example like a stereotypical dwarf for dwarves, elvish verbiage for night elves, etc). ",
            "rpshort": "You should reply in-character, i.e. as if you were the speaking character themselves, but do not be overly verbose. Try to tonally match the races of the speakers (for example like a stereotypical dwarf for dwarves; eloquent and flowery language for night elves, etc). But be succinct, do not ramble."
        }
    }

    # -------------------------- ROUTES -----------------------------------------

    @app.post("/group")
    def postGroup():
        if  request.is_json:
            leaderId = request.get_json()["id"]
            mode = request.get_json().get("mode")
            registerGroup(leaderId,mode)
            return {"id": leaderId, "conv": conversations[leaderId]}, 201
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

             #args.replyMode
            #print(sysQuery)

            group = conversations.get(leaderId)
            if(group==None):
                registerGroup(leaderId)
                #return {"error": "Group with id "+ leaderId +" is not registered."}, 400

            conversations[leaderId]["history"].append(message)            
            replies = makeReply(conversations[leaderId], context,leaderId)

            ##just for debugging purposes
            return replies, 200
        return {"error": "Request must be JSON"}, 415

    @app.get("/")
    def testEndpoint():
        return "this is a test", 200

    def registerGroup(leaderId, mode="rpshort"):
        mode = "rpshort" if mode==None else mode
        conversations[leaderId] = {"mode" : mode, "history" : []}


    def makeReply(groupConversation, context, leaderId):
        modeString = settingsMap["replyMode"][groupConversation["mode"]]
        playerName = context["players"][0]["name"]
        sysQuery = systemBase + "\n" + getContextString(context) + "\n" + postContext + playerName + ".\n" + modeString
        sysObj = {"role":"system", "content": sysQuery}

        print(sysQuery)

        #allow for historyculling. Only the <lastn> messages in the stored history should be send to GPT
        history = ""
        lastn = 100
        startn = max(0, len(groupConversation["history"])-lastn)
        for index in range(startn, len(groupConversation["history"])):
            history += groupConversation["history"][index]
            history += "\n"
        historyObj = {"role":"user", "content": history}
        
        #temp
        #return tempReply        
        
        reply = getReplies(sysObj, historyObj, playerName)
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
            if(len(speakerMessage)!= 2):
                continue
            speaker = speakerMessage[0].strip()
            mes = speakerMessage[1].strip()
            res["replies"].append({"speaker" : speaker, "message": mes})
            conversations[leaderId]["history"].append(speaker+": "+mes+"\n")

        #print("Updated Local History: ", conversations[leaderId]["history"])
        return res

    #formats the given context JSON into a string with all the necessary context about the group for GPT
    def getContextString(cont):
        context = "The Party consists of the real player " + cont["players"][0]["name"]+ ", " + getUnitString(cont["players"][0]) +";\n"
        context += "and the following Bots/NPCs:\n"
        lastBotIdx = len(cont["bots"])
        for index in range(0, lastBotIdx):
            bot = cont["bots"][index]
            context += bot["name"] + ", "
            context += getUnitString(bot)
            if(index == lastBotIdx-1):
                context+=".\n"
            #elif(index == lastBotIdx-2):
            #    context+=", and\n"
            else:
                context += ";\n"
        
        context += "All members of the party are Level " + str(cont["players"][0]["level"]) + "."
        return context        
        return tempContext;

    def getReplies(sysMessage, historyMessage, playerName):
        response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-0613",
        messages=[sysMessage, historyMessage],
        temperature=1,
        max_tokens=382,
        top_p=1,
        frequency_penalty=0.35,
        presence_penalty=0,
        stop=[playerName+":"]   #if the model decides to write for the player, this should interrupt it
        )
        return response['choices'][0]['message']['content']
    
    def getUnitString(unitObj):
        specString = ""
        if(unitObj.get("spec") != None):
            specString = unitObj["spec"] + " "
        return "the " + unitObj["gender"] + " " + unitObj["race"] + " " + specString + unitObj["class"]

    #debug
    registerGroup(1234)
    app.run(debug=True)

