from flask_jwt_extended import jwt_required, get_jwt_identity

from flask_restplus import (Resource,
                            Namespace)
from . import api
from api.db import db_connection
import rethinkdb as r

ns: Namespace = api.namespace('users', description='Chats Ednpoint',
                              decorators=[jwt_required])


# @ns.route('/<string:user_id>')
# class Users(Resource):
#     pass


@ns.route('/<string:user_id>/filters')
class UserFilters(Resource):
    def get(self, user_id):
        user_id = get_jwt_identity()
        with db_connection() as conn:
            filters = r.table('filters').filter(
                lambda f: r.table('users').get(user_id)[
                    'added_filter_ids'].contains(f['id'])
            ).run(conn)
        return list(filters)

    post_parser = ns.parser()
    post_parser.add_argument('filter_id',
                             location='json',
                             required=True,
                             nullable=False)

    def post(self, user_id):
        args = self.post_parser.parse_args()
        filter_id = args['filter_id']
        user_id = get_jwt_identity()
        with db_connection() as conn:
            user_already_has_filter = r.table('users').get(user_id)['added_filter_ids'].contains(filter_id).run(conn)
            if user_already_has_filter:
                return 
            r.table('users').get(user_id).update(
                lambda user: {
                    'added_filter_ids': user['added_filter_ids'].append(filter_id)
                }
            ).run(conn)
        return
