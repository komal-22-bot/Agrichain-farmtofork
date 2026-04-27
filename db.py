import mysql.connector

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="student",
    database="agridb"
)

cursor = db.cursor(dictionary=True)
print("DB connected successfully")
