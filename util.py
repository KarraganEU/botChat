import db
import prompts
import openai
import argparse
import os

settingsMap = {
    "replyMode": {
        "player" : "You should reply out-of-character, i.e. as if you were the player controlling the character.",
        "rp" : "You should reply in-character, i.e. as if you were the speaking character themselves. Try to tonally match the races of the speakers (for example like a stereotypical dwarf for dwarves, elvish verbiage for night elves, etc). ",
        "rpshort": "You should reply in-character, i.e. as if you were the speaking character themselves, but do not be overly verbose. Try to tonally match the races of the speakers (for example like a stereotypical dwarf for dwarves; eloquent and flowery language for night elves, etc). But be succinct, do not ramble."
    }
}

def init(inMemDB):
    parser = argparse.ArgumentParser()
    #parser.add_argument("--replyMode", help="Whether the bot should reply in-character or out of character", choices=['rpshort', 'rp', 'player'], default='rpshort')
    parser.add_argument("--key")
    parser.add_argument("--port", default=5000)
    parser.add_argument('-debug', action=argparse.BooleanOptionalAction, default=False)
    args = parser.parse_args()
    apiKey = args.key
    debug = args.debug
    port = args.port
    #apiKey = os.environ.get('API_KEY')
    if(apiKey == None):
        print("ERROR: Expected OpenAI API KEY as Environment Variable API_KEY")    
    openai.api_key = apiKey

    if(not(os.path.isfile(db.DB_NAME))): #or debug):
        db.init()
    
    db.initFromDB(inMemDB) #could also be a return value

    return debug, port



def appendAndSave(message, leaderId, conversations):
    """Saves the given message to the DB and appends it to the inMem-Conversation Object"""
    #if(not(message.endswith("\n"))): 
    #    message += "\n"
    #the new line is only "necessary" for open ai to get better prompting and the prompt builder automatically appends it
    #the dbs (in-mem and sqlite) do not need to worry about the \n
    conversations[leaderId]["history"].append(message)
    split =  message.split(":")
    db.saveMessage(split[1].strip(), split[0].strip(), leaderId)

def changeAndPersistSetting(leaderId, settingName, newValue, conversations):
    changeSetting(leaderId,settingName,newValue, conversations)
    db.updateSettings(settingName, newValue, leaderId)

def changeSetting(leaderId, settingName, newValue, conversations):
    conversations[leaderId][settingName] = newValue

def makeGroup(leaderId,conversations): 
    conversations[leaderId] = {"history" : []}

def registerGroup(leaderId,conversations, mode="rpshort"):
    if(conversations.get(leaderId)!=None):
        return
    makeGroup(leaderId, conversations)
    changeAndPersistSetting(leaderId, "mode", mode, conversations)
    print("registering group with leaderId: " + str(leaderId) + " with mode " +mode)

## BOT REPLIES

def makeReply(context, leaderId, conversations):
    groupConversation = conversations[leaderId]
    modeString = settingsMap["replyMode"][groupConversation["mode"]]
    playerName = context["players"][0]["name"]
    sysQuery = prompts.systemBase + "\n" + getContextString(context) + "\n" + prompts.postContext + playerName + ".\n" + modeString
    sysObj = {"role":"system", "content": sysQuery}

    print(sysQuery)

    #allow for historyculling. Only the <lastn> messages in the stored history should be send to GPT
    history = ""
    lastn = 100
    startn = max(0, len(groupConversation["history"])-lastn)
    for index in range(startn, len(groupConversation["history"])):
        history += groupConversation["history"][index]
        if(not(history.endswith("\n"))):
            history += "\n"
    historyObj = {"role":"user", "content": history}
    
    print(history)
    #temp
    #return debugReply        
    
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
        appendAndSave(stripped, leaderId, conversations)
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
    return prompts.debugContext;

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