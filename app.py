import os

from flask_qrcode import QRcode
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, render_template
import flask_resize
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect

# Create and name Flask app
app = Flask("HomeLabApp", static_url_path="", static_folder="static")

app.config['RESIZE_URL'] = 'https://mysite.com/'
app.config['RESIZE_ROOT'] = 'C:\\Users\\simon clucas\\PycharmProjects\\retro-database\\static/uploads/'

resize = flask_resize.Resize(app)


app.config['SECRET_KEY'] = '\xfd{H\xe5<\x95\xf9\xe3\x96.5\xd1\x01O<!\xd5\xa2\xa0\x9fR"\xa1\xa8'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# database connection
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'retrodb'

app.config['UPLOAD_FOLDER'] = 'static/uploads/'

app.config['FILE_UPLOADS'] = 'static/uploads/'


app.debug = os.environ.get('DEBUG', False)

csrf = CSRFProtect(app)

QRcode(app)

SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'mysql://{0}:{1}@{2}/{3}'.format(app.config['MYSQL_USER'],
                                                                                     app.config['MYSQL_PASSWORD'],
                                                                                     app.config['MYSQL_HOST'],
                                                                                     app.config['MYSQL_DB']))

app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI

db = SQLAlchemy(app, session_options={"expire_on_commit": "False"})

# Flask BCrypt will be used to salt the user password
flask_bcrypt = Bcrypt(app)

# Associate Flask-Login manager with current app
login_manager = LoginManager()
login_manager.init_app(app)


@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html', title='404', error=error), 404
