from flask import render_template, flash, redirect, make_response, session, url_for, request, g, jsonify, abort
from flask_login import login_user, logout_user, current_user, login_required, current_user
from flask_jwt import JWT, jwt_required, current_identity
from sqlalchemy.sql import func
import dateutil.parser
import datetime
from app import app, db, lm, bcrypt
from .token import generate_confirmation_token, confirm_token
from .email import send_email
from .forms import LoginForm, EditNicknameForm, CreateForm, AddBulbForm, AddLocationForm, AddGroupForm, LocationSelector
from .models import User, Location, Bulb, Group, Scene, Shared_control
from .decorators import check_confirmed


######################################################################################
##
## PAGE VIEWING
##
######################################################################################

# INDEX
@app.route('/', methods=['GET','POST'])
@app.route('/index')
@login_required
@check_confirmed
def index():
  user=g.user
  #grab list of user's locations for group and bulb selectors
  location_choices = [(location.id, location.name) for location in Location.query.filter_by(owner_id=user.id)]
  #create a default location w/ name "home" for user
  if len(location_choices) == 0:
    location = Location(name="Home", owner_id=user.id)
    db.session.add(location)
    db.session.commit()
    return redirect(redirect_url())
  #make sure user has their location set. if not, initalize it to their first location
  #this will be the first on the dropdown anyway
  if not user.last_location and len(location_choices) > 0:
    user.last_location = location_choices[0][0]
    db.session.add(user)
    db.session.commit()
    return redirect(redirect_url())
  last_location_name = Location.query.get(user.last_location).name
  #grab all the bulbs and groups from their location to display for control
  bulbs = user.bulbs.filter_by(location_id=user.last_location)
  groups = user.groups.filter_by(location_id=user.last_location)
  #create forms to add new locations, groups, and bulbs
  location_form=AddLocationForm()
  bulb_form=AddBulbForm()
  group_form = AddGroupForm()
  #add form to select current location
  location_selection_form = LocationSelector()
  bulb_form.location.choices = location_choices
  group_form.location.choices = location_choices
  location_selection_form.selector.choices = location_choices
  #grab list of user's bulbs for group add
  group_form.bulbs.choices = [(bulb.id, bulb.name) for bulb in Bulb.query.filter_by(owner_id=user.id)]
  return render_template('index.html', title='Home', user=user,
    bulbs=bulbs, groups=groups, current_location=last_location_name, location_form=location_form, bulb_form=bulb_form, group_form=group_form,
    location_selector=location_selection_form)

#ADD BULB FORM RENDER (WORKS WITH @APP.ROUTE(... METHODS=['POST']) IN BULB CONTROLS)
@app.route('/bulb/add', methods=['GET'])
@login_required
def addBulb():
  locations = [(location.id, location.name) for location in Location.query.filter_by(owner_id=user.id)]
  form = AddBulbForm(request.form)
  form.location.choices = locations
  return render_template('add_bulb.html', form=form, title="Adding bulb")

#ADD GROUP FORM RENDER (WORKS WITH @APP.ROUTE(... METHODS=['POST']) IN GROUP CONTROLS)
@app.route('/group/add', methods=['GET'])
@login_required
def addGroup():
  locations = [(location.id, location.name) for location in Location.query.filter_by(owner_id=user.id)]
  bulbs = [(bulb.id, bulb.name) for bulb in Bulb.query.filter_by(owner_id=user.id)]
  form = AddGroupForm(request.form)
  form.location.choices = locations
  return render_template('add_group.html', form=form, title="Adding group")

#LOCATION SWITCH FORM
@app.route('/location/switch', methods=['GET'])
@login_required
def switchLocation():
  locations = [(location.id, location.name) for location in Location.query.filter_by(owner_id=user.id)]
  form = LocationSelector(request.form)
  form.selector.choices = locations
  return render_template('switch_location.html', form=form, title="Changing location")

#BULB INFO PAGE
@app.route('/bulb/<int:id>', methods=['GET'])
@login_required
def showBulb(id):
  bulb = Bulb.query.get(id)
  if bulb == None:
    not_found()
  return render_template('bulb_page.html', bulb=bulb, title=bulb.name)

