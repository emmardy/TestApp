from app import db

#CREATE A CLASS NAMED MYPOSTS BECAUSE DATABSES ARE IN OBJECTS AND CLASSES in SQLALchemy
class MyPosts(db.model):

	__tablename__ = "posts"
	id = db.column(db.Integer, primary_key=True)
	title = db.column(db.String, nullable=False)
	Description = db.column(db.String, nullable=False)

    def __init__(self,title,description):
    	self.title = title
    	self.description = description 

    	#__repr__ tells flask how to print the objects
    def__repr__(self):
         return '<title{}'.format(self.title) 	
    	