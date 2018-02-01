from netsim_app import app
from netsim_app.views import socketio
socketio.run(app,debug=True,port=8080)