#USER PAGE
@app.route('/user/<nickname>')
@login_required
@check_confirmed
def user(nickname):
  user = User.query.filter_by(nickname=nickname).first()
  if user == None:
    flash("User %s not found." % nickname)
    return redirect(url_for(index))
  bulbs = Bulb.query.filter_by(owner_id=user.id)
  locations = Location.query.filter_by(owner_id=user.id)
  groups = Group.query.filter_by(owner_id=user.id)
  return render_template('user.html', user=user, bulbs=bulbs, groups=groups, locations=locations)

#CREATE ACCOUNT PAGE
@app.route('/create', methods=['GET', 'POST'])
def create():
  form = CreateForm()
  if form.validate_on_submit():
        user = User(email=func.lower(form.email.data), nickname=form.nickname.data,
          password=form.password.data, confirmed=False)
        user.authenticated = True
        db.session.add(user)
        db.session.commit()

        token = generate_confirmation_token(user.email)
        confirm_url = url_for('confirm_email', token=token, _external=True)
        html = render_template('activate.html', confirm_url=confirm_url)
        subject = "Please confirm email for Connected Light Example"
        send_email(user.email, subject, html)

        login_user(user)
        flash('A confirmation email has been sent.')
        return redirect(url_for('unconfirmed'))
  return render_template('create.html', form=form)

#CONFIRM ACCOUNT PAGE
@app.route('/confirm/<token>', methods=['GET'])
def confirm_email(token):
  try:
    email = confirm_token(token)
  except:
    flash('This confirmation link is invalid or expired.', 'danger')
  user = User.query.filter_by(email=email).first_or_404()
  if user.confirmed:
    flash('Account already confirmed. Please login.', 'success')
  else:
    user.confirmed = True
    user.confirmed_on = datetime.datetime.now()
    user.authenticated = True
    db.session.add(user)
    db.session.commit()
    login_user(user)
    flash("You have confirmed your account. Thank you!", 'success')
  return redirect(url_for('index'))

#UNCONFIRMED ACCOUNT PAGE
@app.route('/unconfirmed')
@login_required
def unconfirmed():
  user = g.user
  if user.confirmed:
    return redirect(url_for(index))
  return render_template('user/unconfirmed.html', user=user, system_email=app.config['MAIL_DEFAULT_SENDER'])


#LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.user is not None and g.user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
      user = User.query.filter_by(email=func.lower(form.email.data)).first()
      remember = form.remember_me.data
      if user:
        if bcrypt.check_password_hash(user.password, form.password.data):
            user.authenticated = True
            db.session.add(user)
            db.session.commit()
            login_user(user, remember=remember)
            return redirect(url_for('index'))
      else:
        flash('User does not exist.')
        return redirect(url_for("login"))
    return render_template("login.html", title='Sign In', form=form)
#LOGOUT
@app.route('/logout', methods=['GET', 'POST'])
def logout():
  if g.user is not None and g.user.is_authenticated:
    user = current_user
    user.authenticated = False
    db.session.add(user)
    db.session.commit()
    logout_user()
  return render_template("logout.html")




######################################################################################
##
## CONTROL ENDPOINTS
##
######################################################################################

###
### USER HARDWARE/APP INFO CONTROLS
###

### BULB CONTROLS
#BULB SWITCH (POWER ON/OFF)
@app.route('/bulb/<int:id>/switch', methods=['POST'])
@login_required
def switchBulb(id):
  user= g.user
  bulb = Bulb.query.get(id)
  old_state = bulb.power
  if bulb is not None and bulb.owner == user:
    new_state = not bulb.power
    bulb.power = new_state
    db.session.add(bulb)
    #db.session.commit()
    # if this is the last bulb in a group to change state, change the group's state.
    group = bulb.group
    if group is not None:
      group_should_change = True
      for bulb in group.bulbs:
        if bulb.power == old_state:
          group_should_change = False
      if group_should_change:
        group.power = new_state
      db.session.add(group)
    db.session.commit()
  return redirect(redirect_url())

