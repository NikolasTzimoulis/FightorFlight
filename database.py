import sqlite3 as lite
import time
import datetime
import encodings

taskDB = "fof.db"
con = lite.connect(taskDB)
with con:    
    cur = con.cursor()
    #cur.execute("CREATE TABLE Tasks(id INTEGER PRIMARY KEY, name TEXT UNIQUE, complete INTEGER);")
    #cur.execute("CREATE TABLE Fights(startTime INTEGER, endTime INTEGER, value INTEGER, taskId INTEGER, FOREIGN KEY(taskId) REFERENCES Tasks(id));")
    #cur.execute("SELECT id, name, complete FROM Tasks ORDER BY complete")
    
    #cur.execute("SELECT * FROM Fights WHERE value = 1 ORDER BY endTime DESC LIMIT 1")
    #lastTask = cur.fetchall()[0]
    #print datetime.datetime.fromtimestamp(lastTask[0]).strftime('%Y-%m-%d, %H:%M'), datetime.datetime.fromtimestamp(lastTask[1]).strftime('%Y-%m-%d, %H:%M'), lastTask[2:]
    #cur.execute("DELETE FROM Fights WHERE startTime = ? AND endTime = ? AND value = ? AND taskID = ?", lastTask)
    
    cur.execute("SELECT * FROM Fights WHERE taskID = (SELECT id FROM Tasks WHERE name = 'lala')")
    print cur.fetchall()
    cur.execute("DELETE FROM Fights WHERE taskID = (SELECT id FROM Tasks WHERE name = 'lala')")
    cur.execute("DELETE FROM Tasks WHERE name = 'lala'")
    