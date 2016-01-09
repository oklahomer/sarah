# -*- coding: utf-8 -*-
"""Provide Gitter interaction."""
import collections
import json
import logging
from contextlib import closing
from threading import Thread
from typing import Dict, Optional, Callable, Any, Iterable, Union, Sequence, \
    List

import requests

from sarah import ValueObject
from sarah.bot import Base
from sarah.bot.values import ScheduledCommand, PluginConfig
from sarah.value_object import ObjectMapper


class GitterClient(object):
    """A client module that provides access to Gitter web API."""

    class Room(ValueObject):
        def __init__(self,
                     id: str,
                     name: str,
                     topic: str,
                     oneToOne: bool,
                     unreadItems: int,
                     mentions: int,
                     lurk: bool,
                     url: str,
                     githubType: str) -> None:
            pass

        @property
        def id(self) -> str:
            return self['id']

        @property
        def name(self) -> str:
            return self['name']

        @property
        def topic(self) -> str:
            return self['topic']

        @property
        def is_one_to_one(self) -> bool:
            return self['oneToOneA']

        @property
        def unread_items(self) -> int:
            return self['unreadItems']

        @property
        def mentions(self) -> int:
            return self['mentions']

        @property
        def is_lurk(self) -> bool:
            return self['lurk']

        @property
        def url(self) -> str:
            return self['url']

        @property
        def github_type(self) -> str:
            return self['githubType']

    class Message(ValueObject):
        """Represent Message resource returned by gitter.

        See https://developer.gitter.im/docs/messages-resource
        """

        def __init__(self,
                     id: str,
                     text: str,
                     html: str,
                     sent: str,
                     fromUser: Dict[str, Any],
                     unread: bool,
                     readBy: int,
                     urls: Sequence[Dict[str, Any]],
                     mentions: Sequence[Dict[str, Any]],
                     issues: Sequence[Dict[str, Any]],
                     meta: Dict[str, Any]) -> None:
            self['fromUser'] = ObjectMapper(GitterClient.User).map(fromUser)
            # TODO convert "sent" and "editedAt" to datetime related object
            pass

        @property
        def id(self) -> str:
            return self['id']

        @property
        def text(self) -> str:
            return self['text']

        @property
        def html(self) -> str:
            return self['html']

        @property
        def sent(self) -> str:
            return self['sent']

        @property
        def edited_at(self) -> str:
            return self['editedAt']

        @property
        def from_user(self) -> 'GitterClient.User':
            return self['fromUser']

        @property
        def is_unread(self) -> bool:
            return self['unread']

        @property
        def read_by(self) -> int:
            return self['readBy']

        @property
        def urls(self) -> List[Dict[str, Any]]:
            return self['urls']

        @property
        def mentions(self) -> List[Dict[str, Any]]:
            return self['mentions']

        @property
        def issues(self) -> List[Dict[str, Any]]:
            return self['issues']

        @property
        def meta(self) -> List[Dict[str, Any]]:
            return self['meta']

    class User(ValueObject):
        def __init__(self,
                     id: str,
                     username: str,
                     displayName: str,
                     url: str,
                     avatarUrlSmall: str,
                     avatarUrlMedium: str) -> None:
            pass

        @property
        def id(self) -> str:
            return self['id']

        @property
        def user_name(self) -> str:
            return self['username']

        @property
        def display_name(self) -> str:
            return self['displayName']

        @property
        def url(self) -> str:
            return self['url']

        @property
        def avatar_url_small(self) -> str:
            return self['avatarUrlSmall']

        @property
        def avatar_url_medium(self) -> str:
            return self['avatarUrlMedium']

    def __init__(self,
                 token: str,
                 base_url: str = "https://api.gitter.im/v1/") -> None:
        self.token = token
        self.base_url = base_url if base_url.endswith("/") else base_url + "/"

    def generate_endpoint(self,
                          resource: str,
                          resource_id: str = None,
                          sub_resource: str = None) -> str:
        # https://developer.gitter.im/docs/rest-api#url-breakdown
        path_fragments = []
        for val in [resource, resource_id, sub_resource]:
            if val:
                path_fragments.append(val)
            else:
                break

        return self.base_url + "/".join(path_fragments)

    def get_rooms(self) -> List[Room]:
        endpoint = self.generate_endpoint("rooms")
        return self.request("GET",
                            endpoint,
                            mapper=ObjectMapper(GitterClient.Room))

    def get_current_user(self) -> User:
        endpoint = self.generate_endpoint("user")
        return self.request("GET",
                            endpoint,
                            mapper=ObjectMapper(GitterClient.User))[0]

    def post_message(self, room_id: str, text: str) -> Message:
        endpoint = self.generate_endpoint("rooms", room_id, "chatMessages")
        return self.request("POST",
                            endpoint,
                            post_params={'text': text},
                            mapper=ObjectMapper(GitterClient.Message))

    def request(self,
                method: str,
                endpoint: str,
                mapper: ObjectMapper,
                params: Dict = None,
                post_params: Dict = None) \
            -> Union[ValueObject, List[ValueObject]]:

        headers = {'Accept': "application/json",
                   'Authorization': "Bearer " + self.token,
                   'Content-Type': "application/json"}

        try:
            response = requests.request(method,
                                        endpoint,
                                        headers=headers,
                                        params=params,
                                        json=post_params)
            logging.debug(response)
            # object_hook is handy when mapping sinple object,
            # but requires extra work to map nested object
            # return json.loads(response.content.decode(),
            #                   object_hook=mapper.map)
            obj = json.loads(response.content.decode())
            if isinstance(obj, collections.Mapping):
                return mapper.map(obj)
            elif isinstance(obj, collections.Iterable):
                return [mapper.map(elm) for elm in obj]
            else:
                raise Exception("Unexpected response format. %s", obj)

        except Exception as e:
            logging.error("ERROR : %s", e)
            raise e


