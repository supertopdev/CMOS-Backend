from __future__ import annotations

import os

import inject
from api import blueprints, error_handler_mapping
from cache import cache
from config.logging import setup_logging
from flask import Flask
from flask_cors import CORS
from flask_marshmallow import Marshmallow
from models.database import db, migrate
from services.cloud_storage import CloudStorageService
from services.opentok import OpenTokClient


def set_config(app: Flask, environment: str):
    config_module = "config.config."
    match environment:
        case "test":
            config_module = f"{config_module}TestConfig"
        case "local":
            config_module = f"{config_module}LocalConfig"
        case "production":
            config_module = f"{config_module}ProductionConfig"
        case "staging" | _:
            config_module = f"{config_module}StagingConfig"
    app.logger.debug(f"Using {config_module}")
    app.config.from_object(config_module)


def create_app() -> Flask:
    app = Flask(__name__)
    environment = os.environ.get("ENVIRONMENT", "")
    environment = environment.lower()
    set_config(app, environment)
    setup_logging(app)
    cache.init_app(app, {"CACHE_TYPE": "RedisCache", "CACHE_REDIS_URL": app.config.get("REDIS_URL")})

    with app.app_context():
        db.init_app(app)
        migrate.init_app(app, db)

        for blueprint in blueprints:
            app.register_blueprint(blueprint=blueprint)

        for key in error_handler_mapping:
            for value in error_handler_mapping[key]:
                app.register_error_handler(value, key)

        def configure_with_binder(binder):
            binder.bind(
                CloudStorageService,
                CloudStorageService(app.config.get("STORAGE_BUCKET")),
            )
            binder.bind(
                OpenTokClient,
                OpenTokClient(
                    app.config.get("VONAGE_API_KEY"),
                    app.config.get("VONAGE_API_SECRET"),
                ),
            )

        # Configure a shared injector.
        if environment == "test":
            inject.clear_and_configure(configure_with_binder)
        else:
            inject.configure(configure_with_binder)

    ma = Marshmallow(app)  # noqa: F841
    app.logger.info("Running app!")
    return app


app = create_app()
CORS(app, resources={r"/*": {"origins": "*"}})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=app.config.get("PORT", 8080), debug=app.config.get("DEBUG", True))
