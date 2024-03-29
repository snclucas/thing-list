import re
import uuid

from MySQLdb import OperationalError
from sqlalchemy.exc import SQLAlchemyError
from flask import current_app, Blueprint, render_template, request, flash, redirect, url_for
from app import db
from app import login_manager, flask_bcrypt, app
from flask_login import (login_required, login_user, logout_user, confirm_login)

from database_functions import find_user, save_new_user, find_user_by_token, activate_user_in_db, find_user_by_username, \
    find_user_by_email
from email_utils import send_email
from models import User
import strings

auth_flask_login = Blueprint('auth_flask_login', __name__, template_folder='templates')



@auth_flask_login.context_processor
def inject_front_end_strings():
    """
    Inject strings into the front end
    :return:
    """
    return dict(strings=strings)



@auth_flask_login.route(rule='/forgot-password', methods=['GET', 'POST'])
def reset_password_form():
    """
    Reset Password Form

    Handles the logic for resetting user passwords.

    Returns:
        template: 'auth/reset_password.html' - If the request method is 'GET'
        template: 'auth/reset_password.html' with flash message - If the username is empty
        template: 'auth/reset_password.html' with flash message - If unable to update the user token
        template: 'auth/login.html' with flash message - If the reset password email is sent successfully

    Method:
        GET:
            Renders the 'auth/reset_password.html' template.

        POST:
            Retrieves the username from the request form data.
            If the username is empty, renders the 'auth/reset_password.html' template with a flash message.

            Otherwise, finds the user with the given username or email.
            If the user exists, generates a confirmation token and updates the user's token in the database.
            If an error occurs during the database update, flashes a message and renders the 'auth/reset_password.html' template.

            Constructs the text and HTML bodies of the email using the 'email/user_registration.txt' and 'email/user_registration.html' templates and the username and confirmation token
    *.

            Sends the email with the subject "Password reset" to the user's email address.

            Flashes a message indicating that an email will be sent if the account exists.

            Renders the 'auth/login.html' template.
    """
    if request.method == "GET":
        return render_template('auth/reset_password.html')
    else:
        username = request.form.get('username', '').strip()
        if not username:
            flash("Username cannot be empty.")
            return render_template(template_name_or_list="auth/reset_password.html")

        potential_user = find_user_by_username(username) or find_user_by_email(username)
        if potential_user:
            user_email = potential_user.email
            confirmation_token = uuid.uuid4().hex
            confirmation_token = flask_bcrypt.generate_password_hash(confirmation_token)
            potential_user.token = confirmation_token
            try:
                db.session.commit()
            except SQLAlchemyError as err:
                current_app.logger.error(msg=f"Error updating user token: {str(err)}", exc_info=True)
                flash("Unable to reset password")

            text_body = render_template(template_name_or_list='email/user_registration.txt', user=username,
                                        token=confirmation_token)
            html_body = render_template(template_name_or_list='email/user_registration.html', user=username,
                                        token=confirmation_token)
            send_email(subject="Password reset", sender=app.config['ADMINS'][0], recipients=[user_email],
                       text_body=text_body, html_body=html_body)

        flash("If this account exists, an email will be sent with instructions to reset the password")
        return render_template(template_name_or_list="auth/login.html")