class ConnectAttemptionCounter(object):
    def __init__(self, limit: int = 10):
        self.__count = 0
        self.__limit = limit

    def increment(self):
        self.__count += 1

    def reset(self):
        self.__count = 0

    def can_retry(self):
        return self.__limit > self.__count

    @property
    def count(self):
        return self.__count


class Gitter(Base):
    """Provide bot for Gitter."""

    def __init__(self,
                 token: str = '',
                 plugins: Iterable[PluginConfig] = None,
                 rest_base_url: str = None,
                 stream_base_url: str = "https://stream.gitter.im/v1/",
                 max_workers: int = None) -> None:
        super().__init__(plugins=plugins, max_workers=max_workers)

        self.user_id = None
        self.token = token
        self.client = self.setup_client(token=token, base_url=rest_base_url)
        self.stream_base_url = stream_base_url \
            if stream_base_url.endswith("/") else stream_base_url + "/"

    def setup_client(self, token: str, base_url: str = None) -> GitterClient:
        return GitterClient(token, base_url) \
            if base_url else GitterClient(token)

    def generate_schedule_job(self, command: ScheduledCommand) \
            -> Optional[Callable[..., None]]:
        pass

    def generate_endpoint(self, room_id: str):
        return "%srooms/%s/chatMessages" % (self.stream_base_url, room_id)

    def connect(self) -> None:
        rooms = self.client.get_rooms()

        user = self.client.get_current_user()
        self.user_id = user.id

        threads = [Thread(target=self.connect_room,
                          kwargs={'room': room},
                          daemon=True)
                   for room in rooms]

        for thread in threads:
            thread.run()

    def connect_room(self, room: GitterClient.Room) -> None:
        headers = {'Accept': "application/json",
                   'Authorization': "Bearer " + self.token}
        endpoint = self.generate_endpoint(room.id)
        message_mapper = ObjectMapper(GitterClient.Message)
        with closing(
                requests.get(endpoint, headers=headers, stream=True)) as r:
            for line in r.iter_lines():
                line = line.strip()
                if not line:
                    continue

                message = message_mapper.map(json.loads(line.decode('utf-8')))
                self.handle_message(room, message)

    def handle_message(self,
                       room: GitterClient.Room,
                       message: GitterClient.Message) -> None:
        logging.debug(message)
        try:
            if message.from_user.id == self.user_id:
                return None

            ret = self.respond(message.from_user.id, message.text)
            if ret:
                self.client.post_message(room.id, ret)
        except Exception as e:
            logging.error(e)

    def disconnect(self) -> None:
        pass
