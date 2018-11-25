from api.db import db_connection
from datetime import datetime
import pytz
from flask_restplus import (inputs,
                            Model,
                            Namespace,
                            reqparse,
                            Resource,
                            fields,
                            abort)
from flask_jwt_extended import (jwt_required,
                                get_jwt_identity)
from typing import List
import requests
from . import api
from api import models
import rethinkdb as r
from functools import wraps

ns: Namespace = api.namespace('filters',
                              description='Filters Endpoint',
                              decorators=[])


@ns.response(404, 'Filter with given \'filter_id\' not found')
def check_if_filter_exists(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        filter_id = kwargs['filter_id']
        with db_connection() as conn:
            filter_exists = r.table('filters').get_all(
                filter_id).count().eq(1).run(conn)
            if not filter_exists:
                return abort(404, 'Filter Not Found')
        return f(*args, **kwargs)
    return wrapper

@ns.route('/')
class Filters(Resource):
    post_parser = ns.parser()
    post_parser.add_argument('type',
                             choices=('text', 'image', 'audio'),
                             location='json',
                             required=True,
                             nullable=False)

    def get(self):
        with db_connection() as conn:
            filters = r.table('filters').run(conn)
        return list(filters)

    def post(self):
        args = self.post_parser.parse_args()
        input_type = args['type']
        with db_connection() as conn:
            filters = r.table('filters').filter({
                'input_type': input_type
            }).run(conn)
        return list(filters)

@ns.route('/<string:filter_id>')
class Filter(Resource):
    method_decorators=[check_if_filter_exists]
    def get(self, filter_id):
        with db_connection() as conn:
            f = r.table('filters').get(filter_id).run(conn)
        return f