#BULB BRIGHTNESS CONTROL
@app.route('/bulb/<int:id>/dim', methods=['POST'])
@login_required
def dimBulb(id):
  user = g.user
  bulb = Bulb.query.get(id)
  value = request.form.get("brightness")
  if bulb is None:
    flash("Bulb not found. Could not set brightness.")
    return redirect(redirect_url())
  if bulb.owner != user:
    flash("No permissions to set brightness on this bulb.")
    flash(bulb.owner)
    return redirect(redirect_url())
  bulb.brightness = value
  db.session.add(bulb)
  db.session.commit()
  return redirect(redirect_url())

#ADD BULB
@app.route('/bulb/add', methods=['POST'])
@login_required
def validateBulb():
  user = g.user
  locations = [(location.id, location.name) for location in Location.query.filter_by(owner_id=user.id)]
  form = AddBulbForm(request.form)
  form.location.choices = locations
  if form.validate_on_submit():
     bulb = Bulb(name=form.name.data, owner=user, owner_id=user.id, location_id=form.location.data, bulb_type=form.bulb_type.data)
     db.session.add(bulb)
     db.session.commit()
     flash("New bulb added.")
  else:
     flash("Failed to add bulb.")
  return redirect(redirect_url())

#DELETE BULB
@app.route('/bulb/<int:id>/delete', methods=['GET'])
@login_required
def deleteBulb(id):
  user = g.user
  bulb = Bulb.query.get(id)
  if bulb is not None and bulb.owner_id == user.id:
    db.session.delete(bulb)
    db.session.commit()
    flash("Bulb \"" + bulb.name + "\" deleted.")
  else:
    flash("Error deleting bulb \"" + bulb.name + "\".")
  return redirect(redirect_url())

### GROUP CONTROLS
#GROUP SWITCH (POWER ON/OFF)
@app.route('/group/<int:id>/switch', methods=['POST'])
@login_required
def switchGroup(id):
  user = g.user
  group = Group.query.get(id)
  if group is not None and group.owner == user:
    group.power = not group.power
    db.session.add(group)
    bulbs = group.bulbs.all()
    for bulb in bulbs:
      bulb.power =  group.power
      db.session.add(bulb)
    db.session.commit()
  return redirect(redirect_url())

#GROUP BRIGHTNESS CONTROL
@app.route('/group/<int:id>/dim', methods=['POST'])
@login_required
def dimGroup(id):
  user = g.user
  group = Group.query.get(id)
  value = request.form.get("brightness")
  if group is None:
    flash("Group not found. Could not set brightness.")
    return redirect(redirect_url())
  if group.owner != user:
    flash("No permissions to set brightness on this group.")
    return redirect(redirect_url())
  group.brightness = value
  db.session.add(group)
  bulbs = group.bulbs.all()
  for bulb in bulbs:
    bulb.brightness = group.brightness
    db.session.add(bulb)
  db.session.commit()
  return redirect(redirect_url())

#ADD GROUP
@app.route('/group/add', methods=['POST'])
@login_required
def validateGroup():
  user = g.user
  locations = [(location.id, location.name) for location in Location.query.filter_by(owner_id=user.id)]
  bulbs = [(bulb.id, bulb.name) for bulb in Bulb.query.filter_by(owner_id=user.id)]
  form = AddGroupForm(request.form)
  form.location.choices = locations
  form.bulbs.choices = bulbs
  if form.validate_on_submit():
      group = Group(name=form.name.data, owner=user, owner_id=user.id, location_id=form.location.data)
      group.bulbs.extend([Bulb.query.get(b) for b in form.bulbs.data])
      db.session.add(group)
      db.session.commit()
      flash("New group added.")
  else:
    flash("Failed to add group.")
  return redirect(redirect_url())

#DELETE GROUP
@app.route('/group/<int:id>/delete', methods=['GET'])
@login_required
def deleteGroup(id):
  user = g.user
  group = Group.query.get(id)
  if group is not None and group.owner_id == user.id:
    db.session.delete(group)
    db.session.commit()
    flash("Group \"" + group.name + "\" deleted.")
  else:
    flash("Error deleting group \"" + group.name + "\".")
  return redirect(redirect_url())

