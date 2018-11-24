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

ns: Namespace = api.namespace('filters',
                              description='Filters Ednpoint',
                              decorators=[])


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
