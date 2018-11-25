from flask_jwt_extended import (jwt_required,
                                get_jwt_identity)
from flask_restplus import (Resource,
                            fields, abort)
from . import api
from api.db import db_connection
import rethinkdb as r
import requests
from functools import wraps
ns = api.namespace(
    'messages', description='Messages Endpoint', decorators=[jwt_required])


@ns.response(404, 'Filter with given \'filter_id\' not found')
def check_if_filter_exists(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user_id = get_jwt_identity()
        filter_id = kwargs['filter_id']
        with db_connection() as conn:
            filter_exists = r.table('filters').get_all(
                filter_id).count().eq(1).run(conn)
            if not filter_exists:
                return abort(404, 'Filter Not Found')
            user_has_this_filter = r.table('users').get(
                user_id)['added_filter_ids'].contains(filter_id).run(conn)
            if not user_has_this_filter:
                return abort(403, 'You can not apply this filter since you have not added this filter to your user\'s filters')
        return f(*args, **kwargs)
    return wrapper


@ns.response(404, 'Message with given \'message_id\' not found')
def check_if_message_exists(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user_id = get_jwt_identity()
        message_id = kwargs['message_id']
        with db_connection() as conn:
            message_exists = r.table('messages').filter({
                'message_id': message_id,
                'receiver_id': user_id
            }).count().eq(1).run(conn)
            if not message_exists:
                return abort(404, 'Message Not Found')
        return f(*args, **kwargs)
    return wrapper


@ns.route('/<string:message_id>/applicable_filters')
class MessageApplicableFilters(Resource):
    method_decorators = [check_if_message_exists]

    def get(self, message_id):
        user_id = get_jwt_identity()
        with db_connection() as conn:
            filters = r.table('filters').filter(
                lambda f: r.table('users').get(user_id)['added_filter_ids'].contains(f['id']).and_(
                    f['input_type'].eq(
                        r.table('values').get(
                            r.table('messages').filter({
                                'message_id': message_id,
                                'receiver_id': user_id,
                            })[-1]['value_ids'][-1]
                        )['type']
                    )
                )
            ).run(conn)
        return list(filters)


@ns.route('/<string:message_id>/apply_filter/<string:filter_id>')
class MessageApplyFilter(Resource):
    method_decorators = [check_if_message_exists, check_if_filter_exists]

    def post(self, message_id, filter_id):
        user_id = get_jwt_identity()
        with db_connection() as conn:
            value = r.table('values').get(
                r.table('messages').filter({
                    'message_id': message_id,
                    'receiver_id': user_id
                })[0]['value_ids'][-1]
            ).run(conn)
            f = r.table('filters').get(filter_id).run(conn)
            if value['type'] == 'text':
                res = requests.post(
                    f['external_url'],
                    json={
                        'value': value['content']
                    }
                )
                try:
                    content = res.json()['value']
                except:
                    raise NotImplementedError

                new_value = {
                    'type': f['output_type'],
                    'content': content
                }
            elif value['type'] == 'image':
                res = requests.post(
                    f['external_url'],
                    data=value['content']
                )
                new_value = {
                    'type': f['output_type'],
                    'content': res.content
                }
            generated_value = r.table('values').insert(new_value).run(conn)
            if 'generated_keys' not in generated_value or len(generated_value['generated_keys']) != 1:
                raise NotImplementedError
            value_generated_id = generated_value['generated_keys'][0]
            r.table('messages').filter({
                'message_id': message_id,
                'receiver_id': user_id
            }).update(
                lambda message: {
                    'value_ids': message['value_ids'].append(value_generated_id),
                    'filter_ids': message['filter_ids'].append(filter_id)
                }
            ).run(conn)
            v = r.table('values').get(value_generated_id).run(conn)
        return v