### LOCATION CONTROLS
#ADD LOCATION
@app.route('/location/add', methods=['POST'])
@login_required
def addLocation():
  user = g.user
  form = AddLocationForm()
  if form.validate_on_submit():
    location = Location(name=form.name.data, owner_id=user.id, owner=user)
    db.session.add(location)
    db.session.commit()
    flash("New location added.")
  else:
    flash("Failed to add location.")
  return redirect(redirect_url())

#DELETE LOCATION
@app.route('/location/<int:id>/delete', methods=['GET'])
@login_required
def deleteLocation(id):
  user = g.user
  location = Location.query.get(id)
  if location is not None and location.owner_id == user.id:
    db.session.delete(location)
    db.session.commit()
    flash("Location \"" + location.name + "\" deleted.")
  else:
    flash("Error deleting location \"" + location.name + "\".")
  return redirect(redirect_url())

#SWITCH LOCATION (CHANGE USER LAST_LOCATION)
@app.route('/location/select', methods=['POST'])
@login_required
def validateLocation():
  user = g.user
  form = LocationSelector()
  next_location_id = form.selector.data
  print form.selector.data
  next_location = Location.query.get(next_location_id)
  if next_location is not None and next_location.owner_id == user.id:
    user.last_location = next_location_id
    db.session.add(user)
    db.session.commit()
  return redirect(redirect_url())

## WEBAPP CONTROLS
#EDIT NICKNAME
@app.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
    form = EditNicknameForm(g.user.nickname)
    if form.validate_on_submit():
        g.user.nickname = form.nickname.data
        db.session.add(g.user)
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('edit'))
    else:
        form.nickname.data = g.user.nickname
    return render_template('edit.html', form=form)

#RESEND CONFIRMATION LINK
@app.route('/resend')
@login_required
def resend_confirmation():
  user = g.user
  token = generate_confirmation_token(user.email)
  confirm_url = url_for('confirm_email', token=token, _external=True)
  html = render_template('activate.html', confirm_url=confirm_url)
  subject = "Please confirm email for Connected Light Example"
  send_email(user.email, subject, html)
  flash ('A new confirmation email has been sent.', 'success')
  return redirect(url_for('unconfirmed'))





######################################################################################
##
## HELPERS/OBJECTS
##
######################################################################################

###
### REQUIRED HELPERS/OBJECTS FOR OTHER MODULES
###

#FLASK-JWT METHODS
def authenticate(email, password):
  print (email + ": " + password)
  user = User.query.filter_by(email=func.lower(email)).first()
  print user
  if user and bcrypt.check_password_hash(user.password, password):
    return user
  else:
    return bad_request("Password not accepted.")
def identity(payload):
  id = payload['identity']
  return User.query.get(id)
jwt = JWT(app, authenticate, identity)

#LOGIN-MANAGER
@lm.user_loader
def load_user(id):
    return User.query.get(int(id))

#GLOBALS MANAGER
@app.before_request
def before_request():
  g.user = current_user

###
### ERROR HANDLERS
###

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

# @app.errorhandler(400)
# def bad_request_error(error):
#   db.session.rollback()
#   print(error)
#   return 'Improper request. Check API usage.\n', 400

###
### GENERAL HELPER METHODS
###
def redirect_url(default='index'):
  return request.args.get('next') or \
         request.referrer or \
         url_for(default)
def bad_request(message):
  response = jsonify({"error":message})
  response.status_code = 400
  return response
def not_found():
  response = jsonify()
  response.status_code = 404
  return response

def created(object):
  type_ref = {Bulb: 'get_bulb',
              Location: 'get_location',
              Group: 'get_group',
              User: 'get_user'
  }
  response = jsonify(object.serialize())
  response.status_code = 201
  if type(object) in type_ref.keys():
    location_func = type_ref[type(object)]
    response.headers['location'] = url_for(location_func, id=object.id, _external=True)
    response.autocorrect_location_header = False
  return response
