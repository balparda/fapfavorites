#!/usr/bin/python3 -bb
#
# Copyright 2023 Daniel Balparda (balparda@gmail.com)
#
"""views.py unittest."""

import copy
import functools
import os
# import pdb
from typing import Any
import unittest
from unittest import mock

# import duplicates
# import fapdata

# load the Django modules in a very special manner:
os.environ['DJANGO_SETTINGS_MODULE'] = 'fapper.settings'  # cspell:disable-line
# not only we need the os.environ to load django stuff, we also have to patch the cache
# decorator before we load the module, as decorators are applied at module load, and the
# cache decorator is a very tricky one to fool at runtime
from django.views.decorators import cache  # noqa: E402


def _mock_decorator(*args, **kwargs):
  def _decorator(f):
      @functools.wraps(f)
      def _decorated_function(*args, **kwargs):
          return f(*args, **kwargs)
      return _decorated_function
  return _decorator


cache.cache_page = _mock_decorator  # monkey-patch the cache
from viewer import views  # noqa: E402

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


class TestDjangoViews(unittest.TestCase):
  """Tests for views.py."""

  def test_SHA256HexDigest(self) -> None:
    """Test."""
    digest = views.SHA256HexDigest()
    self.assertEqual(digest.to_python('fOO'), 'foo')
    self.assertEqual(digest.to_url('Bar'), 'bar')

  @mock.patch('fapdata.GetDatabaseTimestamp')
  @mock.patch('fapdata.FapDatabase')
  def test_DBFactory(self, mock_db: mock.MagicMock, mock_tm: mock.MagicMock) -> None:
    """Test."""
    mock_tm.return_value = 100
    db = mock.MagicMock()
    mock_db.return_value = db
    self.assertEqual(views._DBFactory(), db)
    mock_tm.assert_called_once_with(views.conf.settings.IMAGEFAP_FAVORITES_DB_PATH)
    mock_db.assert_called_once_with(
        views.conf.settings.IMAGEFAP_FAVORITES_DB_PATH, create_if_needed=False)
    db.Load.assert_called_once_with()

  @mock.patch('viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('os.path.getsize')
  def test_ServeIndex(
      self, mock_getsize: mock.MagicMock, mock_render: mock.MagicMock,
      mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_db.return_value = _TestDBFactory()
    mock_getsize.return_value = 100000
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {}
    request.GET = {}
    views.ServeIndex(request)
    mock_render.assert_called_once_with(request, 'viewer/index.html', _INDEX_CONTEXT)

  @mock.patch('viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapdata.FapDatabase.DeleteUserAndAlbums')
  @mock.patch('fapdata.FapDatabase.Save')
  def test_ServeUsers(
      self, mock_save: mock.MagicMock, mock_delete: mock.MagicMock,
      mock_render: mock.MagicMock, mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_db.return_value = _TestDBFactory()
    mock_delete.return_value = (66, 22)
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {'delete_input': '3'}
    request.GET = {}
    views.ServeUsers(request)
    mock_delete.assert_called_once_with(3)
    mock_save.assert_called_once_with()
    mock_render.assert_called_once_with(request, 'viewer/users.html', _USERS_CONTEXT)

  @mock.patch('viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapdata.FapDatabase.DeleteAlbum')
  @mock.patch('fapdata.FapDatabase.Save')
  def test_ServeFavorites(
      self, mock_save: mock.MagicMock, mock_delete: mock.MagicMock,
      mock_render: mock.MagicMock, mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_db.return_value = _TestDBFactory()
    mock_delete.return_value = (66, 22)
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {'delete_input': '11'}
    request.GET = {}
    views.ServeFavorites(request, 1)
    mock_delete.assert_called_once_with(1, 11)
    mock_save.assert_called_once_with()
    mock_render.assert_called_once_with(request, 'viewer/favorites.html', _FAVORITES_CONTEXT)

  @mock.patch('viewer.views._DBFactory')
  def test_ServeFavorites_User_404(self, mock_db: mock.MagicMock) -> None:
    """Test."""
    mock_db.return_value = _TestDBFactory()
    with self.assertRaises(views.http.Http404):
      views.ServeFavorites(mock.Mock(views.http.HttpRequest), 5)

  @mock.patch('viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapdata.FapDatabase.Save')
  def test_ServeFavorite_All_On_And_Tagging(
      self, mock_save: mock.MagicMock, mock_render: mock.MagicMock,
      mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    db = _TestDBFactory()
    mock_db.return_value = db
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {
        'tag_select': '24',
        'selected_blobs': ('0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19,'
                           'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'),
    }
    request.GET = {
        'dup': '1',  # by default, show portrait+landscape, lock is off
    }
    views.ServeFavorite(request, 1, 10)
    new_tags = {sha: db.blobs[sha]['tags'] for sha in _FAVORITE_CONTEXT_ALL_ON['blobs_data'].keys()}
    self.assertDictEqual(new_tags, _FAVORITE_NEW_TAGS)
    mock_save.assert_called_once_with()
    mock_render.assert_called_once_with(request, 'viewer/favorite.html', _FAVORITE_CONTEXT_ALL_ON)

  @mock.patch('viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapdata.FapDatabase.Save')
  def test_ServeFavorite_All_Off(
      self, mock_save: mock.MagicMock, mock_render: mock.MagicMock,
      mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_db.return_value = _TestDBFactory()
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {}
    request.GET = {
        'portrait': '0',  # by default, no duplicates
        'landscape': '0',
        'lock': '1',
    }
    views.ServeFavorite(request, 1, 10)
    mock_save.assert_not_called()
    mock_render.assert_called_once_with(request, 'viewer/favorite.html', _FAVORITE_CONTEXT_ALL_OFF)

  @mock.patch('viewer.views._DBFactory')
  def test_ServeFavorite_User_404(self, mock_db: mock.MagicMock) -> None:
    """Test."""
    mock_db.return_value = _TestDBFactory()
    with self.assertRaises(views.http.Http404):
      views.ServeFavorite(mock.Mock(views.http.HttpRequest), 5, 10)

  @mock.patch('viewer.views._DBFactory')
  def test_ServeFavorite_Folder_404(self, mock_db: mock.MagicMock) -> None:
    """Test."""
    mock_db.return_value = _TestDBFactory()
    with self.assertRaises(views.http.Http404):
      views.ServeFavorite(mock.Mock(views.http.HttpRequest), 1, 50)

  @mock.patch('viewer.views._DBFactory')
  @mock.patch('django.http.HttpResponse')
  @mock.patch('fapdata.FapDatabase.HasBlob')
  @mock.patch('fapdata.FapDatabase.GetBlob')
  def test_ServeBlob(
      self, mock_get_blob: mock.MagicMock, mock_has_blob: mock.MagicMock,
      mock_response: mock.MagicMock, mock_db: mock.MagicMock) -> None:
    """Test."""
    mock_db.return_value = _TestDBFactory()
    mock_has_blob.return_value = True
    mock_get_blob.return_value = b'image binary data'
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {}
    request.GET = {}
    views.ServeBlob(request, '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8')
    mock_has_blob.assert_called_once_with(
        '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8')
    mock_get_blob.assert_called_once_with(
        '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8')
    mock_response.assert_called_once_with(content=b'image binary data', content_type='image/gif')

  @mock.patch('viewer.views._DBFactory')
  def test_ServeBlob_Existence_404(self, mock_db: mock.MagicMock) -> None:
    """Test."""
    mock_db.return_value = _TestDBFactory()
    with self.assertRaises(views.http.Http404):
      views.ServeBlob(mock.Mock(views.http.HttpRequest), 'hash-does-not-exist')

  @mock.patch('viewer.views._DBFactory')
  @mock.patch('fapdata.FapDatabase.HasBlob')
  def test_ServeBlob_Blob_Not_On_Disk_404(
      self, mock_has_blob: mock.MagicMock, mock_db: mock.MagicMock) -> None:
    """Test."""
    mock_db.return_value = _TestDBFactory()
    mock_has_blob.return_value = False
    with self.assertRaises(views.http.Http404):
      views.ServeBlob(
          mock.Mock(views.http.HttpRequest),
          '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8')

  @mock.patch('viewer.views._DBFactory')
  @mock.patch('fapdata.FapDatabase.HasBlob')
  def test_ServeBlob_Invalid_Extension_404(
      self, mock_has_blob: mock.MagicMock, mock_db: mock.MagicMock) -> None:
    """Test."""
    db = _TestDBFactory()
    mock_db.return_value = db
    mock_has_blob.return_value = True
    db.blobs['5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8']['ext'] = 'invalid'
    with self.assertRaises(views.http.Http404):
      views.ServeBlob(
          mock.Mock(views.http.HttpRequest),
          '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8')

  @mock.patch('viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapdata.FapDatabase.Save')
  def test_ServeTag_Root_And_Create(
      self, mock_save: mock.MagicMock, mock_render: mock.MagicMock,
      mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    db = _TestDBFactory()
    mock_db.return_value = db
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {'named_child': 'new-tag-foo'}
    request.GET = {}
    views.ServeTag(request, 0)
    mock_save.assert_called_once_with()
    mock_render.assert_called_once_with(request, 'viewer/tag.html', _TAG_ROOT_CONTEXT)

  @mock.patch('viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapdata.FapDatabase.Save')
  def test_ServeTag_Leaf_And_Delete(
      self, mock_save: mock.MagicMock, mock_render: mock.MagicMock,
      mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    db = _TestDBFactory()
    mock_db.return_value = db
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {'delete_input': '33'}
    request.GET = {}
    views.ServeTag(request, 2)
    new_tags = {sha: db.blobs[sha]['tags'] for sha in db.blobs.keys()}
    self.assertDictEqual(new_tags, _TAG_NEW_TAGS)
    mock_save.assert_called_once_with()
    mock_render.assert_called_once_with(request, 'viewer/tag.html', _TAG_LEAF_CONTEXT)

  @mock.patch('viewer.views._DBFactory')
  def test_ServeTag_404(self, mock_db: mock.MagicMock) -> None:
    """Test."""
    mock_db.return_value = _TestDBFactory()
    with self.assertRaises(views.http.Http404):
      views.ServeTag(mock.Mock(views.http.HttpRequest), 666)

  @mock.patch('viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  def test_ServeDuplicates(self, mock_render: mock.MagicMock, mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_db.return_value = _TestDBFactory()
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {}
    request.GET = {}
    views.ServeDuplicates(request)
    mock_render.assert_called_once_with(request, 'viewer/duplicates.html', _DUPLICATES_CONTEXT)

  @mock.patch('viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  def test_ServeDuplicate_Blob(self, mock_render: mock.MagicMock, mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_db.return_value = _TestDBFactory()
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {}
    request.GET = {}
    views.ServeDuplicate(
        # this is a blob-only (hash collision) duplicate
        request, '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf')
    mock_render.assert_called_once_with(request, 'viewer/duplicate.html', _DUPLICATE_BLOB_CONTEXT)

  @mock.patch('viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapdata.FapDatabase.Save')
  def test_ServeDuplicate_Set(
      self, mock_save: mock.MagicMock, mock_render: mock.MagicMock,
      mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    db = _TestDBFactory()
    mock_db.return_value = db
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {
        '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19': 'keep',
        '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': 'false',
        'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': 'false',
    }
    request.GET = {}
    views.ServeDuplicate(
        request, 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e')
    mock_save.assert_called_once_with()
    mock_render.assert_called_once_with(request, 'viewer/duplicate.html', _DUPLICATE_SET_CONTEXT)

  @mock.patch('viewer.views._DBFactory')
  def test_ServeDuplicate_Blob_404(self, mock_db: mock.MagicMock) -> None:
    """Test."""
    mock_db.return_value = _TestDBFactory()
    with self.assertRaises(views.http.Http404):
      views.ServeDuplicate(mock.Mock(views.http.HttpRequest), 'not-a-valid-blob-hash')

  @mock.patch('viewer.views._DBFactory')
  def test_ServeDuplicate_Singleton_404(self, mock_db: mock.MagicMock) -> None:
    """Test."""
    mock_db.return_value = _TestDBFactory()
    with self.assertRaises(views.http.Http404):
      views.ServeDuplicate(
          mock.Mock(views.http.HttpRequest),
          # this hash has no duplicate set nor hash collision
          'dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180')

  @mock.patch('viewer.views._DBFactory')
  def test_ServeDuplicate_Update_404(self, mock_db: mock.MagicMock) -> None:
    """Test."""
    mock_db.return_value = _TestDBFactory()
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {
        # this is a blob-only (hash collision) duplicate, and should not support POST
        '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': 'keep',
    }
    request.GET = {}
    with self.assertRaises(views.http.Http404):
      views.ServeDuplicate(
          request, '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf')


@mock.patch('fapdata.os.path.isdir')
def _TestDBFactory(mock_isdir: mock.MagicMock) -> views.fapdata.FapDatabase:
  mock_isdir.return_value = True
  db = views.fapdata.FapDatabase('/foo/', create_if_needed=False)
  db._db = copy.deepcopy(_MOCK_DATABASE)  # needed: some of the test methods will change the dict!
  db.duplicates = views.duplicates.Duplicates(db._duplicates_registry, db._duplicates_key_index)
  return db


_MOCK_DATABASE: views.fapdata._DatabaseType = {
    'users': {
        1: 'Luke',  # has 2 albums
        2: 'Ben',   # has 1 album
        3: 'Yoda',  # has 0 albums
    },
    'favorites': {
        1: {  # Luke
            10: {
                'date_blobs': 1675300000,
                'date_straight': 0,
                'images': [100, 101, 102, 103, 104],
                'name': 'luke-folder-10',
                'pages': 9,
            },
            11: {
                'date_blobs': 1671000000,
                'date_straight': 1675300000,
                'images': [110, 111, 112],
                'name': 'luke-folder-11',
                'pages': 8,
            },
        },
        2: {  # Ben
            20: {
                'date_blobs': 1673000000,
                'date_straight': 0,
                'images': [200, 201, 202, 203],
                'name': 'ben-folder-20',
                'pages': 3,
            },
        },
    },
    'blobs': {
        '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19': {
            'animated': False,
            'ext': 'jpg',
            'height': 200,
            'loc': {
                (102, 'url-102', 'name-102.jpg', 1, 10),
            },
            'percept': 'cd4fc618316732e7',
            'sz': 54643,
            'sz_thumb': 54643,
            'tags': {3},
            'width': 198,  # image will be considered "square" aspect
        },
        '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': {
            'animated': False,
            'ext': 'png',
            'height': 173,
            'loc': {
                (110, 'url-110', 'name-110.png', 1, 11),
                (202, 'url-202', 'name-202.png', 2, 20),
            },
            'percept': 'd99ee32e586716c8',
            'sz': 45309,
            'sz_thumb': 45309,
            'tags': set(),  # untagged!
            'width': 130,
        },
        '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8': {
            'animated': True,
            'ext': 'gif',
            'height': 500,
            'tags': {246, 33},
            'loc': {
                (200, 'url-200', 'name-200.gif', 2, 20),
            },
            'percept': 'e699669966739866',
            'sz': 444973,
            'sz_thumb': 302143,
            'width': 100,
        },
        '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {
            'animated': False,
            'ext': 'jpg',
            'height': 200,
            'loc': {
                (101, 'url-101', 'name-101.jpg', 1, 10),
                (111, 'url-111', 'name-111.jpg', 1, 11),
                (201, 'url-201', 'name-201.jpg', 2, 20),
            },
            'percept': 'd99ee32e586716c8',
            'sz': 101,
            'sz_thumb': 0,
            'tags': {11, 33},
            'width': 160,
        },
        'dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180': {
            'animated': False,
            'ext': 'jpg',
            'height': 222,
            'loc': {
                (112, 'url-112', 'name-112.jpg', 1, 11),
            },
            'percept': '89991f6f62a63479',
            'sz': 89216,
            'sz_thumb': 11890,
            'tags': {246},
            'width': 300,
        },
        'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': {
            'animated': False,
            'ext': 'jpg',
            'height': 246,
            'loc': {
                (100, 'url-100', 'name-100.jpg', 1, 10),
                (104, 'url-104', 'name-104.jpg', 1, 10),  # dup in same album as above!
                (203, 'url-203', 'name-203.jpg', 2, 20),
            },
            'percept': 'cc8fc37638703ee1',
            'sz': 56583,
            'sz_thumb': 56583,
            'tags': {1, 2},
            'width': 200,
        },
        'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e': {
            'animated': True,
            'ext': 'gif',
            'height': 100,
            'tags': {1, 24, 33},
            'loc': {
                (103, 'url-103', 'name-103.gif', 1, 10),
            },
            'percept': 'e699669966739866',
            'sz': 444973,
            'sz_thumb': 302143,
            'width': 500,
        },
    },
    'image_ids_index': {
        100: 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e',
        101: '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
        102: '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19',
        103: 'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e',
        104: 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e',
        110: '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
        111: '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
        112: 'dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180',
        200: '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8',
        201: '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
        202: '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
        203: 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e',
    },
    'duplicates_registry': {
        ('0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19',
         '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
         'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'): {
            '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19': 'new',
            '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': 'keep',
            'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': 'skip',
        },
        ('5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8',
         'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e'): {
            '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8': 'false',
            'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e': 'false',
        },
    },
    'duplicates_key_index': {
        '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19': (
            '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19',
            '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
            'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'),
        '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': (
            '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19',
            '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
            'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'),
        'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': (
            '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19',
            '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
            'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'),
        '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8': (
            '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8',
            'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e'),
        'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e': (
            '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8',
            'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e'),
    },
    'tags': {
        0: {  # unused tag!
            'name': 'plain',
            'tags': {},
        },
        1: {
            'name': 'one',
            'tags': {
                11: {
                    'name': 'one-one',
                    'tags': {},
                },
            },
        },
        2: {
            'name': 'two',
            'tags': {
                22: {  # unused tag!
                    'name': 'two-two',
                    'tags': {},
                },
                24: {
                    'name': 'two-four',
                    'tags': {
                        246: {
                            'name': 'deep',
                            'tags': {},
                        },
                    },
                },
            },
        },
        3: {
            'name': 'three',
            'tags': {
                33: {
                    'name': 'three-three',
                    'tags': {},
                },
            },
        },
    },
}

_INDEX_CONTEXT: dict[str, Any] = {
    'users': 3,
    'tags': 9,
    'duplicates': 2,
    'dup_action': 1,
    'n_images': 7,
    'database_stats': [
        ('Database is located in \'/foo/imagefap.database\', and is 97.66kb '
         '(8.80438% of total images size)'),
        ('1.08Mb total (unique) images size (101b min, 434.54kb max, '
         '158.45kb mean with 190.33kb standard deviation, 2 are animated)'),
        ('Pixel size (width, height): 22.49k pixels min (130, 173), '
         '66.60k pixels max (300, 222), 44.27k mean with 14.35k standard deviation'),
        ('754.60kb total thumbnail size (0b min, 295.06kb max, 107.80kb mean with '
         '129.59kb standard deviation), 68.0% of total images size'),
        '',
        '3 users',
        '3 favorite galleries (oldest: 2023/Jan/06-10:13:20-UTC / newer: 2023/Feb/02-01:06:40-UTC)',
        '7 unique images (12 total, 5 exact duplicates)',
        '5 perceptual duplicates in 2 groups',
    ],
}

_USERS_CONTEXT: dict[str, Any] = {
    'users': {
        1: {
            'name': 'Luke',
            'n_img': 8,
            'n_animated': '1 (12.5%)',
            'files_sz': '729.99kb',
            'thumbs_sz': '514.80kb',
            'min_sz': '101b',
            'max_sz': '434.54kb',
            'mean_sz': '91.25kb',
            'dev_sz': '141.78kb',
        },
        2: {
            'name': 'Ben',
            'n_img': 4,
            'n_animated': '1 (25.0%)',
            'files_sz': '534.15kb',
            'thumbs_sz': '394.57kb',
            'min_sz': '101b',
            'max_sz': '434.54kb',
            'mean_sz': '133.54kb',
            'dev_sz': '202.08kb',
        },
        3: {
            'name': 'Yoda',
            'n_img': 0,
            'n_animated': '0 (0.0%)',
            'files_sz': '0b',
            'thumbs_sz': '0b',
            'min_sz': '-',
            'max_sz': '-',
            'mean_sz': '-',
            'dev_sz': '-',
        },
    },
    'user_count': 3,
    'total_img': 12,
    'total_animated': '2 (16.7%)',
    'total_sz': '1.23Mb',
    'total_thumbs': '909.36kb',
    'total_file_storage': '2.12Mb',
    'warning_message': ('User 3/\'Yoda\' deleted, and with them 66 blobs (images) deleted, '
                        'together with their thumbnails, plus 22 duplicates groups abandoned'),
    'error_message': None,
}

_FAVORITES_CONTEXT: dict[str, Any] = {
    'user_id': 1,
    'user_name': 'Luke',
    'favorites': {
        10: {
            'name': 'luke-folder-10',
            'pages': 9,
            'date': '2023/Feb/02-01:06:40-UTC',
            'count': 5,
            'files_sz': '598.52kb',
            'min_sz': '101b',
            'max_sz': '434.54kb',
            'mean_sz': '119.70kb',
            'dev_sz': '177.58kb',
            'thumbs_sz': '458.94kb',
            'n_animated': '1 (20.0%)',
        },
        11: {
            'name': 'luke-folder-11',
            'pages': 8,
            'date': '2022/Dec/14-06:40:00-UTC',
            'count': 3,
            'files_sz': '131.47kb',
            'min_sz': '101b',
            'max_sz': '87.12kb',
            'mean_sz': '43.82kb',
            'dev_sz': '43.51kb',
            'thumbs_sz': '55.86kb',
            'n_animated': '0 (0.0%)',
        },
    },
    'album_count': 2,
    'img_count': 8,
    'page_count': 17,
    'total_sz': '729.99kb',
    'total_thumbs_sz': '514.80kb',
    'total_file_storage': '1.22Mb',
    'total_animated': '1 (12.5%)',
    'warning_message': ('Favorites album 11/\'luke-folder-11\' deleted, and with it 66 '
                        'blobs (images) deleted, together with their thumbnails, '
                        'plus 22 duplicates groups abandoned'),
    'error_message': None,
}

_FAVORITE_CONTEXT_ALL_ON: dict[str, Any] = {
    'user_id': 1,
    'user_name': 'Luke',
    'folder_id': 10,
    'name': 'luke-folder-10',
    'show_duplicates': True,
    'dup_url': 'dup=1',
    'show_portraits': True,
    'portrait_url': 'portrait=1',
    'show_landscapes': True,
    'landscape_url': 'landscape=1',
    'locked_for_tagging': False,
    'tagging_url': 'lock=0',
    'pages': 9,
    'date': '2023/Feb/02-01:06:40-UTC',
    'count': 5,
    'stacked_blobs': [
        [
            (100, 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'),
            (101, '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf'),
            (102, '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19'),
            (103, 'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e'),
        ], [
            (104, 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'),
            (0, ''),
            (0, ''),
            (0, ''),
        ],
    ],
    'blobs_data': {
        'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': {
            'name': 'name-104.jpg',
            'sz': '55.26kb',
            'dimensions': '200x246 (WxH)',
            'tags': 'one, two, two/two-four',
            'thumb': 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e.jpg',
            'has_duplicate': True,
            'album_duplicate': True,
            'has_percept': True,
            'imagefap': 'https://www.imagefap.com/photo/104/',
        },
        '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {
            'name': 'name-101.jpg',
            'sz': '101b',
            'dimensions': '160x200 (WxH)',
            'tags': 'one/one-one, three/three-three',
            'thumb': '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf.jpg',
            'has_duplicate': True,
            'album_duplicate': False,
            'has_percept': False,
            'imagefap': 'https://www.imagefap.com/photo/101/',
        },
        '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19': {
            'name':
            'name-102.jpg',
            'sz': '53.36kb',
            'dimensions': '198x200 (WxH)',
            'tags': 'three, two/two-four',
            'thumb': '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19.jpg',
            'has_duplicate': False,
            'album_duplicate': False,
            'has_percept': True,
            'imagefap': 'https://www.imagefap.com/photo/102/',
        },
        'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e': {
            'name': 'name-103.gif',
            'sz': '434.54kb',
            'dimensions': '500x100 (WxH)',
            'tags': 'one, three/three-three, two/two-four',
            'thumb': 'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e.gif',
            'has_duplicate': False,
            'album_duplicate': False,
            'has_percept': False,
            'imagefap': 'https://www.imagefap.com/photo/103/',
        },
    },
    'tags': [
        (0, 'plain', 'plain'),
        (1, 'one', 'one'),
        (11, 'one-one', 'one/one-one'),
        (2, 'two', 'two'),
        (22, 'two-two', 'two/two-two'),
        (24, 'two-four', 'two/two-four'),
        (246, 'deep', 'two/two-four/deep'),
        (3, 'three', 'three'),
        (33, 'three-three', 'three/three-three'),
    ],
    'warning_message': '2 images tagged with \'two-four\'',
    'error_message': None,
}

_FAVORITE_NEW_TAGS: dict[str, set[int]] = {
    '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19': {3, 24},
    '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {11, 33},
    'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': {1, 2, 24},
    'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e': {1, 24, 33},
}

_FAVORITE_CONTEXT_ALL_OFF: dict[str, Any] = {
    'user_id': 1,
    'user_name': 'Luke',
    'folder_id': 10,
    'name': 'luke-folder-10',
    'show_duplicates': False,
    'dup_url': 'dup=0',
    'show_portraits': False,
    'portrait_url': 'portrait=0',
    'show_landscapes': False,
    'landscape_url': 'landscape=0',
    'locked_for_tagging': True,
    'tagging_url': 'lock=1',
    'pages': 9,
    'date': '2023/Feb/02-01:06:40-UTC',
    'count': 1,
    'stacked_blobs': [
        [
            (102, '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19'),
            (0, ''),
            (0, ''),
            (0, ''),
        ],
    ],
    'blobs_data': {
        '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19': {
            'name': 'name-102.jpg',
            'sz': '53.36kb',
            'dimensions': '198x200 (WxH)',
            'tags': 'three',
            'thumb': '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19.jpg',
            'has_duplicate': False,
            'album_duplicate': False,
            'has_percept': True,
            'imagefap': 'https://www.imagefap.com/photo/102/',
        },
    },
    'tags': _FAVORITE_CONTEXT_ALL_ON['tags'],
    'warning_message': None,
    'error_message': None,
}

_TAG_ROOT_CONTEXT: dict[str, Any] = {
    'tags': [
        (0, 'plain', 'plain', 0),
        (1, 'one', 'one', 0),
        (11, 'one-one', 'one/one-one', 1),
        (2, 'two', 'two', 0),
        (22, 'two-two', 'two/two-two', 1),
        (24, 'two-four', 'two/two-four', 1),
        (246, 'deep', 'two/two-four/deep', 2),
        (3, 'three', 'three', 0),
        (33, 'three-three', 'three/three-three', 1),
        (247, 'new-tag-foo', 'new-tag-foo', 0),
    ],
    'tag_id': 0,
    'page_depth': 0,
    'page_depth_up': 0,
    'tag_name': None,
    'warning_message': 'Tag 247/\'new-tag-foo\' created',
    'error_message': None,
}

_TAG_LEAF_CONTEXT: dict[str, Any] = {
    'tags': [
        (22, 'two-two', 'two/two-two', 1),
        (24, 'two-four', 'two/two-four', 1),
        (246, 'deep', 'two/two-four/deep', 2),
    ],
    'tag_id': 2,
    'page_depth': 1,
    'page_depth_up': 0,
    'tag_name': 'two',
    'warning_message': "Tag 33/'three-three' deleted and association removed from 3 blobs (images)",
    'error_message': None,
}

_TAG_NEW_TAGS: dict[str, set[int]] = {
    '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19': {3},
    '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': set(),
    '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8': {246},
    '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {11},
    'dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180': {246},
    'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': {1, 2},
    'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e': {1, 24},
}

_DUPLICATES_CONTEXT: dict[str, Any] = {
    'duplicates': {
        ('0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19',
         '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
         'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'): {
            'name': ('(0aaef1becbd966a2&hellip;, 321e59af9d70af77&hellip;, '  # cspell:disable-line
                     'e221b76f55946176&hellip;)'),                            # cspell:disable-line
            'size': 3,
            'action': True,
            'verdicts': 'N / K / S',
        },
        ('5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8',
         'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e'): {
            'name': '(5b1d83a7317f2bb1&hellip;, ed1441656a734052&hellip;)',  # cspell:disable-line
            'size': 2,
            'action': False,
            'verdicts': 'F / F',
        },
    },
    'dup_action': 1,
    'dup_count': 2,
    'img_count': 5,
    'new_count': '1 (20.0%)',
    'false_count': '2 (40.0%)',
    'keep_count': '1 (20.0%)',
    'skip_count': '1 (20.0%)',
}

_DUPLICATE_BLOB_CONTEXT: dict[str, Any] = {
    'digest': '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
    'dup_key': '(9b162a339a3a6f9a&hellip;)',  # cspell:disable-line
    'current_index': -1,
    'previous_key': None,
    'next_key': None,
    'duplicates': {
        '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {
            'action': '',
            'sz': '101b',
            'dimensions': '160x200 (WxH)',
            'tags': 'one/one-one, three/three-three',
            'thumb': '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf.jpg',
            'percept': 'd99ee32e586716c8',
            'loc': [
                {
                    'fap_id': 101,
                    'file_name': 'name-101.jpg',
                    'user_id': 1,
                    'user_name': 'Luke',
                    'folder_id': 10,
                    'folder_name': 'luke-folder-10',
                    'imagefap': 'https://www.imagefap.com/photo/101/',
                }, {
                    'fap_id': 111,
                    'file_name': 'name-111.jpg',
                    'user_id': 1,
                    'user_name': 'Luke',
                    'folder_id': 11,
                    'folder_name': 'luke-folder-11',
                    'imagefap': 'https://www.imagefap.com/photo/111/',
                }, {
                    'fap_id': 201,
                    'file_name': 'name-201.jpg',
                    'user_id': 2,
                    'user_name': 'Ben',
                    'folder_id': 20,
                    'folder_name': 'ben-folder-20',
                    'imagefap': 'https://www.imagefap.com/photo/201/',
                },
            ],
        },
    },
    'error_message': None,
}

_DUPLICATE_SET_CONTEXT: dict[str, Any] = {
    'digest': 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e',
    'dup_key': ('(0aaef1becbd966a2&hellip;, 321e59af9d70af77&hellip;, '  # cspell:disable-line
                'e221b76f55946176&hellip;)'),                            # cspell:disable-line
    'current_index': 0,
    'previous_key': None,
    'next_key': ('5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8',
                 'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e'),
    'duplicates': {
        '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19': {
            'action': 'keep',
            'sz': '53.36kb',
            'dimensions': '198x200 (WxH)',
            'tags': 'three',
            'thumb': '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19.jpg',
            'percept': 'cd4fc618316732e7',
            'loc': [
                {
                    'fap_id': 102,
                    'file_name': 'name-102.jpg',
                    'user_id': 1,
                    'user_name': 'Luke',
                    'folder_id': 10,
                    'folder_name': 'luke-folder-10',
                    'imagefap': 'https://www.imagefap.com/photo/102/',
                },
            ],
        },
        '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': {
            'action': 'false',
            'sz': '44.25kb',
            'dimensions': '130x173 (WxH)',
            'tags': '',
            'thumb': '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6.png',
            'percept': 'd99ee32e586716c8',
            'loc': [
                {
                    'fap_id': 110,
                    'file_name': 'name-110.png',
                    'user_id': 1,
                    'user_name': 'Luke',
                    'folder_id': 11,
                    'folder_name': 'luke-folder-11',
                    'imagefap': 'https://www.imagefap.com/photo/110/',
                }, {
                    'fap_id': 202,
                    'file_name': 'name-202.png',
                    'user_id': 2,
                    'user_name': 'Ben',
                    'folder_id': 20,
                    'folder_name': 'ben-folder-20',
                    'imagefap': 'https://www.imagefap.com/photo/202/',
                },
            ],
        },
        'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': {
            'action': 'false',
            'sz': '55.26kb',
            'dimensions': '200x246 (WxH)',
            'tags': 'one, two',
            'thumb': 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e.jpg',
            'percept': 'cc8fc37638703ee1',
            'loc': [
                {
                    'fap_id': 100,
                    'file_name': 'name-100.jpg',
                    'user_id': 1,
                    'user_name': 'Luke',
                    'folder_id': 10,
                    'folder_name': 'luke-folder-10',
                    'imagefap': 'https://www.imagefap.com/photo/100/',
                }, {
                    'fap_id': 104,
                    'file_name': 'name-104.jpg',
                    'user_id': 1,
                    'user_name': 'Luke',
                    'folder_id': 10,
                    'folder_name': 'luke-folder-10',
                    'imagefap': 'https://www.imagefap.com/photo/104/',
                }, {
                    'fap_id': 203,
                    'file_name': 'name-203.jpg',
                    'user_id': 2,
                    'user_name': 'Ben',
                    'folder_id': 20,
                    'folder_name': 'ben-folder-20',
                    'imagefap': 'https://www.imagefap.com/photo/203/',
                },
            ],
        },
    },
    'error_message': None,
}


SUITE = unittest.TestLoader().loadTestsFromTestCase(TestDjangoViews)


if __name__ == '__main__':
  unittest.main()
