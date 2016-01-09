# -*- coding: utf-8 -*-
import json
from unittest.mock import patch, Mock

import pytest
import requests
from assertpy import assert_that
from requests.models import Response

from sarah.bot.gitter import GitterClient, Gitter, ConnectAttemptionCounter
from sarah.value_object import ObjectMapper

room_info = [{'unreadItems': 0,
              'topic': '',
              'noindex': False,
              'uri': 'spam/ham/egg',
              'roomMember': True,
              'mentions': 0,
              'userCount': 2,
              'lurk': False,
              'lastAccessTime': '2015-12-31T07:07:03.941Z',
              'tags': [],
              'githubType': 'REPO_CHANNEL',
              'oneToOne': False,
              'name': 'spam/ham/egg',
              'id': 'AAAAAc216b6c7089XXXXX72',
              'url': '/spam/ham/egg',
              'security': 'PRIVATE'}]


class TestGitterClient(object):
    @pytest.fixture(scope='function')
    def client(self, request):
        return GitterClient("dummy_token")

    def test_init_with_default_url(self):
        client = GitterClient("dummy_token")
        assert_that(client).has_token("dummy_token")
        assert_that(client.base_url).is_not_empty()

    def test_init_with_url(self):
        client = GitterClient("dummy_token", "http://sample.com/v1")
        assert_that(client).has_base_url("http://sample.com/v1/")

    def test_generate_endpoint(self, client):
        assert_that(client.generate_endpoint("rooms")).ends_with("/rooms")
        assert_that(client.generate_endpoint("rooms", "room_id1")) \
            .ends_with("/rooms/room_id1")
        assert_that(client.generate_endpoint("rooms", "room_id1", "message")) \
            .ends_with("/rooms/room_id1/message")

    def test_get_current_user(self, client):
        mapper = ObjectMapper(GitterClient.User)
        userInfo = {'id': "userIdSpamHam",
                    'username': "oklahomer",
                    'displayName': "homer",
                    'url': "/oklahomer",
                    'avatarUrlSmall': '/path/to/small/file.png',
                    'avatarUrlMedium': '/path/to/medium/file.png'}
        with patch.object(client,
                          "request",
                          return_value=[mapper.map(userInfo)]):
            ret = client.get_current_user()
            assert_that(ret).is_equal_to(mapper.map(userInfo))
            method, endpoint = client.request.call_args[0]
            assert_that(method).is_equal_to("GET")
            assert_that(endpoint).ends_with("/user")

    def test_get_rooms(self, client):
        mapper = ObjectMapper(GitterClient.Room)
        rooms = [mapper.map(d) for d in room_info]
        with patch.object(client,
                          "request",
                          return_value=rooms):
            ret = client.get_rooms()
            assert_that(ret).is_equal_to(rooms)
            method, endpoint = client.request.call_args[0]
            assert_that(method).is_equal_to("GET")
            assert_that(endpoint).ends_with("/rooms")

    def test_post_message(self, client):
        sending_text = "my message"
        room_id = "room_d_123"
        response_object = {
            'id': "5330521e20d939a3be000018",
            "text": "Happy Hacking!",
            "html": "Happy Hacking!",
            "sent": "2014-03-24T15:41:18.991Z",
            "editedAt": None,
            "fromUser": {
                "id": "5315ef029517002db7dde53b",
                "username": "malditogeek",
                "displayName": "Mauro Pompilio",
                "url": "/malditogeek",
                "avatarUrlSmall": "https://localhost/u/14751?",
                "avatarUrlMedium": "https://localhost/u/14751?",
                "v": 2
            },
            "unread": False,
            "readBy": 0,
            "urls": [],
            "mentions": [],
            "issues": [],
            "meta": {},
            "v": 1
        }
        mapper = ObjectMapper(GitterClient.Message)
        with patch.object(client,
                          "request",
                          return_value=mapper.map(response_object)):
            ret = client.post_message(room_id, sending_text)
            assert_that(ret).is_equal_to(mapper.map(response_object))
            method, endpoint = client.request.call_args[0]
            assert_that(method).is_equal_to("POST")
            assert_that(endpoint).ends_with("/chatMessages")

    def test_request(self, client):
        response = Mock(spec=Response)
        with patch.object(requests,
                          "request",
                          return_value=response):
            mapper = ObjectMapper(GitterClient.Room)
            with patch.object(response.content,
                              "decode",
                              return_value=json.dumps(room_info)):
                ret = client.request("GET",
                                     "http://localhost/rooms",
                                     ObjectMapper(GitterClient.Room),
                                     {'param': "spam"},
                                     {'body': "ham"})
                method, endpoint = requests.request.call_args[0]
                kwargs = requests.request.call_args[1]
                assert_that(ret).is_equal_to([mapper.map(obj)
                                              for obj in room_info])
                assert_that(method).is_equal_to("GET")
                assert_that(endpoint).is_equal_to("http://localhost/rooms")
                assert_that(kwargs['params']).is_equal_to({'param': "spam"})
                assert_that(kwargs['json']).is_equal_to({'body': "ham"})
                assert_that(kwargs['headers']['Authorization']).is_not_empty()
                assert_that(kwargs['headers']['Accept']).is_not_empty()
                assert_that(kwargs['headers']['Content-Type']).is_not_empty()


class TestConnectAttemptionCounter(object):
    def test_valid(self):
        counter = ConnectAttemptionCounter()
        assert_that(counter.count).is_zero()
        assert_that(counter.increment())
        assert_that(counter.count).is_equal_to(1)
        assert_that(counter.increment())
        assert_that(counter.count).is_equal_to(2)
        assert_that(counter.can_retry()).is_true()

    def test_valid_with_limit(self):
        counter = ConnectAttemptionCounter(limit=2)
        assert_that(counter.can_retry()).is_true()
        assert_that(counter.increment())
        assert_that(counter.can_retry()).is_true()
        assert_that(counter.increment())
        assert_that(counter.can_retry()).is_false()
        assert_that(counter.reset())
        assert_that(counter.can_retry()).is_true()


class TestGitter(object):
    @pytest.fixture(scope='function')
    def gitter(self, request):
        return Gitter("dummy_token")

    def test_init(self):
        gitter = Gitter("dummy_token")

        assert_that(gitter) \
            .has_user_id(None) \
            .has_token("dummy_token") \
            .has_stream_base_url("https://stream.gitter.im/v1/")
        assert_that(gitter.client).is_instance_of(GitterClient)

    def test_generate_endpoint(self, gitter):
        endpoint = gitter.generate_endpoint("dummy")
        assert_that(endpoint).starts_with("http")
        assert_that(endpoint).ends_with("/rooms/dummy/chatMessages")
