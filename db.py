import sqlite3
import ast
import util

DB_NAME = "database.db"

def init():
    print("Creating Database...")
    connection = sqlite3.connect(DB_NAME)

    with open('schema.sql') as f:
        connection.executescript(f.read())

    cur = connection.cursor()

    connection.commit()
    connection.close()

def getConnection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def saveMessage(message, sender, leaderId: int):
    conn = getConnection()
    conn.execute('INSERT INTO history (leaderId, sender, content) VALUES (?, ?, ?)', (int(leaderId), sender, message))
    conn.commit()
    conn.close()

def updateSettings(settingName, newValue, leaderId):
    conn = getConnection()
    settings = conn.execute('SELECT * FROM settings WHERE leaderId = ?', (leaderId,)).fetchone()
    if(settings==None):
        settings={settingName: newValue}
        conn.execute("INSERT INTO settings (leaderId, settings) VALUES (?,?)", (int(leaderId), str(settings)))
    else:        
        newSettings = ast.literal_eval(settings["settings"])
        newSettings[settingName] = newValue
        conn.execute("UPDATE settings SET settings = ? WHERE leaderId=?", (str(newSettings), int(leaderId)))
    conn.commit()
    conn.close()

def eraseHistory(leaderId):
    conn = getConnection()
    conn.execute('DELETE FROM history WHERE leaderId = ?', (leaderId,))

    conn.commit()
    conn.close()

def initFromDB(inMemDB):
    conn = getConnection()
    settings = conn.execute('SELECT * FROM settings').fetchall()
    history = conn.execute('SELECT * FROM history ORDER BY id').fetchall()

    for settingResult in settings:
        leaderId = int(settingResult["leaderId"])
        group = inMemDB.get(leaderId)
        if(group==None):
            util.makeGroup(leaderId, inMemDB)
        settingDict = ast.literal_eval(settingResult["settings"])
        for k,v in settingDict.items():
            inMemDB[leaderId][k] = v

    for message in history:        
        leaderId = int(message["leaderId"])
        mes = ""
        mes += message["sender"] 
        mes += ": "
        mes += message["content"]
        inMemDB[leaderId]["history"].append(mes)
    conn.close()
