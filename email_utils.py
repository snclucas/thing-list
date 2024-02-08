from threading import Thread

from flask import render_template
from flask_mail import Message
from app import app, mail


def threading(f):
    def wrapper(*args, **kwargs):
        thr = Thread(target=f, args=args, kwargs=kwargs)
        thr.start()
    return wrapper


@threading
def send_email(subject, sender=None, recipients=None, text_body=None, html_body=None)->(bool, str):
    """
    Sends an email with the provided details.

    Args:
        subject (str): The subject of the email.
        sender (str, optional): The sender of the email. If not provided, the default sender from the application config will be used.
        recipients (list or str, optional): The recipients of the email. Can be a list of email addresses or a single email address string.
        text_body (str, optional): The text body of the email.
        html_body (str, optional): The HTML body of the email.

    Returns:
        tuple: A tuple containing a boolean value indicating whether the email was sent successfully and a string message.

    Note:
        The method should be called within a thread if used in multi-threaded environments.
    """
    if text_body is None:
        return False, "No text body provided"

    if html_body is None:
        return False, "No html body provided"

    if subject is None:
        return False, "No subject provided"

    if app.config['ENVIRONMENT'] != 'production':
        return False

    if sender is None:
        sender = app.config['ADMINS'][0]

    with app.app_context():
        msg = Message(subject, sender=sender, recipients=recipients)
        msg.body = text_body
        msg.html = html_body
        mail.send(msg)

    return True, "Email sent"


def inventory_invite_email(user, token: str):
    text_body = render_template(template_name_or_list='email/inventory_invite.txt', user=user.username, token=token)
    html_body = render_template(template_name_or_list='email/inventory_invite.html', user=user.username, token=token)

    send_email("New user registration",
               sender=app.config['ADMINS'][0],
               recipients=[user.email],
               text_body=text_body,
               html_body=html_body)



def new_registration_email(user, token: str):
    text_body = render_template('email/user_registration.txt', user=user.username, token=token)
    html_body = render_template('email/user_registration.html', user=user.username, token=token)

    send_email("New user registration",
               sender=app.config['ADMINS'][0],
               recipients=[user.email],
               text_body=text_body,
               html_body=html_body)


def send_password_reset_email(user):
    token = user.get_reset_password_token()
    send_email('[Microblog] Reset Your Password',
               sender=app.config['ADMINS'][0],
               recipients=[user.email],
               text_body=render_template('email/reset_password.txt',
                                         user=user, token=token),
               html_body=render_template('email/reset_password.html',
                                         user=user, token=token))
