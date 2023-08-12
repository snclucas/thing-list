import os

from elasticsearch import Elasticsearch
from flask_qrcode import QRcode
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, render_template
import flask_resize
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect


from dotenv import load_dotenv

if not load_dotenv('.env'):
    if not load_dotenv('../.env'):
        raise Exception("Could not read environment file")

__PUBLIC__ = 2
__PRIVATE__ = 0
__OWNER__ = 0
__COLLABORATOR__ = 1
__VIEWER__ = 2

# Create and name Flask app
app = Flask("ThingList", static_url_path="", static_folder="static")

app.config['RESIZE_URL'] = os.environ.get('RESIZE_URL', '')
app.config['RESIZE_ROOT'] = os.environ.get('RESIZE_ROOT', '/tmp')

resize = flask_resize.Resize(app)

ELASTICSEARCH_URL = os.environ.get('ELASTICSEARCH_URL')


app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', '')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# database connection
app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST', '')
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER', '')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD', '')
app.config['MYSQL_DB'] = os.environ.get('MYSQL_DB', '')

app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', '')

app.config['FILE_UPLOADS'] = os.environ.get('FILE_UPLOADS', '')

app.config['POSTS_PER_PAGE'] = os.environ.get('POSTS_PER_PAGE', 10)


app.debug = os.environ.get('DEBUG', bool(os.environ.get('DEBUG', '')))

csrf = CSRFProtect(app)

QRcode(app)

app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True

SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'mysql://{0}:{1}@{2}/{3}'.format(app.config['MYSQL_USER'],
                                                                                     app.config['MYSQL_PASSWORD'],
                                                                                     app.config['MYSQL_HOST'],
                                                                                     app.config['MYSQL_DB']))

app.config['ELASTICSEARCH_URL'] = ELASTICSEARCH_URL

app.elasticsearch = Elasticsearch([app.config['ELASTICSEARCH_URL']]) \
        if app.config['ELASTICSEARCH_URL'] else None


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
