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
        'sender_id': fields.String,
        'created_at': fields.String,
        'values': fields.List(fields.Nested(value_model))
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
                    }).order_by(r.asc('created_at')).merge(
                        lambda message: {
                            'values': r.table('values').filter(
                                lambda value: message['value_ids'].contains(
                                    value['id'])
                            ).coerce_to('array')
                        }
                    ).pluck(
                        'message_id',
                        'sender_id',
                        'created_at',
                        'values'
                    ).coerce_to('array')
                }
            ).run(conn)
        return chat, 200


@ns.route('/<string:chat_id>/messages')
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
            # Group filters
            chat_response = r.table('chats').get(chat_id).run(conn)
            chat = models.Chat(**chat_response)
            args = self.post_parser.parse_args()
            value = args['value']
            type = args['type']
            filters: List[str] = r.table('filters').filter(
                lambda filter:
                    r.table('chats').get(chat_id)[
                        'default_filter_ids'].contains(filter['id'])
            ).pluck(
                'external_url',
                'input_type',
                'output_type'
            ).run(conn)
            current_value = value
            current_type = type

            for f in filters:
                f = models.Filter(f)
                if not (current_type == f.input_type):
                    break

                if f.input_type == 'text':
                    res = requests.post(
                        f.external_url,
                        json={
                            'value': current_value
                        })
                    try:
                        content = res.json()['value']
                    except:
                        raise NotImplementedError
                    current_value = content
                elif f.input_type == 'image':
                    res = requests.post(
                        f.external_url,
                        data=current_value
                    )
                    current_value = res.content
                current_type = f.output_type

            res = r.table('values').insert({
                'content': current_value,
                'type': current_type
            }).run(conn)
            if 'generated_keys' not in res or len(res['generated_keys']) != 1:
                raise NotImplementedError
            value_id = res['generated_keys'][0]
            # send message b
            for current_user_id in chat.user_ids:
                current_user_response = r.table(
                    'users').get(current_user_id).run(conn)
                current_user = models.User(**current_user_response)
                message_generated_res = r.table('messages').insert({
                    'message_id': r.uuid(),
                    'chat_id': chat_id,
                    'sender_id': user_id,
                    'receiver_id': current_user.id,
                    'created_at': r.now(),
                    'value_ids': [value_id],
                    'filter_ids': list()
                }).run(conn)
                if 'generated_keys' not in message_generated_res or len(message_generated_res['generated_keys']) != 1:
                    raise NotImplementedError
                message_generated_id = message_generated_res['generated_keys'][0]

                for f_id in current_user.default_filter_ids:
                    current_filter_external_url = r.table(
                        'filters').get(f_id).run(conn)
                    current_filter_response = None  # do filter request
                    r.table('messages').get(message_generated_id).update(
                        lambda message: {
                            'value_ids': message['value_ids'].append(current_filter_response),
                            'filter_ids': message['filter_ids'].append(f_id)
                        }
                    ).run(conn)
        return message_generated_id