##METHODS BELOW SIMPLIFIED TO ABOVE CREATED()
# def created_bulb(object):
#   type_ref = {Bulb: 'get_bulb',
#               Location: 'get_location',
#               Group: 'get_group',
#               User: 'get_user'
#   }
#   if type(object) not in type_ref.keys():
#     print("Invalid object created.")
#   else:
#     print("Using: " + type_ref[type(object)])
#   resposne = jsonify(object.serialize())
#   response = jsonify(object.serialize())
#   response.status_code = 201
#   response.headers['location'] = url_for('get_bulb', id=object.id, _external=True)
#   response.autocorrect_location_header = False
#   return response
# def created_location(object):
#   response = jsonify(object.serialize())
#   response.status_code = 201
#   response.headers['location'] = url_for('get_bulb', id=object.id, _external=True)
#   response.autocorrect_location_header = False
#   return response
# def created_group(object):
#   response = jsonify(object.serialize())
#   response.status_code = 201
#   response.headers['location'] = url_for('get_group', id=object.id, _external=True)
#   response.autocorrect_location_header = False
#   return response
# def created_user(object):
#   response = jsonify(object.serialize())
#   response.status_code = 201
#   response.headers['location'] = url_for('get_user', id=object.id, _external=True)
#   response.autocorrect_location_header = False
#   return response

def successfully_deleted():
  response = jsonify()
  response.status_code = 204
  return response

###
### CONTEXTS AND FILTERS
###
@app.context_processor
def utility_processor():
  def translate_power(state):
    if (state == False):
      return 'Off'
    elif (state == True):
      return 'On'
    else:
      return 'Error'
  def translate_type(bulb_type):
    if (bulb_type == 'sleep'):
      #return "C by GE: Sleep Smart Light"
      return "SLEEP"
    elif (bulb_type == 'life'):
      #return "C by GE: Life Smart Light"
      return 'LIFE'
    elif (bulb_type == 'br30'):
      #return "C by GE: BR30 Life Smart Light"
      return 'OTHER'
    else:
      return "ERROR"
  return dict(translate_power=translate_power, translate_type=translate_type)
@app.template_filter('strftime')
def _jinja2_filter_datetime(date, fmt=None):
  if type(date) is not datetime.datetime:
    date = dateutil.parser.parse(date)
  native = date.replace(tzinfo=None)
  format='%b %d, %Y'
  return native.strftime(format)





######################################################################################
##
## API
##
######################################################################################

###
# BULBS
###

#ADD BULB
@app.route('/api/a/bulb', methods=['POST'])
@jwt_required()
def create_bulb():
  content = request.get_json(force=True)
  required_keys = [u'name', u'location_id', u'bulb_type']
  if not set(required_keys) <= set(content.keys()):
    return bad_request("Missing either \"name\", \"location_id\", or \"bulb_type\" in request.")
  location = Location.query.get(content['location_id'])
  if location is None or location.owner_id is not current_identity.id:
    return bad_request("User does not have permission to create bulbs on this location, or location does not exist.")
  bulb = Bulb(name=content['name'], owner=current_identity, owner_id=current_identity.id,
    location_id=content['location_id'], bulb_type=content['bulb_type'])
  db.session.add(bulb)
  db.session.commit()
  return created(bulb)

#EDIT BULB
@app.route('/api/a/bulb', methods=['PUT', 'PATCH'])
@jwt_required()
def update_bulb():
  content = request.get_json(force=True)
  required_keys = [u'id']
  if not set(required_keys) <= set(content.keys()):
    return bad_request("Bulb ID as \"id\" is required to update a bulb.")
  bulb = Bulb.query.get(content['id'])
  if bulb is None:
    return not_found()
  if bulb.owner_id is not current_identity.id:
    return bad_request("User does not have permission to update this bulb.")
  for key in content.keys():
    try:
      setattr(bulb, key, content[key])
    except AttributeError:
      continue
  db.session.add(bulb)
  db.session.commit()
  return jsonify(bulb.serialize())

#DELETE BULB
@app.route('/api/a/bulb', methods=['DELETE'])
@jwt_required()
def delete_bulb():
  content = request.get_json(force=True)
  required_keys = [u'id']
  if not set(required_keys) <= set(content.keys()):
    return bad_request("Bulb ID as \"id\" is required to delete a bulb.")
  bulb = Bulb.query.get(content['id'])
  if bulb is None:
    return not_found()
  if bulb.owner_id is not current_identity.id:
    return bad_request("User does not have permission to delete this bulb.")
  db.session.delete(bulb)
  db.session.commit()
  return successfully_deleted()

