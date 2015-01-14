import sqlite3 as lite
import datetime, os

taskDB = "fof.db"
logFileName = 'log.txt'
showOnlyID = None

def valueSymbols(val):
    if val == -1: return '-'
    elif val == 0: return '?'
    elif val == float("inf"): return '+'+u'\u221e'
    else: return '+'+str(int(round(val/60/60,0))) 
    ['?', '+', '-']

con = lite.connect(taskDB)
with con:    
    cur = con.cursor()
    #cur.execute("DELETE FROM ThoughtLog")
    #con.commit()
    tasks = {}
    cur.execute("SELECT id, name FROM Tasks")
    for tid, tName in cur.fetchall():
        tasks[tid] = tName
        print tid, tName
    if showOnlyID is None: 
        cur.execute("SELECT * FROM Fights")
    else:
        cur.execute("SELECT * FROM Fights WHERE taskId = ?", [showOnlyID])
    
    rows = cur.fetchall()
    rows.sort(key=lambda x: x[1])
    lastDate = ""
    logFile = open(logFileName, 'w')
    i = 0
    for row in rows:
        theDate = datetime.datetime.fromtimestamp(row[1]).strftime('%Y-%m-%d')
        if not theDate == lastDate:
            logFile.write((theDate+'\n').encode('utf-8'))
            lastDate = theDate
        line = '\t' + datetime.datetime.fromtimestamp(row[1]).strftime("%H:%M") + '\t' + valueSymbols(row[2]) + " " + tasks[row[3]] #+ str(row[3])
        #print line
        logFile.write((line+'\n').encode('utf-8'))
        i += 1000
    logFile.close()
os.startfile(logFileName)
            