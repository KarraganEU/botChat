import db
import prompts
import openai
import argparse
import os
import logging
import tiktoken
from openai import OpenAI

client = None

maxToken=382
tokenBudget = 4096-maxToken
settingsMap = {
    "replyMode": {
        "player" : "You should reply out-of-character, i.e. as if you were the player controlling the character.",
        "rp" : "You should reply in-character, i.e. as if you were the speaking character themselves. Try to tonally match the races of the speakers (for example like a stereotypical dwarf for dwarves, elvish verbiage for night elves, etc). ",
        "rpshort": "You should reply in-character, i.e. as if you were the speaking character themselves, but do not be overly verbose. Try to tonally match the races of the speakers (for example like a stereotypical dwarf for dwarves; eloquent and flowery language for night elves, etc). But be succinct, do not ramble."
    }
}

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
        "speaker": "Ayanna"
        },
        {
        "message": "Aye, lad! It appears we all agree then. Let us prepare ourselves and make our way to Stratholme together. We shall bring light, justice, and steel down upon the undead scum!",
        "speaker": "Bromos"
        }
    ]}

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

    logLevel = logging.DEBUG if debug else logging.INFO
    
    ch = logging.StreamHandler()
    fh = logging.FileHandler("log.log", encoding='utf-8')
    logging.basicConfig(level=logLevel, format='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s', handlers=[ch,fh])

    logger = logging.getLogger()

    if(apiKey == None):
        apiKey = getKeyFromFile()
        if(apiKey == None):
            logger.error("Expected OpenAI API KEY as Environment Variable API_KEY or in key.txt")    
    print(apiKey)

    global client
    client = OpenAI(api_key=apiKey)

    if(not(os.path.isfile(db.DB_NAME)) or debug):
        db.init()
    
    db.initFromDB(inMemDB) #could also be a return value

    return debug, port

def appendAndSave(message, leaderId, cache):
    """Saves the given message to the DB and appends it to the inMem-Conversation Object"""
    #if(not(message.endswith("\n"))): 
    #    message += "\n"
    #the new line is only "necessary" for open ai to get better prompting and the prompt builder automatically appends it
    #the dbs (in-mem and sqlite) do not need to worry about the \n
    cache[leaderId]["history"].append(message)
    split =  message.split(":")
    db.saveMessage(split[1].strip(), split[0].strip(), leaderId)

def changeAndPersistSetting(leaderId, settingName, newValue, cache):
    changeSetting(leaderId,settingName,newValue, cache)
    db.updateSettings(settingName, newValue, leaderId)

def changeSetting(leaderId, settingName, newValue, cache):
    cache[leaderId][settingName] = newValue

def makeGroup(leaderId,cache): 
    cache[leaderId] = {"history" : []}

def registerGroup(leaderId,cache, mode="rpshort"):
    if(cache.get(leaderId)!=None):
        return
    makeGroup(leaderId, cache)
    changeAndPersistSetting(leaderId, "mode", mode, cache)    
    logging.getLogger().info("registering group with leaderId: " + str(leaderId) + " with mode " +mode)

## BOT REPLIES

def makeReply(context, leaderId, cache):
    logger = logging.getLogger()
    groupConversation = cache[leaderId]
    modeString = settingsMap["replyMode"][groupConversation["mode"]]
    playerName = context["players"][0]["name"]
    sysQuery = prompts.systemBase + "\n" + getContextString(context) + "\n" + prompts.postContext + playerName + ".\n" + modeString
    sysObj = {"role":"system", "content": sysQuery}

    logger.info(sysQuery)
    sysCount = getTokenCount(sysQuery)
    #allow for historyculling. Only the <lastn> messages in the stored history should be send to GPT
    tempHistory = ""
    history = []
    #we need to start with the last messages to always get the latest, but need to append the history in chronological order, hence the double reverse
    #technically, one history would be sufficient, but this way we don't have to .join the array in every loop to get the raw token count
    #alternatively, we could discard tempHistory and only save the raw token count we're looping over, but depending on the tokenizer, this would perhaps be less accurate
    for message in reversed(groupConversation["history"]):        
        nextMessage = message
        if(not(nextMessage.endswith("\n"))):
            nextMessage += "\n"
        if(getTokenCount(nextMessage + tempHistory) + sysCount > tokenBudget):
            logger.info("Reached Token limit, culling history")
            break;
        history.append(nextMessage)
        tempHistory += nextMessage
    
    history = ''.join(reversed(history))

    logger.info(history)
    historyObj = {"role":"user", "content": history}
    
    #temp
    #return debugReply
    
    reply = getReplies(sysObj, historyObj, playerName)
    logger.info("--------------------------------------------------")
    logger.info(f"OpenAI API Response: {reply}")
    logger.info("---------------------------------------------------")
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
        appendAndSave(stripped, leaderId, cache)
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
    response = client.chat.completions.create(
    model="gpt-3.5-turbo-0613",
    messages=[sysMessage, historyMessage],
    temperature=1,
    max_tokens=maxToken,
    top_p=1,
    frequency_penalty=0.35,
    presence_penalty=0,
    stop=[playerName+":"]   #if the model decides to write for the player, this should interrupt it
    )
    return response.model_dump()['choices'][0]['message']['content']

def getUnitString(unitObj):
    specString = ""
    if(unitObj.get("spec") != None):
        specString = unitObj["spec"] + " "
    return "the " + unitObj["gender"] + " " + unitObj["race"] + " " + specString + unitObj["class"]

def getFileContents(filename):
    """ Given a filename,
        return the contents of that file
    """
    try:
        with open(filename, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        print("'%s' file not found" % filename)

def getKeyFromFile():
    return getFileContents("key.txt")

def getTokenCount(text) -> int:
    """Return the number of tokens in a string."""
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    return len(encoding.encode(text))
