#for creating login form we should enable CSRF as True
WTF_CSRF_ENABLED = True
SECRET_KEY = 'you-will-never-guess'

SQLALCHEMY_DATABASE_URI = 'sqlite3:///'posts.db