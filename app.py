import os

from flask_qrcode import QRcode
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, render_template
import flask_resize
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect


from dotenv import load_dotenv
load_dotenv('.env')

# Create and name Flask app
app = Flask("ThingList", static_url_path="", static_folder="static")

app.config['RESIZE_URL'] = os.environ.get('RESIZE_URL', '')
app.config['RESIZE_ROOT'] = os.environ.get('RESIZE_ROOT', '')

resize = flask_resize.Resize(app)


app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', '')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# database connection
app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST', '')
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER', '')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD', '')
app.config['MYSQL_DB'] = os.environ.get('MYSQL_DB', '')

app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', '')

app.config['FILE_UPLOADS'] = os.environ.get('FILE_UPLOADS', '')


app.debug = os.environ.get('DEBUG', bool(os.environ.get('DEBUG', '')))

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
