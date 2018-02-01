from flask import Flask

app = Flask(__name__)

from netsim_app import views
