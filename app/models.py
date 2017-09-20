import json
from app import db, bcrypt
from datetime import datetime
from flask import jsonify

class User(db.Model):

    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password = db.Column(db.String(160), nullable=False)
    registered_on = db.Column(db.DateTime, nullable=False)
    authenticated = db.Column(db.Boolean, default=False)
    bulbs = db.relationship('Bulb', backref='owner', lazy='dynamic')
    groups = db.relationship('Group', backref='owner', lazy='dynamic')
    locations = db.relationship('Location', backref='owner', lazy='dynamic')
    confirmed = db.Column(db.Boolean, default=False, nullable=False)
    confirmed_on = db.Column(db.DateTime, nullable=True)
    last_location = db.Column(db.Integer)

    def __init__(self, email, nickname, password, confirmed, confirmed_on=None):
        self.email = email
        self.nickname = nickname
        self.password = bcrypt.generate_password_hash(password)
        self.registered_on = datetime.now()
        self.confirmed = confirmed
        self.confirmed_on = confirmed_on

    @property
    def is_authenticated(self):
    	return self.authenticated

    @property
    def is_active(self):
    	return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        try:
            return unicode(self.id)
        except NameError:
            return str(self.id)

    def __repr__(self):
        return '<User %r>' % (self.email)

    def serialize(self):
        bulbs = self.bulbs
        return {
            'id': self.id,
            'nickname': self.nickname,
            'email': self.email,
            'bulbs': [b.serialize() for b in self.bulbs if self.bulbs is not None],
            'locations': [l.serialize() for l in self.locations if self.locations is not None]
        }

class Bulb(db.Model):
    __tablename__ = 'bulb'

    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(120), index=True)
    bulb_type = db.Column(db.String(30))
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    friend_id = db.Column(db.Integer)

    location_id = db.Column(db.Integer, db.ForeignKey('location.id'))
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))
    power = db.Column(db.Boolean, default=False)
    brightness = db.Column(db.Integer, default=10)

    def __repr__(self):
        return '<Bulb %r>' % (self.name)

    def __getitem__(self, item):
        return getattr(self, item)

    def __setitem__(self, item, value):
        self.item = value

    def serialize(self):
        power_state = 'Off' if self.power == False else 'True'
        location = Location.query.filter_by(id=self.location_id).first()
        if location is None:
            return {"error":"Bulb is created without a location. This shouldn't have happened."}
        response =  {
            'id': self.id,
            'name': self.name,
            'bulb_type': self.bulb_type,
            'owner': {
                'owner_id': self.owner_id,
                'owner_nickname': User.query.get(self.owner_id).nickname
                },
            'location': {
                'location_id': location.id,
                'location_name': location.name
                },
            'power': power_state,
            'brightness': self.brightness
        }
        return response

    def serialize_state(self): 
        power_state = 'Off' if self.power == False else 'On'
        return {'id': self.id,
            'name': self.name,
            'state': {
                'state_bool': self.power,
                'state_string': power_state
            }
        }


class Location(db.Model):
    __tablename__ = 'location'

    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(120), index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    bulbs = db.relationship('Bulb', backref='location', lazy='joined')
    groups = db.relationship('Group', backref='location', lazy='dynamic')

    def __repr__(self):
        return '<Location %r>' % (self.name)

    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
            'owner': {
                'owner_id': self.owner_id,
                'owner_nickname': User.query.get(self.owner_id).nickname
            },
            'bulbs': [b.serialize() for b in self.bulbs if b is not None]
        }

class Group(db.Model):
    __tablename__ = 'group'

    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(120), index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'))
    bulbs = db.relationship('Bulb', backref='group', lazy='dynamic' )
    power = db.Column(db.Boolean, default=False)
    brightness = db.Column(db.Integer, default=10)

    def __repr__(self):
            return '<Group %r>' % (self.name)

    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
            'owner': {
                'owner_id': self.owner_id,
                'owner_nickname': User.query.get(self.owner_id).nickname
            },
            'location': {
                'location_id': self.location_id,
                'location_name': Location.query.get(self.location_id).name
            },
            'bulbs' : [b.serialize() for b in self.bulbs if b is not None]
        }


class Scene(db.Model):
    __tablename__ = 'scene'

    id = db.Column(db.Integer, primary_key = True)
    scene_name = db.Column(db.String(120), index= True)
    
    def __repr__(self):
        return '<Scene %r>' % (self.name)

    def serialize(self): 
        return {
               'id':self.id,
               'scene_name':self.scene_name
        }   


class Entry_Scene(db.Model):
        __tablename__ = 'entry_scene'

        id = db.Column(db.Integer,primary_key = True)
        brightness = db.Column(db.Integer, default = 10)
        color = db.Column(db.String(30),index=True)
        location_id = db.Column(db.Integer, db.ForeignKey('location.id'))

        def __repr__(self):
            return'<Entry_Scene %r>' %(self.name)

        def serialize(self):
                return {
                    'id' : self.id,
                    'brightness' : self.brightness,
                    'color' : self.color,
                    'location' : self.location
                }


class Shared_control(db.Model):

    __tablename__ = 'owner_table'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String, db.ForeignKey('user.email'))
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'))

    def __repr__(self):
        return '<Owner %r>' % (self.email)

    def serialize(self):
        return {
                'id': self.id,
                'email': self.email,
                'location': self.location_id
                }
