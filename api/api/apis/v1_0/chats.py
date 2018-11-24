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
from . import api
import rethinkdb as r
from functools import wraps

ns: Namespace = api.namespace('chats', description='Chats Ednpoint',
                              decorators=[jwt_required])

value_model = ns.model(
    name='Value',
    model={
        'id': fields.String,
        'type': fields.String,
        'content': fields.Raw,
    }
)

message_model = ns.model(
    name='Message',
    model={
        'message_id': fields.String,
        'chat_id': fields.String,
        'sender_id': fields.String,
        'receiver_id': fields.String,
        'created_at': fields.String,
        'value_ids': fields.List(fields.Nested(value_model))
    }
)

chat_short_model: Model = ns.model(
    name='Short Chat Model',
    model={
        'id': fields.String,
        'name': fields.String,
        'last_message': fields.Nested({
            'sender_name': fields.String,
            'created_at': fields.DateTime,
            'content': fields.Raw,
            'type': fields.String
        }),
        'participants_count': fields.Integer
    }
)

chat_model: Model = ns.model(
    name='Chat',
    model={
        'id': fields.String(
            example='33bad3e9-4ac1-4c50-9dd3-38f11c1fd833'),
        'name': fields.String(
            example='Example Chat Name'),
        'messages': fields.List(fields.Nested(message_model)),
        'user_ids': fields.List(fields.String(
            example='54cefb93-972a-4a67-be2e-25d5c8592ff6')),
        'default_filter_ids': fields.List(fields.String(
            example='d7eda49c-8e8b-4d57-84ed-ae90264a3ab9'))
    }
)


@ns.response(403, 'This user has not permission to access this chat')
def check_access(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user_id = get_jwt_identity()
        chat_id = kwargs['chat_id']
        with db_connection() as conn:
            access_allowed = r.table('chats').get(
                chat_id)['user_ids'].contains(user_id).run(conn)
            if not access_allowed:
                return abort(403, 'You do not have permission to access this chat')
        return f(*args, **kwargs)
    return wrapper


@ns.response(404, 'Chat with given \'chat_id\' not found')
def check_if_chat_exists(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        chat_id = kwargs['chat_id']
        with db_connection() as conn:
            chat_exists = r.table('chats').get_all(
                chat_id).count().eq(1).run(conn)
            if not chat_exists:
                return abort(404, 'Chat Not Found')
        return f(*args, **kwargs)
    return wrapper


@ns.route('/')
class Chats(Resource):

    @ns.marshal_list_with(chat_short_model)
    def get(self):
        user_id = get_jwt_identity()
        with db_connection() as conn:
            chats = r.table('chats').filter(
                lambda chat:
                    chat['user_ids'].contains(user_id)
            ).merge(
                lambda chat: {
                    'last_message': r.table('messages').filter({
                        'chat_id': chat['id'],
                        'receiver_id': user_id,
                    }).order_by(r.desc('created_at'))[0].merge(
                        lambda message: {
                            'content': r.table('values').get(message['value_ids'][-1])['content'],
                            'sender_name': r.table('users').get(message['sender_id'])['name'],
                            'type': r.table('values').get(message['value_ids'][-1])['type']
                        }
                    ).pluck(
                        'created_at',
                        'sender_name',
                        'content',
                        'type'
                    ),
                    'participants_count': chat['user_ids'].count()
                }
            ).pluck(
                'id',
                'name',
                {
                    'last_message': [
                        'content',
                        'sender_name',
                        'type',
                        'created_at'
                    ]
                },
                'participants_count'
            ).run(conn)
        listed_chats = list(chats)
        return listed_chats, 200


@ns.route('/<string:chat_id>')
class Chat(Resource):
    method_decorators = [check_if_chat_exists, check_access]

    @ns.marshal_with(chat_model)
    def get(self, chat_id: str):
        user_id = get_jwt_identity()
        with db_connection() as conn:
            chat = r.table('chats').get(chat_id).merge(
                lambda chat: {
                    'messages': r.table('messages').filter({
                        'chat_id': chat_id,
                        'receiver_id': user_id,
                    }).coerce_to('array')
                }
            ).run(conn)
        return chat, 200


@ns.route('/string:chat_id/messages')
class ChatMessages(Resource):
    method_decorators = [check_if_chat_exists, check_access]

    post_parser: reqparse.RequestParser = ns.parser()
    post_parser.add_argument('type',
                             type=str,
                             choices=('text', 'image', 'audio'),
                             location='json',
                             required=True,
                             nullable=False)
    post_parser.add_argument('value',
                             location='json',
                             required=True,
                             nullable=False)

    @ns.expect(ns.model(
        name='Message',
        model={
            'type': fields.String(
                required=True,
                description='Type of message to send: \'text\', \'image\' or \'audio\'',
                example='text'),
            'value': fields.Raw(
                required=True,
                description='Content of the message to send',
                example='Example Message'
            )
        }
    ))
    def post(self, chat_id: str):
        user_id = get_jwt_identity()
        with db_connection() as conn:
            r.table('messages').insert({
                'chat_id': chat_id,
                'sender_id': user_id,
                'created_at': pytz.timezone('Europe/Helsinki').localize(datetime.now())
            }).run(conn)
        # todo: create message for every receiver and send it to receivers
