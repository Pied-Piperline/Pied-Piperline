from flask_jwt_extended import (jwt_required,
                                get_jwt_identity)
from flask_restplus import (Resource,
                            fields, abort)
from . import api

ns = api.namespace(
    'messages', description='Messages Endpoint', decorators=[jwt_required])


@ns.route('/<string:message_id>/apply_filter')
class Message(Resource):
    def post(self, message_id):
        raise NotImplementedError