#GET BULB
@app.route('/api/a/bulb/<int:id>', methods=['GET'])
@jwt_required()
def get_bulb(id):
  bulb = Bulb.query.get(id)
  if bulb == None:
    return not_found()
  if bulb.owner_id is not current_identity.id:
    return bad_request("User does not have permission to view this bulb.")
  return jsonify(bulb.serialize())

#GET BULB POWER
@app.route('/api/a/bulb/<int:id>/power', methods=['GET'])
@jwt_required()
def get_bulb_state(id):
  bulb = Bulb.query.get(id)
  if bulb == None:
    not_found()
  if bulb.owner_id is not current_identity.id:
    return bad_request("User does not have permission to view this bulb.")
  return jsonify(bulb.serialize_state())

#CHANGE BULB POWER
@app.route('/api/a/bulb/<int:id>/power', methods=['POST', 'PUT', 'PATCH'])
@jwt_required()
def change_bulb_state(id):
  bulb = Bulb.query.get(id)
  if bulb == None:
    return not_found()
  content = request.get_json()
  if content['state'] == None or content['state'] not in [0, 1]:
    return bad_request("Attribute \"state\" must be set to either 1 (on) or 0 (off)")
  bulb.power = content['state']
  db.session.commit()
  return jsonify(bulb.serialize_state()), 200;

###
# GROUPS
###

#ADD GROUP
@app.route('/api/a/group', methods=['POST'])
@jwt_required()
def create_group():
  content = request.get_json(force=True)
  required_keys = [u'name', u'location_id', u'bulb_ids']
  if not set(required_keys) <= set(content.keys()):
    return bad_request("Missing either \"name\", \"location_id\", or \"bulb_ids\" in request.")
  location = Location.query.get(content['location_id'])
  if location is None or location.owner_id is not current_identity.id:
    return bad_request("User does not have permission to create groups on this location, or location does not exist.")
  if "bulb_ids" not in content or type(content['bulb_ids']) is not list:
    return bad_request("Group must contain at least one bulb, with \"bulb_ids\" as a list.")
  bulbs = []
  for b in content['bulb_ids']:
    bulb = Bulb.query.get(b)
    if bulb.owner_id == current_identity.id:
      bulbs.append(bulb)
    else:
      return bad_request("User does not have permissions on bulb #" + b +", or bulb does not exist.")
  group = Group(name=content['name'], owner=current_identity, owner_id = current_identity.id,
    location_id=content['location_id'], bulbs=bulbs)
  db.session.add(group)
  db.session.commit()
  return created(group)

#EDIT GROUP
@app.route('/api/a/group', methods=['PUT', 'PATCH'])
@jwt_required()
def update_group():
  content = request.get_json(force=True)
  required_keys = [u'id']
  if not set(required_keys) <= set(content.keys()):
    return bad_request("Group ID as \"id\" is required to update a group.")
  group = Group.query.get(content['id'])
  if group is None:
    return not_found()
  if group.owner_id is not current_identity.id:
    return bad_request("User does not have permission to update this group.")
  for key in content.keys():
    try:
      setattr(group, key, content[key])
    except AttributeError:
      continue
  db.session.add(group)
  db.session.commit()
  return jsonify(group.serialize())

#DELETE GROUP
@app.route('/api/a/group', methods=['DELETE'])
@jwt_required()
def delete_group():
  content = request.get_json(force=True)
  required_keys = [u'id']
  if not set(required_keys) <= set(content.keys()):
    return bad_request("Group ID as \"id\" is required to delete a group.")
  group = Group.query.get(content['id'])
  if group is None:
    return not_found()
  if group.owner_id is not current_identity.id:
    return bad_request("User does not have permission to delete this group.")
  db.session.delete(group)
  db.session.commit()
  return successfully_deleted()

#GET GROUP
@app.route('/api/a/group/<int:id>', methods=['GET'])
@jwt_required()
def get_group(id):
  group = Group.query.get(id)
  if group == None:
    return not_found()
  if group.owner_id is not current_identity.id:
    return bad_request("User does not have permission to view this group.")
  return jsonify(group.serialize())

