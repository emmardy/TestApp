import sqlite3 # we are using sqlite3 as the database 

# create a new database if the database doesn't already exist
with sqlite3.connect('sample.db') as connection:

    # get a cursor object used to execute SQL commands
    c = connection.cursor()

    # create the table
    c.execute("CREATE TABLE posts(title TEXT, description TEXT)")

    # insert dummy data into the table
    c.execute('INSERT INTO posts VALUES("Hello", "WELCOME.")')
    c.execute('INSERT INTO posts VALUES("Well", "LETS DO SOME PYTHON")')
    c.execute('INSERT INTO posts VALUES("GOOD", "GOOD MORNING")')
    c.execute('INSERT INTO posts VALUES("Okay", "EVERYTHING WILL BE OKAY !!")')
