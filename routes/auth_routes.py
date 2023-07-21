
from flask import current_app, Blueprint, render_template, request, flash, redirect, url_for

from app import login_manager, flask_bcrypt
from flask_login import (login_required, login_user, logout_user, confirm_login)

from database_functions import find_user
from models import User

auth_flask_login = Blueprint('auth_flask_login', __name__, template_folder='templates')


@auth_flask_login.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST" and "username" in request.form:
        username = request.form["username"]
        user = find_user(username_or_email=username)
        if user and flask_bcrypt.check_password_hash(user.password, request.form["password"]) and user.is_active:
            remember = request.form.get("remember", "no") == "yes"

            if login_user(user, remember=remember):
                flash("Logged in!")
                return redirect(url_for('main.profile', username=user.username).replace('%40', '@'))
            else:
                flash("unable to log you in")

    return render_template("auth/login.html")


#
# Route disabled - enable route to allow user registration.
#
@auth_flask_login.route("/register", methods=["GET", "POST"])
def register():

    current_app.logger.info(request.form)

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']

        # generate password hash
        password_hash = flask_bcrypt.generate_password_hash(request.form['password'])

        # prepare User
        new_user = User(username=username, email=email, password=password_hash)
        print(new_user)

        try:
            new_user.save()
            if login_user(new_user, remember=False):
                flash("Logged in!")
                return redirect('/')
            else:
                flash("unable to log you in")
        except Exception as err:
            flash("unable to register with that email address")
            current_app.logger.error("Error on registration - possible duplicate emails")

    return render_template("auth/register.html")


@auth_flask_login.route("/reauth", methods=["GET", "POST"])
@login_required
def reauth():
    if request.method == "POST":
        confirm_login()
        flash(u"Reauthenticated.")
        return redirect(request.args.get("next") or '/admin')

    templateData = {}
    return render_template("auth/reauth.html", **templateData)


@auth_flask_login.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.")
    return redirect('/login')


@login_manager.unauthorized_handler
def unauthorized_callback():
    return redirect('/login')


@login_manager.user_loader
def load_user(id):
    if id is None:
        redirect('/login')

    user = User.query.filter_by(id=id).first()
    if user.is_active:
        return user
    else:
        return None
