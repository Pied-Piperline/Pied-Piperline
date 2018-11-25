from flask import Flask
from werkzeug.contrib.fixers import ProxyFix
from flask_cors import CORS

app = Flask(__name__, static_folder='tmp')
CORS(app)
app.wsgi_app = ProxyFix(app.wsgi_app)
app.url_map.strict_slashes = False


def init_app():
    from .apis import add_apis
    add_apis(app)
    return app
