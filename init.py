def creatte_app():
    ...
    app = Flask(duffy)
    ...
    from .core.views import core as core_blueprint
    app.register_blueprint(
        core_blueprint,
        url_prefix='/api/v1/core'
    )
