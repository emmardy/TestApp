from flask import Flask, render_template, redirect, url_for, request, session, flash, g
from functools import wraps
from app import app #from app package import app variable
import sqlite3 # this is the db im using for this app

app.secret_key = "never-try-to-guess"
app.database = 'sample.db'  #name of the database 

#LOGIN Decorator
def login_required(f):  # this is login_required function
    @wraps(f) #this is wrapper funtion
    def wrap(*args,**kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Login First')
            return redirect(url_for('login'))
    return wrap   

#FRONT PAGE DECORATOR 
@app.route('/') #frontpage decorator
@login_required
def home():
    g.db = connect_db() #g is variable in flask that stores the global user/holds a session once logged in
    cur = g.db.execute('select * from posts') #cur is the object that holds the connection
    posts = [dict(title=row[0], description=row[1]) for row in cur.fetchall()]
    g.db.close()
    return render_template('index.html',posts = posts)
                                     
	#return " WELCOME TO OUR WEBPAGE !"
@app.route('/welcome') #welcome page decorator
def welcome():
     return render_template('welcome.html')	

#LOGIN 
@app.route('/login', methods=['GET', 'POST']) #loginpage decorator
def login():
    error = None
    if request.method == 'POST':
        if request.form['username'] != 'admin' or request.form['password'] != 'loop':
            error = 'username password doesn\'t match.'
        else:
            session['logged_in'] = True
            flash('You are logged in Successfully')
            return redirect(url_for('home'))
    return render_template('login.html', error=error)

#LOGOUT
@app.route('/logout') #logout decorator
@login_required
def logout():
    session.pop('logged_in', None)
    flash('You are logged out !')
    return redirect(url_for('welcome'))

#DATABASE CONNECTION
def connect_db():
    return sqlite3.connect(app.database)


