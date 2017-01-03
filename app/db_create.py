from app import db
from models import MyPosts

#CREATE DB
db.create_all()

#INSERT IN DB
db.session.add(MyPosts("Hello", "WELCOME"))
db.session.add(MyPosts("Well", "LETS DO SOME PYTHON"))

#COMMIT THE CHANGES
db.session.commit()