###
# LOCATIONS
###

#GET LOCATION
@app.route('/api/a/location/<int:id>', methods=['GET'])
@jwt_required()
def get_location(id):
  location = Location.query.get(id)
  if location == None:
    not_found()
  return jsonify(location.serialize())

#ADD LOCATION
@app.route('/api/a/location', methods=['POST'])
@jwt_required()
def create_location():
  content = request.get_json(force=True)
  required_keys = [u'name']
  if not set(required_keys) <= set(content.keys()):
    return bad_request("Missing \"name\" attribute.")
  location = Location(name=content['name'], owner=current_identity, owner_id=current_identity.id)
  if "group_ids" in content and type(content['group_ids']) is list:
    groups = []
    for g in content['group_ids']:
      group = Group.query.get(g)
      if group.owner_id == current_identity.id:
        groups.append(group)
    location.groups = groups
  if "bulb_ids" in content and type(content['group_ids']) is list:
    bulbs = []
    for b in content['bulb_ids']:
      bulb = Bulb.query.get(b)
      if bulb.owner_id == current_identity.id:
        bulbs.append(bulb)
    location.bulbs = bulbs
  db.session.add(location)
  db.session.commit()
  return created(location)

#UPDATE LOCATION
@app.route('/api/a/location', methods=['PUT', 'PATCH'])
@jwt_required()
def update_location():
  content = request.get_json(force=True)
  required_keys = [u'id']
  if not set(required_keys) <= set(content.keys()):
    return bad_request("Location ID as \"id\" is required to update a location.")
  location = Location.query.get(content['id'])
  if location is None:
    return not_found()
  if location.owner_id is not current_identity.id:
    return bad_request("User does not have permission to update this location.")
  for key in content.keys():
    try:
      setattr(location, key, content[key])
    except AttributeError:
      continue
  db.session.add(location)
  db.session.commit()
  return jsonify(location.serialize())

#DELETE LOCATION
@app.route('/api/a/location', methods=['DELETE'])
@jwt_required()
def delete_location():
  content = request.get_json(force=True)
  required_keys = [u'id']
  if not set(required_keys) <= set(content.keys()):
    return bad_request("Location ID as \"id\" is required to delete a location.")
  location = Location.query.get(content['id'])
  if location is None:
    return not_found()
  if location.owner_id is not current_identity.id:
    return bad_request("User does not have permission to delete this location.")
  db.session.delete(location)
  db.session.commit()
  return successfully_deleted()

###
# USER
###

#GET USER
@app.route('/api/a/user/<int:id>', methods=['GET'])
@jwt_required()
def get_user(id):
  user = User.query.get(id)
  if user == None:
    return not_found()
  return jsonify(user.serialize())

#ADD USER
@app.route('/api/a/user', methods=['POST'])
def create_user():
  content = request.get_json(force=True)
  required_keys = [u'nickname', u'password', u'email']
  if not set(required_keys) <= set(content.keys()):
    return bad_request("Missing \'nickname\', \'email\', or \'password\' argument.")
  if User.query.filter_by(nickname=content['nickname']).first() is not None:
    return bad_request("Nickname already exists.")
  if User.query.filter_by(email=content['email']).first() is not None:
    return bad_request("Email is already used.")
  user = User(email=content['email'], nickname=content['nickname'],
            password=content['password'], confirmed=True, confirmed_on=datetime.datetime.now())
  # token = generate_confirmation_token(user.email)
  # confirm_url = url_for('confirm_email', token=token, _external=True)
  # user.confirm_url = confirm_url
  # html = render_template('activate.html', confirm_url=confirm_url)
  # subject = "Please confirm email for Connected Light Example"
  # send_email(user.email, subject, html)
  db.session.add(user)
  db.session.commit()
  return created(user)

