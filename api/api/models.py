from dataclasses import dataclass, field

import rethinkdb as r
from typing import List


@dataclass
class User:
    username: str
    password: str
    name: str = None
    avatar: str = None
    phone_number: str = None
    id: str = None


@dataclass
class Chat:
    name: str
    user_ids: List[str] = field(default_factory=list)
    default_filter_ids: List[str] = field(default_factory=list)
    id: str = None
