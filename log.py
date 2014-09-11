import sqlite3 as lite
import datetime, os

taskDB = "fof.db"
logFileName = 'log.txt'
valueSymbols = ['?', '+', '-']

con = lite.connect(taskDB)
with con:    
    cur = con.cursor()
    #cur.execute("DELETE FROM ThoughtLog")
    #con.commit()
    tasks = {}
    cur.execute("SELECT id, name FROM Tasks")
    for tid, tName in cur.fetchall():
        tasks[tid] = tName
    cur.execute("SELECT * FROM Fights")
    rows = cur.fetchall()
    rows.sort(key=lambda x: x[1])
    lastDate = ""
    logFile = open(logFileName, 'w')
    for row in rows:
        theDate = datetime.datetime.fromtimestamp(row[1]).strftime('%Y-%m-%d')
        if not theDate == lastDate:
            print theDate
            logFile.write((theDate+'\n').encode('utf-8'))
            lastDate = theDate
        line = '\t' + datetime.datetime.fromtimestamp(row[1]).strftime("%H:%M") + '\t' + valueSymbols[row[2]] + " " + tasks[row[3]] #+ str(row[3])
        #print line
        logFile.write((line+'\n').encode('utf-8'))
    logFile.close()
os.startfile(logFileName)
            