#EDIT USER
@app.route('/api/a/user', methods=['PUT', 'PATCH'])
@jwt_required()
def update_user():
  content = request.get_json(force=True)
  required_keys = [u'id']
  if not set(required_keys) <= set(content.keys()):
    return bad_request("User ID as \"id\" is required to update a user.")
  user = User.query.get(content['id'])
  if user is None:
    return not_found()
  if user.id is not current_identity.id:
    return bad_request("User does not have permission to update this user.")
  for key in content.keys():
    try:
      setattr(user, key, content[key])
    except AttributeError:
      continue
  db.session.add(user)
  db.session.commit()
  return jsonify(user.serialize())

#DELETE USER
@app.route('/api/a/user', methods=['DELETE'])
@jwt_required()
def delete_user():
  content = request.get_json(force=True)
  required_keys = [u'id']
  if not set(required_keys) <= set(content.keys()):
    return bad_request("User ID as \"id\" is required to delete a user.")
  user = User.query.get(content['id'])
  if user is None:
    return not_found()
  if user.id is not current_identity.id:
    return bad_request("User does not have permission to delete this user.")
  db.session.delete(user)
  db.session.commit()
  return successfully_deleted()

###
# SCENES
###
# --CREATE SCENE--#
@app.route('/api/a/scene', methods=['POST'])
# @jwt_required
def create_scene():
  content = request.get_json(force=True)
  required_keys = [u'name', u'bulbs']  # We Need Name and bulb_id to Create a Scene
  if not set(required_keys) <= set(content.keys()):
    return bad_request("Missing \"name\", \"bulb_ids\" in your Request")
  if "bulb_ids" not in content or type(content['bulb_ids']) is not list:
    return bad_request("A Scene Must Have Atleast one Bulb, with \"bulb_ids\".")
  bulbs = []
  for b in content['bulbs']:

    bulb = Bulb.query.get(b.get('bulb_id'))
    if (bulb.owner_id == current_identity.id) or (bulb.friend_id == current_identity.id):
      # set a "brightness" and "color" fields

      bulb.brightness = b.get('brightness')
      bulb.color = b.get('color')
      bulbs.append(bulb)

    else:
      return bad_request("User doesn\t have permission on bulb #" + b + " ")

  scene = Scene(name=content(name), owner=current_identity, owner_id=current_identity.id, bulbs=bulbs)
  db.session.add(scene)
  db.session.commit()
  return created(scene)


# --DELETE SCENE--#
@app.route('/api/a/scene', methods=['DELETE'])
# @jwt_required
def delete_scene():
  content = request.get_json(force=True)
  required_keys = [u'id']
  if not set(required_keys) <= set(content.keys()):
    return bad_request("scene.id is required to delete this scene")
  scene = Scene.query.get(content['id'])
  if scene is None:
    return not_found()
  if scene.owner_id is not current_identity.id:
    return bad_request("You don\t have permission to make a delete request")
  db.session.delete(scene)
  db.session.commit()
  #return delete()


# --UPDATE SCENE--#
@app.route('/api/a/scene', methods=['PUT', 'PATCH'])
# @jwt_required()
def update_scene():
  content = request.get_json(force=True)
  required_keys = [u'name', u'bulb_ids', u'brightness', u'color']
  if not set(required_keys) <= set(content.keys()):
    return bad_request("Please Enter the scene \"name\",\"bulb_ids\", \"brightness\", and \"Color\" to update")
  scene = Scene.query.get(content['name'])
  if scene is None:
    return not_found()
  if scene.name is not current_identity.name:
    return bad_request("You are Not Allowed to Update")


# --CHANGE OWNER--#
@app.route('/api/a/share/location', methods=['PUT'])
# @jwt_required()
def add_friend():
  content = request.get_json(force=True)
  required_keys = [u'location_id', u'email']

  if not set(required_keys) <= set(content.keys()):
      return bad_request("Please Enter the scene 'location_id' and 'email' to share location")

  location = Location.query.get(int(content['location_id']))
  user = User.query.filter_by(email=content['email']).first()

  if user:
    if location:
        if location.owner_id is not current_identity.id:
            return bad_request("You don\t have permission")
        else:
          shared_ctrl = Shared_control(email=content['email'], location_id=int(content['location_id']))
          db.session.add(shared_ctrl)
          db.session.commit()
          return created(shared_ctrl)
    else:
        return bad_request("No location with this ID")
  else:
    return bad_request("No user have this email")