@auth_flask_login.route(rule='/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """
    Args:
        token: The token generated for password reset.

    Returns:
        None

    This method handles the password reset functionality. It expects a token parameter to be passed in the URL. If the request method is GET, it renders the 'new_password.html' template
    *. If the request method is POST, it retrieves the supplied password from the form, sanitizes it, and generates a password hash using flask_bcrypt.

    It then searches for a user with the provided token using the 'find_user_by_token' method. If a user is found and the user is not activated and the user's token matches the provided
    * token, it updates the user's password with the generated password hash and commits the changes to the database. If there is an error during the update, an error message is logged and
    * a flash message is displayed indicating that the password reset was unsuccessful.

    If no user is found or if the user is already activated or the user's token does not match the provided token, a flash message is displayed indicating that the password reset was unsuccessful
    *.

    Finally, it renders the 'login.html' template.
    """
    if request.method == "GET":
        return render_template('auth/new_password.html')
    else:

        supplied_password = sanitize(request.form.get("password"))
        # generate password hash
        password_hash = flask_bcrypt.generate_password_hash(supplied_password)

        supplied_token = flask_bcrypt.generate_password_hash(token)
        user_ = find_user_by_token(token=supplied_token)

        if user_ is not None and not user_.activated and user_.token == token:
            user_.password = password_hash
            try:
                db.session.commit()
            except SQLAlchemyError as err:
                current_app.logger.error(msg=f"Error updating user password: {str(err)}", exc_info=True)
                flash("Unable to reset password")

            flash("Password reset")
        else:
            flash("Unable to reset password")

        return render_template('auth/login.html')


def sanitize(input_string: str) -> str:
    """
    Sanitizes the given input string by encoding and decoding it using unicode_escape.

    Args:
        input_string (str): The input string to be sanitized.

    Returns:
        str: The sanitized input string.
    """
    # Perform input sanitization
    return input_string.encode('unicode_escape').decode()


@auth_flask_login.route(rule="/login", methods=["GET", "POST"])
def login():
    """
    Method: login

    This method is used to authenticate a user and log them into the system.

    URL: /login
    Methods: GET, POST

    Parameters:
        - None

    Returns:
        - None
    """

    if request.method == "POST" and "username" in request.form:

        username = sanitize(request.form.get("username"))
        password = sanitize(request.form.get("password"))

        user = find_user(username_or_email=username)
        if user and flask_bcrypt.check_password_hash(user.password, password) and user.is_active:
            remember = request.form.get("remember", "no") == "yes"

            if user.activated == 0:
                flash("Account not activated")
                return render_template("auth/login.html")

            if login_user(user, remember=remember):
                return redirect(url_for('main.profile', username=user.username).replace('%40', '@'))
            else:
                flash("Unable to log you in")
        else:
            flash("Unable to log you in")

    allow_registrations = (int(app.config['ALLOW_REGISTRATIONS']) == 1)
    return render_template(template_name_or_list="auth/login.html", allow_registrations=allow_registrations)


@auth_flask_login.route(rule="/activate-user/<token>", methods=["GET"])
def activate_user(token):
    """
    Activate a user based on the given token.

    :param token: The activation token provided in the URL.
    :type token: str
    :return: The rendered template after user activation.
    :rtype: str
    """
    supplied_token = flask_bcrypt.generate_password_hash(token)
    user_ = find_user_by_token(token=supplied_token)
    template = "auth/login.html"

    if user_ is not None and not user_.activated and user_.token == token:
        status, msg = activate_user_in_db(user_id=user_.id)
        if status:
            flash("You are now an activated Thing!")
        else:
            flash("Unable to activate user")

    return render_template(template)


@auth_flask_login.route(rule="/passwd", methods=["GET", "POST"])
@login_required
def change_password():
    current_app.logger.info(request.form)

    if request.method == 'POST':

        username = request.form['username']

        try:
            user_ = find_user(username_or_email=username)
            if user_ is not None:
                confirmation_token = uuid.uuid4().hex
                confirmation_token = flask_bcrypt.generate_password_hash(confirmation_token)

                text_body = render_template(template_name_or_list='email/reset_password.txt', user=username, token=confirmation_token)
                html_body = render_template(template_name_or_list='email/reset_password.html', user=username, token=confirmation_token)
                send_email(subject="Password change", sender=app.config['ADMINS'][0], recipients=[user_.email],
                           text_body=text_body, html_body=html_body)

        except Exception as err:
            current_app.logger.error("Error on registration - possible duplicate emails")

        flash("If this account exists, an email will be sent with instructions to reset the password")
        return render_template("auth/reset_password.html")


    else:
        return render_template("auth/reset_password.html")


def password_check(password):
    """
    Check if a password meets the specified criteria.

    Parameters:
    password (str): The password to be checked.

    Returns:
    dict: A dictionary containing the result of the password check.
        - 'password_ok' (bool): True if the password meets the criteria, False otherwise.
        - 'length_error' (bool): True if the password length is less than 8 characters, False otherwise.
        - 'digit_error' (bool): True if the password does not contain any digits, False otherwise.
        - 'uppercase_error' (bool): True if the password does not contain any uppercase letters, False otherwise.
        - 'lowercase_error' (bool): True if the password does not contain any lowercase letters, False otherwise.
        - 'symbol_error' (bool): True if the password does not contain any symbols, False otherwise.
    """
    # calculating the length
    length_error = len(password) < 8
    # searching for digits
    digit_error = re.search(pattern=r"\d", string=password) is None
    # searching for uppercase
    uppercase_error = re.search(pattern=r"[A-Z]", string=password) is None
    # searching for lowercase
    lowercase_error = re.search(pattern=r"[a-z]", string=password) is None
    # searching for symbols
    symbol_error = re.search(pattern=r"\W", string=password) is None
    # overall result
    password_ok = not (length_error or digit_error or uppercase_error or lowercase_error or symbol_error)

    return {
        'password_ok': password_ok,
        'length_error': length_error,
        'digit_error': digit_error,
        'uppercase_error': uppercase_error,
        'lowercase_error': lowercase_error,
        'symbol_error': symbol_error,
    }


@auth_flask_login.route(rule="/register", methods=["GET", "POST"])
def register():
    """
    Registers a new user in the application.

    Route: `/register`
    Methods: `GET`, `POST`

    __Args__:
        - None

    __Returns__:
        - If registrations are not allowed, renders the `auth/register.html` template with `allow_registrations` set to `False`.
        - If a `POST` request is made:
            - If the `username` field is empty, flashes an error message and renders the `auth/register.html` template.
            - If the `email` field is empty, flashes an error message and renders the `auth/register.html` template.
            - If the `email` field is not a valid email address (using a simple regex validation), flashes an error message and renders the `auth/register.html` template.
            - If the supplied password does not meet the criteria, flashes an error message and renders the `auth/register.html` template.
            - If a user with the same email or username already exists, flashes an error message and renders the `auth/register.html` template.
            - Otherwise, generates a password hash, generates a confirmation token, creates a new `User` with the provided details, and attempts to save the new user.
                - If the user is successfully added, constructs the text and HTML bodies for the registration email, sends the email to the user's email address, flashes a success message
    *, and renders the `auth/login.html` template.
                - If there is an error adding the user, flashes an error message.
        - If a `GET` request is made or an exception occurs, renders the `auth/register.html` template with `allow_registrations` set to the value of `ALLOW_REGISTRATIONS` from the application
    *'s config.

    __Raises__:
        - Any exception that occurs during the registration process.

    """
    allow_registrations = (int(app.config['ALLOW_REGISTRATIONS']) == 1)

    if not allow_registrations:
        return render_template(template_name_or_list="auth/register.html", allow_registrations=allow_registrations)

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        supplied_password = request.form.get('password', '').strip()

        if not username:
            flash("Username cannot be empty.")
            return render_template(template_name_or_list="auth/register.html", allow_registrations=allow_registrations)

        if not email:
            flash("Email cannot be empty.")
            return render_template(template_name_or_list="auth/register.html", allow_registrations=allow_registrations)

        # Simple email validation, you might want to use a more robust method in production
        if not re.match(pattern=r"[^@]+@[^@]+\.[^@]+", string=email):
            flash("Invalid email address.")
            return render_template(template_name_or_list="auth/register.html", allow_registrations=allow_registrations)

        password_check_results = password_check(supplied_password)
        if not password_check_results['password_ok']:
            flash("Password does not meet the criteria")
            return render_template(template_name_or_list="auth/register.html", allow_registrations=allow_registrations)

        existing_user = find_user_by_username(username) or find_user_by_email(email)
        if existing_user:
            flash("User with that email or username already exists")
            return render_template(template_name_or_list="auth/register.html", allow_registrations=allow_registrations)

        # generate password hash
        password_hash = flask_bcrypt.generate_password_hash(supplied_password)

        confirmation_token = uuid.uuid4().hex
        confirmation_token = flask_bcrypt.generate_password_hash(confirmation_token)

        # prepare User
        new_user = User(username=username, email=email, password=password_hash, token=confirmation_token)

        try:
            user_added, msg, user = save_new_user(new_user)
            if user_added:
                text_body = render_template(template_name_or_list='email/user_registration.txt', user=username, token=confirmation_token)
                html_body = render_template(template_name_or_list='email/user_registration.html', user=username, token=confirmation_token)
                send_email(subject="New user registration", sender=app.config['ADMINS'][0], recipients=[email],
                           text_body=text_body, html_body=html_body)
                flash("Check your email for an activation link!")
                return render_template("auth/login.html")
            else:
                flash("Unable to register you at this time")
        except Exception as err:
            current_app.logger.error(msg=f"Exception occurred: {str(err)}", exc_info=True)
            flash("Unable to register with that email address")
            current_app.logger.error("Error on registration - possible duplicate emails")

    return render_template(template_name_or_list="auth/register.html", allow_registrations=allow_registrations)


@auth_flask_login.route(rule="/reauth", methods=["GET", "POST"])
@login_required
def reauth():
    if request.method == "POST":
        confirm_login()
        flash(u"Reauthenticated.")
        return redirect(request.args.get("next") or '/admin')

    template_data = {}
    return render_template(template_name_or_list="auth/reauth.html", **template_data)


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
    """
    Load User

    Loads the user associated with the given ID.

    Parameters:
    - id (int): The ID of the user to load.

    Returns:
    - User: The user with the specified ID, if found and active. If the ID is None or the user is not found or inactive, returns None.

    Note:
    - This method is decorated with the `@login_manager.user_loader` decorator to register it as the user loader function for the current login manager. It is automatically called when loading
    * a user based on the ID.
    """
    if id is None:
        redirect('/login')

    try:
        user = User.query.filter_by(id=id).first()
    except OperationalError as err:
        current_app.logger.error(msg=f"Error loading user: {str(err)}", exc_info=True)
        return render_template(template_name_or_list='500.html', message="error"), 500
    if user is not None:
        if user.is_active:
            return user
        else:
            return None
