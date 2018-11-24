from dataclasses import dataclass, field

import rethinkdb as r
from typing import List


@dataclass
class User(object):
    username: str
    password: str
    name: str = None
    avatar: str = None
    phone_number: str = None
    id: str = None
    default_filter_ids: List[str] = field(default_factory=list)
    added_filter_ids: List[str] = field(default_factory=list)


@dataclass
class Chat(object):
    name: str
    user_ids: List[str] = field(default_factory=list)
    default_filter_ids: List[str] = field(default_factory=list)
    id: str = None

@dataclass
class Filter(object):
    name: str
    external_url: str
    input_type: str = 'text'
    output_type: str = 'text'
    is_pipeline: bool = False
    filter_ids: List[str] = field(default_factory=list)
    description: str = None
    avatar = None


