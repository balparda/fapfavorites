#!/usr/bin/python3 -bb
#
# Copyright 2023 Daniel Balparda (balparda@gmail.com)
#
# pylint: disable=invalid-name,protected-access,wrong-import-position
"""views.py unittest."""

import copy
import functools
import os
# import pdb
from typing import Any
import unittest
from unittest import mock

import numpy as np

# load the Django modules in a very special manner:
os.environ['DJANGO_SETTINGS_MODULE'] = 'fapper.settings'  # cspell:disable-line
# not only we need the os.environ to load django stuff, we also have to patch the cache
# decorator before we load the module, as decorators are applied at module load, and the
# cache decorator is a very tricky one to fool at runtime
from django.views.decorators import cache  # noqa: E402


__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (2, 0)


def _mock_decorator(*unused_args, **unused_kwargs):
  def _decorator(f):
    @functools.wraps(f)
    def _decorated_function(*args, **kwargs):
      return f(*args, **kwargs)
    return _decorated_function
  return _decorator


cache.cache_page = _mock_decorator  # monkey-patch the cache
from fapfavorites.viewer import views  # noqa: E402
from fapfavorites import fapdata       # noqa: E402

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


class TestDjangoViews(unittest.TestCase):
  """Tests for views.py."""

  def test_SHA256HexDigest(self) -> None:
    """Test."""
    digest = views.SHA256HexDigest()
    self.assertEqual(digest.to_python('fOO'), 'foo')
    self.assertEqual(digest.to_url('Bar'), 'bar')

  @mock.patch('fapfavorites.fapdata.GetDatabaseTimestamp')
  @mock.patch('fapfavorites.fapdata.FapDatabase')
  def test_DBFactory(self, mock_db: mock.MagicMock, mock_tm: mock.MagicMock) -> None:
    """Test."""
    mock_tm.return_value = 100  # different from other test_DBFactory*() to not trigger cache!
    db = mock.MagicMock()
    mock_db.return_value = db
    self.assertEqual(views._DBFactory(), db)
    mock_tm.assert_called_once_with(views.conf.settings.IMAGEFAP_FAVORITES_DB_PATH)
    mock_db.assert_called_once_with(
        views.conf.settings.IMAGEFAP_FAVORITES_DB_PATH, create_if_needed=False)
    db.Load.assert_called_once_with()

  @mock.patch('fapfavorites.fapdata.GetDatabaseTimestamp')
  @mock.patch('fapfavorites.fapdata.FapDatabase')
  def test_DBFactory_Fail_Dir(self, mock_db: mock.MagicMock, mock_tm: mock.MagicMock) -> None:
    """Test."""
    mock_tm.return_value = 101  # different from other test_DBFactory*() to not trigger cache!
    db = mock.MagicMock()
    mock_db.return_value = db
    db.thumbs_dir_exists = False
    with self.assertRaisesRegex(fapdata.Error, r'blobs and/or thumbs directories'):
      views._DBFactory()

  @mock.patch('fapfavorites.fapdata.GetDatabaseTimestamp')
  @mock.patch('fapfavorites.fapdata.FapDatabase')
  def test_DBFactory_Fail_Load(self, mock_db: mock.MagicMock, mock_tm: mock.MagicMock) -> None:
    """Test."""
    mock_tm.return_value = 102  # different from other test_DBFactory*() to not trigger cache!
    db = mock.MagicMock()
    mock_db.return_value = db
    db.Load.return_value = False
    with self.assertRaisesRegex(fapdata.Error, r'Database does not exist'):
      views._DBFactory()

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('os.path.getsize')
  def test_ServeIndex(
      self, mock_getsize: mock.MagicMock, mock_render: mock.MagicMock,
      mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    mock_getsize.return_value = 100000
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {}
    request.GET = {}
    views.ServeIndex(request)
    mock_render.assert_called_once_with(request, 'viewer/index.html', mock.ANY)
    self.assertDictEqual(mock_render.call_args[0][2], _INDEX_CONTEXT)

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapfavorites.fapdata.FapDatabase.DeleteUserAndAlbums')
  @mock.patch('fapfavorites.fapdata.FapDatabase.Save')
  def test_ServeUsers(
      self, mock_save: mock.MagicMock, mock_delete: mock.MagicMock,
      mock_render: mock.MagicMock, mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    mock_delete.return_value = (66, 22)
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {'delete_input': '3'}
    request.GET = {}
    views.ServeUsers(request)
    mock_render.assert_called_once_with(request, 'viewer/users.html', mock.ANY)
    self.assertDictEqual(mock_render.call_args[0][2], _USERS_CONTEXT)
    mock_delete.assert_called_once_with(3)
    mock_save.assert_called_once_with()

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapfavorites.fapdata.FapDatabase.DeleteAlbum')
  @mock.patch('fapfavorites.fapdata.FapDatabase.Save')
  def test_ServeFavorites(
      self, mock_save: mock.MagicMock, mock_delete: mock.MagicMock,
      mock_render: mock.MagicMock, mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    mock_delete.return_value = (66, 22)
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {'delete_input': '11'}
    request.GET = {}
    views.ServeFavorites(request, 1)
    mock_render.assert_called_once_with(request, 'viewer/favorites.html', mock.ANY)
    self.assertDictEqual(mock_render.call_args[0][2], _FAVORITES_CONTEXT)
    mock_delete.assert_called_once_with(1, 11)
    mock_save.assert_called_once_with()

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  def test_ServeFavorites_User_404(self, mock_db: mock.MagicMock) -> None:
    """Test."""
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    with self.assertRaises(views.http.Http404):
      views.ServeFavorites(mock.Mock(views.http.HttpRequest), 5)

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapfavorites.fapdata.FapDatabase.Save')
  def test_ServeFavorite_All_On_And_Tagging(
      self, mock_save: mock.MagicMock, mock_render: mock.MagicMock,
      mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    db = _TestDBFactory()  # pylint: disable=no-value-for-parameter
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
    new_tags = {sha: db.blobs[sha]['tags'] for sha in _FAVORITE_CONTEXT_ALL_ON['blobs_data']}
    self.assertDictEqual(new_tags, _FAVORITE_NEW_TAGS)
    mock_render.assert_called_once_with(request, 'viewer/favorite.html', mock.ANY)
    self.assertDictEqual(mock_render.call_args[0][2], _FAVORITE_CONTEXT_ALL_ON)
    mock_save.assert_called_once_with()

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapfavorites.fapdata.FapDatabase.Save')
  def test_ServeFavorite_All_Off(
      self, mock_save: mock.MagicMock, mock_render: mock.MagicMock,
      mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {}
    request.GET = {
        'portrait': '0',  # by default, no duplicates
        'landscape': '0',
        'lock': '1',
    }
    views.ServeFavorite(request, 1, 10)
    mock_render.assert_called_once_with(request, 'viewer/favorite.html', mock.ANY)
    self.assertDictEqual(mock_render.call_args[0][2], _FAVORITE_CONTEXT_ALL_OFF)
    mock_save.assert_not_called()

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapfavorites.fapdata.FapDatabase.Save')
  def test_ServeFavorite_Filter_Duplicates(
      self, mock_save: mock.MagicMock, mock_render: mock.MagicMock,
      mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {}
    request.GET = {
        'portrait': '1',  # by default, no duplicates
        'landscape': '1',
    }
    views.ServeFavorite(request, 1, 10)
    mock_render.assert_called_once_with(request, 'viewer/favorite.html', mock.ANY)
    self.assertDictEqual(mock_render.call_args[0][2], _FAVORITE_CONTEXT_FILTER_DUPLICATES)
    mock_save.assert_not_called()

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapfavorites.fapdata.FapDatabase.Save')
  def test_ServeFavorite_Filter_Landscapes_Only(
      self, mock_save: mock.MagicMock, mock_render: mock.MagicMock,
      mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {}
    request.GET = {
        'dup': '1',
        'portrait': '2',
        'landscape': '2',  # when both are set to '2' landscapes will "win"
    }
    views.ServeFavorite(request, 1, 10)
    mock_render.assert_called_once_with(request, 'viewer/favorite.html', mock.ANY)
    # the context should be similar to _FAVORITE_CONTEXT_ALL_ON: check only some fields
    self.assertSetEqual(
        set(mock_render.call_args[0][2]['blobs_data'].keys()),
        {'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e'})
    self.assertEqual(mock_render.call_args[0][2]['portrait_url'], 'portrait=0')
    self.assertEqual(mock_render.call_args[0][2]['landscape_url'], 'landscape=2')
    mock_save.assert_not_called()

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapfavorites.fapdata.FapDatabase.Save')
  def test_ServeFavorite_Filter_Portraits_Only(
      self, mock_save: mock.MagicMock, mock_render: mock.MagicMock,
      mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {}
    request.GET = {
        'dup': '1',
        'portrait': '2',
        'landscape': '0',
    }
    views.ServeFavorite(request, 1, 10)
    mock_render.assert_called_once_with(request, 'viewer/favorite.html', mock.ANY)
    # the context should be similar to _FAVORITE_CONTEXT_ALL_ON: check only some fields
    self.assertSetEqual(
        set(mock_render.call_args[0][2]['blobs_data'].keys()),
        {'9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
         'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'})
    self.assertEqual(mock_render.call_args[0][2]['portrait_url'], 'portrait=2')
    self.assertEqual(mock_render.call_args[0][2]['landscape_url'], 'landscape=0')
    mock_save.assert_not_called()

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapfavorites.fapdata.FapDatabase.Save')
  def test_ServeFavorite_Tag_Filtering_1(
      self, mock_save: mock.MagicMock, mock_render: mock.MagicMock,
      mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {}
    request.GET = {
        'dup': '1',
        'tf1': '2',
        'tv1': '3',
        'tf2': '0',
        'tv2': '1',
    }
    views.ServeFavorite(request, 1, 10)
    mock_render.assert_called_once_with(request, 'viewer/favorite.html', mock.ANY)
    # the context should be similar to _FAVORITE_CONTEXT_ALL_ON: check only some fields
    self.assertSetEqual(
        set(mock_render.call_args[0][2]['blobs_data'].keys()),
        {'0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19'})
    self.assertEqual(mock_render.call_args[0][2]['tag_url_1'], 'tf1=2')
    self.assertEqual(mock_render.call_args[0][2]['value_url_1'], 'tv1=3')
    self.assertEqual(mock_render.call_args[0][2]['tag_url_2'], 'tf2=0')
    self.assertEqual(mock_render.call_args[0][2]['value_url_2'], 'tv2=1')
    mock_save.assert_not_called()

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapfavorites.fapdata.FapDatabase.Save')
  def test_ServeFavorite_Tag_Filtering_2(
      self, mock_save: mock.MagicMock, mock_render: mock.MagicMock,
      mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {}
    request.GET = {
        'dup': '1',
        'tf1': '0',
        'tv1': '24',
        'tf2': '2',
        'tv2': '1',
    }
    views.ServeFavorite(request, 1, 10)
    mock_render.assert_called_once_with(request, 'viewer/favorite.html', mock.ANY)
    # the context should be similar to _FAVORITE_CONTEXT_ALL_ON: check only some fields
    self.assertSetEqual(
        set(mock_render.call_args[0][2]['blobs_data'].keys()),
        {'9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
         'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'})
    self.assertEqual(mock_render.call_args[0][2]['tag_url_1'], 'tf1=0')
    self.assertEqual(mock_render.call_args[0][2]['value_url_1'], 'tv1=24')
    self.assertEqual(mock_render.call_args[0][2]['tag_url_2'], 'tf2=2')
    self.assertEqual(mock_render.call_args[0][2]['value_url_2'], 'tv2=1')
    mock_save.assert_not_called()

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  def test_ServeFavorite_User_404(self, mock_db: mock.MagicMock) -> None:
    """Test."""
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    with self.assertRaises(views.http.Http404):
      views.ServeFavorite(mock.Mock(views.http.HttpRequest), 5, 10)

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  def test_ServeFavorite_Folder_404(self, mock_db: mock.MagicMock) -> None:
    """Test."""
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    with self.assertRaises(views.http.Http404):
      views.ServeFavorite(mock.Mock(views.http.HttpRequest), 1, 50)

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapfavorites.fapdata.FapDatabase.Save')
  def test_ServeTag_Root_And_Create(
      self, mock_save: mock.MagicMock, mock_render: mock.MagicMock,
      mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {'named_child': 'new-tag-foo'}
    request.GET = {}
    views.ServeTag(request, 0)
    mock_render.assert_called_once_with(request, 'viewer/tag.html', mock.ANY)
    self.assertDictEqual(mock_render.call_args[0][2], _TAG_ROOT_CONTEXT)
    mock_save.assert_called_once_with()

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapfavorites.fapdata.FapDatabase.Save')
  def test_ServeTag_Leaf_And_Delete(
      self, mock_save: mock.MagicMock, mock_render: mock.MagicMock,
      mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    db = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    mock_db.return_value = db
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {'delete_input': '33'}
    request.GET = {}
    views.ServeTag(request, 2)
    new_tags = {sha: db.blobs[sha]['tags'] for sha in db.blobs.keys()}
    self.assertDictEqual(new_tags, _TAG_NEW_TAGS)
    mock_render.assert_called_once_with(request, 'viewer/tag.html', mock.ANY)
    self.assertDictEqual(mock_render.call_args[0][2], _TAG_LEAF_CONTEXT_DELETE)
    mock_save.assert_called_once_with()

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapfavorites.fapdata.FapDatabase.Save')
  def test_ServeTag_Leaf_And_Rename(
      self, mock_save: mock.MagicMock, mock_render: mock.MagicMock,
      mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {'rename_tag': 'The One'}
    request.GET = {}
    views.ServeTag(request, 1)
    mock_render.assert_called_once_with(request, 'viewer/tag.html', mock.ANY)
    self.assertDictEqual(mock_render.call_args[0][2], _TAG_LEAF_CONTEXT_RENAME)
    mock_save.assert_called_once_with()

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapfavorites.fapdata.FapDatabase.Save')
  def test_ServeTag_All_On_And_Clear_Tag(
      self, mock_save: mock.MagicMock, mock_render: mock.MagicMock,
      mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    db = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    mock_db.return_value = db
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {
        'clear_tag': '2',
        'selected_blobs': ('0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19,'
                           '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8'),
    }
    request.GET = {
        'dup': '1',  # by default, show portrait+landscape
        'lock': '1',
    }
    views.ServeTag(request, 2)
    clean_tags = {sha: db.blobs[sha]['tags'] for sha in request.POST['selected_blobs'].split(',')}
    self.assertDictEqual(clean_tags, {
        '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19': {3},
        '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8': {33},
    })
    mock_render.assert_called_once_with(request, 'viewer/tag.html', mock.ANY)
    self.assertDictEqual(mock_render.call_args[0][2], _TAG_LEAF_CLEAR_TAG)
    mock_save.assert_called_once_with()

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  def test_ServeTag_404(self, mock_db: mock.MagicMock) -> None:
    """Test."""
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    with self.assertRaises(views.http.Http404):
      views.ServeTag(mock.Mock(views.http.HttpRequest), 666)

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapfavorites.fapdata.FapDatabase.FindDuplicates')
  @mock.patch('fapfavorites.fapdata.FapDatabase.Save')
  def test_ServeDuplicates_And_ReRun(
      self, mock_save: mock.MagicMock, mock_find: mock.MagicMock,
      mock_render: mock.MagicMock, mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    mock_find.return_value = 88
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {'re_run': '1'}
    request.GET = {}
    views.ServeDuplicates(request)
    mock_render.assert_called_once_with(request, 'viewer/duplicates.html', mock.ANY)
    self.assertDictEqual(mock_render.call_args[0][2], _DUPLICATES_CONTEXT_RE_RUN)
    mock_find.assert_called_once_with()
    mock_save.assert_called_once_with()

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapfavorites.fapdata.FapDatabase.Save')
  def test_ServeDuplicates_And_Delete_Pending(
      self, mock_save: mock.MagicMock,
      mock_render: mock.MagicMock, mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {'delete_pending': '1'}
    request.GET = {}
    views.ServeDuplicates(request)
    mock_render.assert_called_once_with(request, 'viewer/duplicates.html', mock.ANY)
    self.assertDictEqual(mock_render.call_args[0][2], _DUPLICATES_CONTEXT_DELETE_PENDING)
    mock_save.assert_called_once_with()

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapfavorites.fapdata.FapDatabase.Save')
  def test_ServeDuplicates_And_Delete_All(
      self, mock_save: mock.MagicMock,
      mock_render: mock.MagicMock, mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {'delete_all': '1'}
    request.GET = {}
    views.ServeDuplicates(request)
    mock_render.assert_called_once_with(request, 'viewer/duplicates.html', mock.ANY)
    self.assertDictEqual(mock_render.call_args[0][2], _DUPLICATES_CONTEXT_DELETE_ALL)
    mock_save.assert_called_once_with()

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapfavorites.fapdata.FapDatabase.Save')
  def test_ServeDuplicates_And_Edit_Parameters(
      self, mock_save: mock.MagicMock,
      mock_render: mock.MagicMock, mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    db = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    db.DeleteAllDuplicates()  # work with no duplicates here, just for simplicity
    mock_db.return_value = db
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {
        'parameters_form_used': '1',
        'enabled_regular_percept': 'on',
        'regular_percept': '7',
        'enabled_animated_diff': 'on',
        'animated_diff': '2',
        'enabled_regular_diff': 'on',
        'regular_diff': '5',
        'enabled_animated_average': 'on',
        'animated_average': '0',
        'enabled_regular_average': 'on',
        'regular_average': '1',
        'enabled_regular_cnn': 'on',
        'regular_cnn': '0.91',
        'enabled_animated_cnn': 'on',
        'animated_cnn': '0.99',
    }
    request.GET = {}
    views.ServeDuplicates(request)
    mock_render.assert_called_once_with(request, 'viewer/duplicates.html', mock.ANY)
    self.assertDictEqual(mock_render.call_args[0][2], _DUPLICATES_CONTEXT_EDIT_PARAMETERS)
    mock_save.assert_called_once_with()

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapfavorites.fapdata.FapDatabase.Save')
  def test_ServeDuplicate_Blob(
      self, mock_save: mock.MagicMock, mock_render: mock.MagicMock,
      mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {}
    request.GET = {}
    views.ServeDuplicate(
        # this is a blob-only (hash collision) duplicate
        request, '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf')
    mock_render.assert_called_once_with(request, 'viewer/duplicate.html', mock.ANY)
    self.assertDictEqual(mock_render.call_args[0][2], _DUPLICATE_BLOB_CONTEXT)
    mock_save.assert_not_called()

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapfavorites.fapdata.FapDatabase.Save')
  def test_ServeDuplicate_Set(
      self, mock_save: mock.MagicMock, mock_render: mock.MagicMock,
      mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    db = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    mock_db.return_value = db
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {
        '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19': 'false',
        '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': 'skip',
        '1_11_110': 'skip',
        '2_20_202': 'keep',  # this one should be 'skip' and we expect it to be corrected in-call
        'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': 'keep',
        '1_10_100': 'keep',
        '1_10_104': 'skip',
        '2_20_203': 'skip',
    }
    request.GET = {}
    views.ServeDuplicate(
        request, 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e')
    mock_render.assert_called_once_with(request, 'viewer/duplicate.html', mock.ANY)
    self.assertDictEqual(mock_render.call_args[0][2], _DUPLICATE_SET_CONTEXT)
    mock_save.assert_called_once_with()

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  def test_ServeDuplicate_Blob_404(self, mock_db: mock.MagicMock) -> None:
    """Test."""
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    with self.assertRaises(views.http.Http404):
      views.ServeDuplicate(mock.Mock(views.http.HttpRequest), 'not-a-valid-blob-hash')

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  def test_ServeDuplicate_Singleton_404(self, mock_db: mock.MagicMock) -> None:
    """Test."""
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    with self.assertRaises(views.http.Http404):
      views.ServeDuplicate(
          mock.Mock(views.http.HttpRequest),
          # this hash has no duplicate set nor hash collision
          'dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180')

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapfavorites.fapdata.FapDatabase.Save')
  def test_ServeDuplicate_Update_Valid(
      self, mock_save: mock.MagicMock, mock_render: mock.MagicMock,
      mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    db = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    mock_db.return_value = db
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {
        # this is a blob-only (hash collision) duplicate
        '1_10_101': 'skip',
        '1_11_111': 'keep',
        '2_20_201': 'skip',
    }
    request.GET = {}
    views.ServeDuplicate(
        request, '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf')
    mock_render.assert_called_once_with(request, 'viewer/duplicate.html', mock.ANY)
    self.assertDictEqual(mock_render.call_args[0][2], _DUPLICATE_IDENTICAL_SET)
    mock_save.assert_called_once_with()

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapfavorites.fapdata.FapDatabase.Save')
  def test_ServeDuplicate_Update_Invalid_All_Skip(
      self, mock_save: mock.MagicMock, mock_render: mock.MagicMock,
      mock_db: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    db = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    mock_db.return_value = db
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {
        # this is a blob-only (hash collision) duplicate
        '1_10_101': 'skip',
        '1_11_111': 'skip',
        '2_20_201': 'skip',
    }
    request.GET = {}
    views.ServeDuplicate(
        request, '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf')
    mock_render.assert_called_once_with(request, 'viewer/duplicate.html', mock.ANY)
    duplicate_response_all_skip = copy.deepcopy(_DUPLICATE_IDENTICAL_SET)
    duplicate_response_all_skip['duplicates'][
        '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf']['loc'][2][
            'verdict'] = 'new'
    duplicate_response_all_skip['error_message'] = (
        'Key \'9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf\' in POST data '
        'is \'keep\' but all child identical selections are "skip": '
        '{(1, 10, 101): \'skip\', (1, 11, 111): \'skip\', (2, 20, 201): \'skip\'}')
    self.assertDictEqual(mock_render.call_args[0][2], duplicate_response_all_skip)
    mock_save.assert_not_called()

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('django.http.HttpResponse')
  @mock.patch('fapfavorites.fapdata.FapDatabase.HasBlob')
  @mock.patch('fapfavorites.fapdata.FapDatabase.GetBlob')
  def test_ServeBlob(
      self, mock_get_blob: mock.MagicMock, mock_has_blob: mock.MagicMock,
      mock_response: mock.MagicMock, mock_db: mock.MagicMock) -> None:
    """Test."""
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    mock_has_blob.return_value = True
    mock_get_blob.return_value = b'image binary data'
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {}
    request.GET = {}
    views.ServeBlob(request, '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8')
    mock_response.assert_called_once_with(content=b'image binary data', content_type='image/gif')
    mock_has_blob.assert_called_once_with(
        '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8')
    mock_get_blob.assert_called_once_with(
        '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8')

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  def test_ServeBlob_Existence_404(self, mock_db: mock.MagicMock) -> None:
    """Test."""
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    with self.assertRaises(views.http.Http404):
      views.ServeBlob(mock.Mock(views.http.HttpRequest), 'hash-does-not-exist')

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('fapfavorites.fapdata.FapDatabase.HasBlob')
  def test_ServeBlob_Blob_Not_On_Disk_404(
      self, mock_has_blob: mock.MagicMock, mock_db: mock.MagicMock) -> None:
    """Test."""
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    mock_has_blob.return_value = False
    with self.assertRaises(views.http.Http404):
      views.ServeBlob(
          mock.Mock(views.http.HttpRequest),
          '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8')

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('fapfavorites.fapdata.FapDatabase.HasBlob')
  def test_ServeBlob_Invalid_Extension_404(
      self, mock_has_blob: mock.MagicMock, mock_db: mock.MagicMock) -> None:
    """Test."""
    db = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    mock_db.return_value = db
    mock_has_blob.return_value = True
    db.blobs['5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8']['ext'] = 'invalid'
    with self.assertRaises(views.http.Http404):
      views.ServeBlob(
          mock.Mock(views.http.HttpRequest),
          '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8')

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('django.http.HttpResponse')
  @mock.patch('fapfavorites.fapdata.FapDatabase.HasThumbnail')
  @mock.patch('fapfavorites.fapdata.FapDatabase.GetThumbnail')
  def test_ServeThumb(
      self, mock_get_thumb: mock.MagicMock, mock_has_thumb: mock.MagicMock,
      mock_response: mock.MagicMock, mock_db: mock.MagicMock) -> None:
    """Test."""
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    mock_has_thumb.return_value = True
    mock_get_thumb.return_value = b'image binary data'
    request = mock.Mock(views.http.HttpRequest)
    request.POST = {}
    request.GET = {}
    views.ServeThumb(request, '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8')
    mock_response.assert_called_once_with(content=b'image binary data', content_type='image/gif')
    mock_has_thumb.assert_called_once_with(
        '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8')
    mock_get_thumb.assert_called_once_with(
        '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8')

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  def test_ServeThumb_Existence_404(self, mock_db: mock.MagicMock) -> None:
    """Test."""
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    with self.assertRaises(views.http.Http404):
      views.ServeThumb(mock.Mock(views.http.HttpRequest), 'hash-does-not-exist')

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('fapfavorites.fapdata.FapDatabase.HasThumbnail')
  def test_ServeThumb_Thumb_Not_On_Disk_404(
      self, mock_has_thumb: mock.MagicMock, mock_db: mock.MagicMock) -> None:
    """Test."""
    mock_db.return_value = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    mock_has_thumb.return_value = False
    with self.assertRaises(views.http.Http404):
      views.ServeThumb(
          mock.Mock(views.http.HttpRequest),
          '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8')

  @mock.patch('fapfavorites.viewer.views._DBFactory')
  @mock.patch('fapfavorites.fapdata.FapDatabase.HasThumbnail')
  def test_ServeThumb_Invalid_Extension_404(
      self, mock_has_thumb: mock.MagicMock, mock_db: mock.MagicMock) -> None:
    """Test."""
    db = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    mock_db.return_value = db
    mock_has_thumb.return_value = True
    db.blobs['5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8']['ext'] = 'invalid'
    with self.assertRaises(views.http.Http404):
      views.ServeThumb(
          mock.Mock(views.http.HttpRequest),
          '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8')


@mock.patch('fapfavorites.fapdata.os.path.isdir')
def _TestDBFactory(mock_isdir: mock.MagicMock) -> views.fapdata.FapDatabase:
  mock_isdir.return_value = True
  db = views.fapdata.FapDatabase('/foo/', create_if_needed=False)
  db._db = copy.deepcopy(_MOCK_DATABASE)  # needed: some of the test methods will change the dict!
  db.duplicates = views.duplicates.Duplicates(db._duplicates_registry, db._duplicates_key_index)
  return db


_MOCK_DATABASE: views.fapdata._DatabaseType = {
    'configs': {
        'duplicates_sensitivity_regular': {
            'percept': 10,
            'diff': 10,
            'average': 3,
            'wavelet': 3,
            'cnn': 0.93,
        },
        'duplicates_sensitivity_animated': {
            'percept': 3,
            'diff': 4,
            'average': -1,
            'wavelet': -1,
            'cnn': 0.98,
        },
    },
    'users': {
        1: {
            'name': 'Luke',  # has 2 albums
            'date_albums': 1675350000,
            'date_finished': 1675390000,
            'date_audit': 1675368770,
        },
        2: {
            'name': 'Ben',  # has 1 album
            'date_albums': 1675370000,
            'date_finished': 0,
            'date_audit': 0,
        },
        3: {
            'name': 'Yoda',  # has 0 albums
            'date_albums': 0,
            'date_finished': 0,
            'date_audit': 0,
        },
    },
    'favorites': {
        1: {  # Luke
            10: {
                'date_blobs': 1675300000,
                'images': [100, 101, 102, 103, 104],
                'failed_images': {
                    (144, 1675360110, 'failed0.jpg', 'f-url-0'),
                },
                'name': 'luke-folder-10',
                'pages': 9,
            },
            11: {
                'date_blobs': 1671000000,
                'images': [110, 111, 112],
                'failed_images': set(),
                'name': 'luke-folder-11',
                'pages': 8,
            },
        },
        2: {  # Ben
            20: {
                'date_blobs': 1673000000,
                'images': [200, 201, 202, 203],
                'failed_images': {
                    (244, 1675360770, 'failed1.jpg', 'f-url-1'),
                    (255, 1675360880, 'failed2.jpg', 'f-url-2'),
                },
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
                (1, 10, 102): ('name-102.jpg', 'new'),
            },
            'percept': 'cd4fc618316732e7',
            'average': '303830301a1c387f',
            'diff': '60e2c3c2d2b1e2ce',
            'wavelet': '303838383a1f3e7f',
            'cnn': np.array([1, 2, 3]),
            'sz': 54643,
            'sz_thumb': 54643,
            'tags': {2, 3},
            'width': 198,  # image will be considered "square" aspect
            'date': 1675368770,
            'gone': {},
        },
        '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': {
            'animated': False,
            'ext': 'png',
            'height': 173,
            'loc': {
                (1, 11, 110): ('name-110.png', 'skip'),
                (2, 20, 202): ('name-202.png', 'keep'),
            },
            'percept': 'd99ee32e586716c8',
            'average': 'ffffff9a180060c8',
            'diff': '6854541633d5c991',
            'wavelet': 'ffffbf88180060c8',
            'cnn': np.array([1, 2, 3]),
            'sz': 45309,
            'sz_thumb': 45309,
            'tags': set(),  # untagged!
            'width': 130,
            'date': 1675368770,
            'gone': {
                110: (1675368770, fapdata._FailureLevel.IMAGE_PAGE, 'url-110'),
                202: (1675368770, fapdata._FailureLevel.FULL_RES, 'url-202'),
            },
        },
        '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8': {
            'animated': True,
            'ext': 'gif',
            'height': 500,
            'tags': {246, 33},
            'loc': {
                (2, 20, 200): ('name-200.gif', 'new'),
            },
            'percept': 'e699669966739866',
            'average': 'ffffff9a180060c8',
            'diff': '6854541633d5c991',
            'wavelet': 'ffffbf88180060c8',
            'cnn': np.array([1, 2, 3]),
            'sz': 444973,
            'sz_thumb': 302143,
            'width': 100,
            'date': 1675360770,
            'gone': {},
        },
        '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {
            'animated': False,
            'ext': 'jpg',
            'height': 200,
            'loc': {
                (1, 10, 101): ('name-101.jpg', 'skip'),
                (1, 11, 111): ('name-111.jpg', 'keep'),
                (2, 20, 201): ('name-201.jpg', 'new'),
            },
            'percept': 'd99ee32e586716c8',
            'average': '091b5f7761323000',
            'diff': 'ffffbf88180060c8',
            'wavelet': '737394c5d3e66431',
            'cnn': np.array([1, 2, 3]),
            'sz': 101,
            'sz_thumb': 0,
            'tags': {2, 11, 33},
            'width': 160,
            'date': 1675360770,
            'gone': {},
        },
        'dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180': {
            'animated': False,
            'ext': 'jpg',
            'height': 222,
            'loc': {
                (1, 11, 112): ('name-112.jpg', 'new'),
            },
            'percept': '89991f6f62a63479',
            'average': '091b5f7761323000',
            'diff': '737394c5d3e66431',
            'wavelet': '091b7f7f71333018',
            'cnn': np.array([1, 2, 3]),
            'sz': 89216,
            'sz_thumb': 11890,
            'tags': {246},
            'width': 300,
            'date': 1675360770,
            'gone': {},
        },
        'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': {
            'animated': False,
            'ext': 'jpg',
            'height': 246,
            'loc': {
                (1, 10, 100): ('name-100.jpg', 'skip'),
                (1, 10, 104): ('name-104.jpg', 'new'),  # dup in same album as above!
                (2, 20, 203): ('name-203.jpg', 'skip'),
            },
            'percept': 'cc8fc37638703ee1',
            'average': '3838381810307078',
            'diff': '626176372565c3f2',
            'wavelet': '3e3f3f1b10307878',
            'cnn': np.array([1, 2, 3]),
            'sz': 56583,
            'sz_thumb': 56583,
            'tags': {1, 2},
            'width': 200,
            'date': 1675360770,
            'gone': {
                104: (1675360770, fapdata._FailureLevel.URL_EXTRACTION, 'url-104'),
            },
        },
        'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e': {
            'animated': True,
            'ext': 'gif',
            'height': 100,
            'tags': {1, 24, 33},
            'loc': {
                (1, 10, 103): ('name-103.gif', 'new'),
            },
            'percept': 'e699669966739866',
            'average': 'ffffffffffffe7e7',
            'diff': '000000000000080c',
            'wavelet': 'ffffffffffffe7e7',
            'cnn': np.array([1, 2, 3]),
            'sz': 444973,
            'sz_thumb': 302143,
            'width': 500,
            'date': 1675368770,
            'gone': {
                103: (1675368770, fapdata._FailureLevel.IMAGE_PAGE, 'url-103'),
            },
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
            'sources': {
                'average': {
                    ('321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
                     'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'): 2,
                },
                'cnn': {
                    ('0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19',
                     '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6'): 0.96,
                    ('321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
                     'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'): 0.98,
                    ('0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19',
                     'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'): 0.95,
                },
                'diff': {
                    ('0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19',
                     '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6'): 9,
                },
                'percept': {
                    ('321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
                     'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'): 10,
                    ('0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19',
                     'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'): 0,
                },
                'wavelet': {
                    ('0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19',
                     'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'): 1,
                },
            },
            'verdicts': {
                '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19': 'new',
                '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': 'keep',
                'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': 'skip',
            },
        },
        ('5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8',
         'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e'): {
            'sources': {
                'diff': {
                    ('5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8',
                     'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e'): 1.0,
                },
                'percept': {
                    ('5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8',
                     'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e'): 2.0,
                },
            },
            'verdicts': {
                '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8': 'false',
                'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e': 'false',
            },
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
        10: {  # unused tag!
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
    'id_action': 2,
    'identical': 3,
    'n_images': 7,
    'database_stats': [
        ('Database is located in \'/foo/imagefap.database\', and is 97.66kb '
         '(8.804% of total images size)'),
        ('1.08Mb total (unique) images size (101b min, 434.54kb max, '
         '158.45kb mean with 190.33kb standard deviation, 2 are animated)'),
        ('Pixel size (width, height): 22.49k pixels min (130, 173), '
         '66.60k pixels max (300, 222), 44.27k mean with 14.35k standard deviation'),
        ('754.60kb total thumbnail size (0b min, 295.06kb max, 107.80kb mean with '
         '129.59kb standard deviation), 68.0% of total images size'),
        '',
        '3 users',
        '3 favorite galleries (oldest: 2022/Dec/14-06:40:00-UTC / newer: 2023/Feb/02-01:06:40-UTC)',
        '7 unique images (12 total, 8 exact duplicates)',
        '3 unique failed images in all user albums',
        '3 unique images are now disappeared from imagefap site',
        '5 perceptual duplicates in 2 groups',
    ],
}

_USERS_CONTEXT: dict[str, Any] = {
    'users': {
        1: {
            'name': 'Luke',
            'date_albums': '2023/Feb/02-15:00:00-UTC',
            'date_finished': '2023/Feb/03-02:06:40-UTC',
            'date_audit': '2023/Feb/02-20:12:50-UTC',
            'n_img': 8,
            'n_failed': 1,
            'n_animated': '1 (12.5%)',
            'n_albums': 2,
            'files_sz': '729.99kb',
            'thumbs_sz': '514.80kb',
            'min_sz': '101b',
            'max_sz': '434.54kb',
            'mean_sz': '91.25kb',
            'dev_sz': '141.78kb',
        },
        2: {
            'name': 'Ben',
            'date_albums': '2023/Feb/02-20:33:20-UTC',
            'date_finished': '-',
            'date_audit': '-',
            'n_img': 4,
            'n_failed': 2,
            'n_animated': '1 (25.0%)',
            'n_albums': 1,
            'files_sz': '534.15kb',
            'thumbs_sz': '394.57kb',
            'min_sz': '101b',
            'max_sz': '434.54kb',
            'mean_sz': '133.54kb',
            'dev_sz': '202.08kb',
        },
        3: {
            'name': 'Yoda',
            'date_albums': '-',
            'date_finished': '-',
            'date_audit': '-',
            'n_img': 0,
            'n_failed': 0,
            'n_animated': '0 (0.0%)',
            'n_albums': 0,
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
    'total_failed': 3,
    'total_animated': '2 (16.7%)',
    'total_albums': 3,
    'total_sz': '1.23Mb',
    'total_thumbs': '909.36kb',
    'total_file_storage': '2.12Mb',
    'warning_message': ('User Yoda (3) deleted, and with them 66 blobs (images) deleted, '
                        'together with their thumbnails, plus 22 duplicates groups abandoned'),
    'error_message': None,
}

_FAVORITES_CONTEXT: dict[str, Any] = {
    'user_id': 1,
    'user_name': 'Luke',
    'date_albums': '2023/Feb/02-15:00:00-UTC',
    'date_finished': '2023/Feb/03-02:06:40-UTC',
    'date_audit': '2023/Feb/02-20:12:50-UTC',
    'favorites': {
        10: {
            'name': 'luke-folder-10',
            'pages': 9,
            'date': '2023/Feb/02-01:06:40-UTC',
            'count': 5,
            'failed': 1,
            'disappeared': '3 (60.0%)',
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
            'failed': 0,
            'disappeared': '1 (33.3%)',
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
    'failed_count': 1,
    'disappeared_count': '4 (50.0%)',
    'page_count': 17,
    'total_sz': '729.99kb',
    'total_thumbs_sz': '514.80kb',
    'total_file_storage': '1.22Mb',
    'total_animated': '1 (12.5%)',
    'warning_message': ('Favorites album Luke/luke-folder-11 (1/11) deleted, and with it 66 '
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
    'show_portraits': 1,
    'portrait_url': 'portrait=1',
    'show_landscapes': 1,
    'landscape_url': 'landscape=1',
    'locked_for_tagging': False,
    'tagging_url': 'lock=0',
    'tag_filter_1': 1,
    'tag_url_1': 'tf1=1',
    'tag_value_1': 0,
    'value_url_1': 'tv1=0',
    'tag_filter_2': 1,
    'tag_url_2': 'tf2=1',
    'tag_value_2': 0,
    'value_url_2': 'tv2=0',
    'selected_tag': 24,
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
    'count_disappeared': 3,
    'stacked_disappeared': [
        [
            (100, 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'),
            (103, 'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e'),
            (104, 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'),
            (0, ''),
        ],
    ],
    'blobs_data': {
        '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19': {
            'name':
            'name-102.jpg',
            'sz': '53.36kb',
            'dimensions': '198x200 (WxH)',
            'tags': 'three, two, two/two-four',
            'has_duplicate': False,
            'album_duplicate': False,
            'has_percept': True,
            'imagefap': 'https://www.imagefap.com/photo/102/',
            'fap_id': 102,
            'duplicate_hints': ('Visual: Ben/ben-folder-20/\'name-202.png\' (2/20/202)\n'
                                'Visual: Ben/ben-folder-20/\'name-203.jpg\' (2/20/203)\n'
                                'Visual: Luke/luke-folder-10/\'name-100.jpg\' (1/10/100)\n'
                                'Visual: Luke/luke-folder-10/\'name-102.jpg\' (1/10/102) <= THIS\n'
                                'Visual: Luke/luke-folder-10/\'name-104.jpg\' (1/10/104)\n'
                                'Visual: Luke/luke-folder-11/\'name-110.png\' (1/11/110)'),
            'date': '2023/Feb/02-20:12:50-UTC',
            'gone': [],
            'verdict': 'new',
        },
        '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {
            'name': 'name-101.jpg',
            'sz': '101b',
            'dimensions': '160x200 (WxH)',
            'tags': 'one/one-one, three/three-three, two',
            'has_duplicate': True,
            'album_duplicate': False,
            'has_percept': False,
            'imagefap': 'https://www.imagefap.com/photo/101/',
            'fap_id': 101,
            'duplicate_hints': ('Exact: Ben/ben-folder-20/\'name-201.jpg\' (2/20/201)\n'
                                'Exact: Luke/luke-folder-10/\'name-101.jpg\' (1/10/101) <= THIS\n'
                                'Exact: Luke/luke-folder-11/\'name-111.jpg\' (1/11/111)'),
            'date': '2023/Feb/02-17:59:30-UTC',
            'gone': [],
            'verdict': 'skip',
        },
        'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': {
            'name': 'name-104.jpg',
            'sz': '55.26kb',
            'dimensions': '200x246 (WxH)',
            'tags': 'one, two, two/two-four',
            'has_duplicate': True,
            'album_duplicate': True,
            'has_percept': True,
            'imagefap': 'https://www.imagefap.com/photo/104/',
            'fap_id': 104,
            'duplicate_hints': ('Exact: Ben/ben-folder-20/\'name-203.jpg\' (2/20/203)\n'
                                'Exact: Luke/luke-folder-10/\'name-100.jpg\' (1/10/100)\n'
                                'Exact: Luke/luke-folder-10/\'name-104.jpg\' (1/10/104) <= THIS\n'
                                'Visual: Ben/ben-folder-20/\'name-202.png\' (2/20/202)\n'
                                'Visual: Ben/ben-folder-20/\'name-203.jpg\' (2/20/203)\n'
                                'Visual: Luke/luke-folder-10/\'name-100.jpg\' (1/10/100)\n'
                                'Visual: Luke/luke-folder-10/\'name-102.jpg\' (1/10/102)\n'
                                'Visual: Luke/luke-folder-10/\'name-104.jpg\' (1/10/104) <= THIS\n'
                                'Visual: Luke/luke-folder-11/\'name-110.png\' (1/11/110)'),
            'date': '2023/Feb/02-17:59:30-UTC',
            'gone': [
                (104, '2023/Feb/02-17:59:30-UTC', 'URL_EXTRACTION'),
            ],
            'verdict': 'new',
        },
        'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e': {
            'name': 'name-103.gif',
            'sz': '434.54kb',
            'dimensions': '500x100 (WxH)',
            'tags': 'one, three/three-three, two/two-four',
            'has_duplicate': False,
            'album_duplicate': False,
            'has_percept': False,
            'imagefap': 'https://www.imagefap.com/photo/103/',
            'fap_id': 103,
            'duplicate_hints': '',
            'date': '2023/Feb/02-20:12:50-UTC',
            'gone': [
                (103, '2023/Feb/02-20:12:50-UTC', 'IMAGE_PAGE'),
            ],
            'verdict': 'new',
        },
    },
    'form_tags': [
        (1, 'one', 'one'),
        (11, 'one-one', 'one/one-one'),
        (10, 'plain', 'plain'),
        (3, 'three', 'three'),
        (33, 'three-three', 'three/three-three'),
        (2, 'two', 'two'),
        (24, 'two-four', 'two/two-four'),
        (246, 'deep', 'two/two-four/deep'),
        (22, 'two-two', 'two/two-two'),
    ],
    'failed_count': 1,
    'failed_data': [
        {
            'id': 144,
            'img_page': 'https://www.imagefap.com/photo/144/',
            'time': '2023/Feb/02-17:48:30-UTC',
            'name': 'failed0.jpg',
            'url': 'f-url-0',
        },
    ],
    'warning_message': '2 images tagged with two/two-four (24)',
    'error_message': None,
}

_FAVORITE_NEW_TAGS: dict[str, set[int]] = {
    '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19': {2, 3, 24},
    '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {2, 11, 33},
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
    'show_portraits': 0,
    'portrait_url': 'portrait=0',
    'show_landscapes': 0,
    'landscape_url': 'landscape=0',
    'locked_for_tagging': True,
    'tagging_url': 'lock=1',
    'tag_filter_1': 1,
    'tag_url_1': 'tf1=1',
    'tag_value_1': 0,
    'value_url_1': 'tv1=0',
    'tag_filter_2': 1,
    'tag_url_2': 'tf2=1',
    'tag_value_2': 0,
    'value_url_2': 'tv2=0',
    'selected_tag': 0,
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
    'count_disappeared': 0,
    'stacked_disappeared': [],
    'blobs_data': {
        '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19': {
            'name': 'name-102.jpg',
            'sz': '53.36kb',
            'dimensions': '198x200 (WxH)',
            'tags': 'three, two',
            'has_duplicate': False,
            'album_duplicate': False,
            'has_percept': True,
            'imagefap': 'https://www.imagefap.com/photo/102/',
            'fap_id': 102,
            'duplicate_hints': ('Visual: Ben/ben-folder-20/\'name-202.png\' (2/20/202)\n'
                                'Visual: Ben/ben-folder-20/\'name-203.jpg\' (2/20/203)\n'
                                'Visual: Luke/luke-folder-10/\'name-100.jpg\' (1/10/100)\n'
                                'Visual: Luke/luke-folder-10/\'name-102.jpg\' (1/10/102) <= THIS\n'
                                'Visual: Luke/luke-folder-10/\'name-104.jpg\' (1/10/104)\n'
                                'Visual: Luke/luke-folder-11/\'name-110.png\' (1/11/110)'),
            'date': '2023/Feb/02-20:12:50-UTC',
            'gone': [],
            'verdict': 'new',
        },
    },
    'form_tags': _FAVORITE_CONTEXT_ALL_ON['form_tags'],
    'failed_count': 1,
    'failed_data': [
        {
            'id': 144,
            'img_page': 'https://www.imagefap.com/photo/144/',
            'time': '2023/Feb/02-17:48:30-UTC',
            'name': 'failed0.jpg',
            'url': 'f-url-0',
        },
    ],
    'warning_message': None,
    'error_message': None,
}

_FAVORITE_CONTEXT_FILTER_DUPLICATES: dict[str, Any] = {
    'user_id': 1,
    'user_name': 'Luke',
    'folder_id': 10,
    'name': 'luke-folder-10',
    'show_duplicates': False,
    'dup_url': 'dup=0',
    'show_portraits': 1,
    'portrait_url': 'portrait=1',
    'show_landscapes': 1,
    'landscape_url': 'landscape=1',
    'locked_for_tagging': False,
    'tagging_url': 'lock=0',
    'tag_filter_1': 1,
    'tag_url_1': 'tf1=1',
    'tag_value_1': 0,
    'value_url_1': 'tv1=0',
    'tag_filter_2': 1,
    'tag_url_2': 'tf2=1',
    'tag_value_2': 0,
    'value_url_2': 'tv2=0',
    'selected_tag': 0,
    'pages': 9,
    'date': '2023/Feb/02-01:06:40-UTC',
    'count': 2,
    'stacked_blobs': [
        [
            (102, '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19'),
            (103, 'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e'),
            (0, ''),
            (0, ''),
        ],
    ],
    'count_disappeared': 1,
    'stacked_disappeared': [
        [
            (103, 'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e'),
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
            'tags': 'three, two',
            'has_duplicate': False,
            'album_duplicate': False,
            'has_percept': True,
            'imagefap': 'https://www.imagefap.com/photo/102/',
            'fap_id': 102,
            'duplicate_hints': ('Visual: Ben/ben-folder-20/\'name-202.png\' (2/20/202)\n'
                                'Visual: Ben/ben-folder-20/\'name-203.jpg\' (2/20/203)\n'
                                'Visual: Luke/luke-folder-10/\'name-100.jpg\' (1/10/100)\n'
                                'Visual: Luke/luke-folder-10/\'name-102.jpg\' (1/10/102) <= THIS\n'
                                'Visual: Luke/luke-folder-10/\'name-104.jpg\' (1/10/104)\n'
                                'Visual: Luke/luke-folder-11/\'name-110.png\' (1/11/110)'),
            'date': '2023/Feb/02-20:12:50-UTC',
            'gone': [],
            'verdict': 'new',
        },
        'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e': {
            'name': 'name-103.gif',
            'sz': '434.54kb',
            'dimensions': '500x100 (WxH)',
            'tags': 'one, three/three-three, two/two-four',
            'has_duplicate': False,
            'album_duplicate': False,
            'has_percept': False,
            'imagefap': 'https://www.imagefap.com/photo/103/',
            'fap_id': 103,
            'duplicate_hints': '',
            'date': '2023/Feb/02-20:12:50-UTC',
            'gone': [
                (103, '2023/Feb/02-20:12:50-UTC', 'IMAGE_PAGE'),
            ],
            'verdict': 'new',
        },
    },
    'form_tags': _FAVORITE_CONTEXT_ALL_ON['form_tags'],
    'failed_count': 1,
    'failed_data': [
        {
            'id': 144,
            'img_page': 'https://www.imagefap.com/photo/144/',
            'time': '2023/Feb/02-17:48:30-UTC',
            'name': 'failed0.jpg',
            'url': 'f-url-0',
        },
    ],
    'warning_message': None,
    'error_message': None,
}

_TAG_ROOT_CONTEXT: dict[str, Any] = {
    'tags': [
        (4, 'new-tag-foo', 'new-tag-foo', 0),
        (1, 'one', 'one', 0),
        (11, 'one-one', 'one/one-one', 1),
        (10, 'plain', 'plain', 0),
        (3, 'three', 'three', 0),
        (33, 'three-three', 'three/three-three', 1),
        (2, 'two', 'two', 0),
        (24, 'two-four', 'two/two-four', 1),
        (246, 'deep', 'two/two-four/deep', 2),
        (22, 'two-two', 'two/two-two', 1),
    ],
    'show_duplicates': False,
    'dup_url': 'dup=0',
    'show_portraits': 1,
    'portrait_url': 'portrait=1',
    'show_landscapes': 1,
    'landscape_url': 'landscape=1',
    'locked_for_tagging': False,
    'tagging_url': 'lock=0',
    'tag_filter_1': 1,
    'tag_url_1': 'tf1=1',
    'tag_value_1': 0,
    'value_url_1': 'tv1=0',
    'tag_filter_2': 1,
    'tag_url_2': 'tf2=1',
    'tag_value_2': 0,
    'value_url_2': 'tv2=0',
    'selected_tag': 0,
    'count': 0,
    'count_disappeared': 0,
    'stacked_blobs': [],
    'stacked_disappeared': [],
    'blobs_data': {},
    'form_tags': _FAVORITE_CONTEXT_ALL_ON['form_tags'],
    'tag_id': 0,
    'page_depth': 0,
    'page_depth_up': 0,
    'tag_name': None,
    'tag_simple_name': None,
    'warning_message': 'Tag new-tag-foo (4) created',
    'error_message': None,
}

_TAG_LEAF_CONTEXT_DELETE: dict[str, Any] = {
    'tags': [
        (24, 'two-four', 'two/two-four', 1),
        (246, 'deep', 'two/two-four/deep', 2),
        (22, 'two-two', 'two/two-two', 1),
    ],
    'show_duplicates': False,
    'dup_url': 'dup=0',
    'show_portraits': 1,
    'portrait_url': 'portrait=1',
    'show_landscapes': 1,
    'landscape_url': 'landscape=1',
    'locked_for_tagging': False,
    'tagging_url': 'lock=0',
    'tag_filter_1': 1,
    'tag_url_1': 'tf1=1',
    'tag_value_1': 0,
    'value_url_1': 'tv1=0',
    'tag_filter_2': 1,
    'tag_url_2': 'tf2=1',
    'tag_value_2': 0,
    'value_url_2': 'tv2=0',
    'selected_tag': 0,
    'count': 5,
    'stacked_blobs': [
        [
            (0, '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19'),
            (0, 'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e'),
            (0, '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf'),
            (0, 'dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180'),
        ], [
            (0, '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8'),
            (0, ''),
            (0, ''),
            (0, ''),
        ],
    ],
    'count_disappeared': 1,
    'stacked_disappeared': [
        [
            (0, 'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e'),
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
            'tags': 'three, two',
            'has_duplicate': False,
            'album_duplicate': False,
            'has_percept': True,
            'imagefap': 'https://www.imagefap.com/photo/102/',
            'fap_id': 102,
            'duplicate_hints': ('Visual: Ben/ben-folder-20/\'name-202.png\' (2/20/202)\n'
                                'Visual: Ben/ben-folder-20/\'name-203.jpg\' (2/20/203)\n'
                                'Visual: Luke/luke-folder-10/\'name-100.jpg\' (1/10/100)\n'
                                'Visual: Luke/luke-folder-10/\'name-102.jpg\' (1/10/102)\n'
                                'Visual: Luke/luke-folder-10/\'name-104.jpg\' (1/10/104)\n'
                                'Visual: Luke/luke-folder-11/\'name-110.png\' (1/11/110)'),
            'date': '2023/Feb/02-20:12:50-UTC',
            'gone': [],
            'verdict': 'new',
        },
        '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8': {
            'name': 'name-200.gif',
            'sz': '434.54kb',
            'dimensions': '100x500 (WxH)',
            'tags': 'three/three-three, two/two-four/deep',
            'has_duplicate': False,
            'album_duplicate': False,
            'has_percept': False,
            'imagefap': 'https://www.imagefap.com/photo/200/',
            'fap_id': 200,
            'duplicate_hints': '',
            'date': '2023/Feb/02-17:59:30-UTC',
            'gone': [],
            'verdict': 'new',
        },
        '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {
            'name': 'name-111.jpg',
            'sz': '101b',
            'dimensions': '160x200 (WxH)',
            'tags': 'one/one-one, three/three-three, two',
            'has_duplicate': True,
            'album_duplicate': False,
            'has_percept': False,
            'imagefap': 'https://www.imagefap.com/photo/111/',
            'fap_id': 111,
            'duplicate_hints': ('Exact: Ben/ben-folder-20/\'name-201.jpg\' (2/20/201)\n'
                                'Exact: Luke/luke-folder-10/\'name-101.jpg\' (1/10/101)\n'
                                'Exact: Luke/luke-folder-11/\'name-111.jpg\' (1/11/111)'),
            'date': '2023/Feb/02-17:59:30-UTC',
            'gone': [],
            'verdict': 'keep',
        },
        'dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180': {
            'name': 'name-112.jpg',
            'sz': '87.12kb',
            'dimensions': '300x222 (WxH)',
            'tags': 'two/two-four/deep',
            'has_duplicate': False,
            'album_duplicate': False,
            'has_percept': False,
            'imagefap': 'https://www.imagefap.com/photo/112/',
            'fap_id': 112,
            'duplicate_hints': '',
            'date': '2023/Feb/02-17:59:30-UTC',
            'gone': [],
            'verdict': 'new',
        },
        'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e': {
            'name': 'name-103.gif',
            'sz': '434.54kb',
            'dimensions': '500x100 (WxH)',
            'tags': 'one, three/three-three, two/two-four',
            'has_duplicate': False,
            'album_duplicate': False,
            'has_percept': False,
            'imagefap': 'https://www.imagefap.com/photo/103/',
            'fap_id': 103,
            'duplicate_hints': '',
            'date': '2023/Feb/02-20:12:50-UTC',
            'gone': [
                (103, '2023/Feb/02-20:12:50-UTC', 'IMAGE_PAGE'),
            ],
            'verdict': 'new',
        },
    },
    'form_tags': _FAVORITE_CONTEXT_ALL_ON['form_tags'],
    'tag_id': 2,
    'page_depth': 1,
    'page_depth_up': 0,
    'tag_name': 'two (2)',
    'tag_simple_name': 'two',
    'warning_message': (
        'Tag three/three-three (33) deleted and association removed from 3 blobs (images)'),
    'error_message': None,
}

_TAG_LEAF_CONTEXT_RENAME: dict[str, Any] = {
    'tags': [
        (11, 'one-one', 'The One/one-one', 1),
    ],
    'show_duplicates': False,
    'dup_url': 'dup=0',
    'show_portraits': 1,
    'portrait_url': 'portrait=1',
    'show_landscapes': 1,
    'landscape_url': 'landscape=1',
    'locked_for_tagging': False,
    'tagging_url': 'lock=0',
    'tag_filter_1': 1,
    'tag_url_1': 'tf1=1',
    'tag_value_1': 0,
    'value_url_1': 'tv1=0',
    'tag_filter_2': 1,
    'tag_url_2': 'tf2=1',
    'tag_value_2': 0,
    'value_url_2': 'tv2=0',
    'selected_tag': 0,
    'count': 2,
    'stacked_blobs': [
        [
            (0, 'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e'),
            (0, '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf'),
            (0, ''),
            (0, ''),
        ],
    ],
    'count_disappeared': 1,
    'stacked_disappeared': [
        [
            (0, 'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e'),
            (0, ''),
            (0, ''),
            (0, ''),
        ],
    ],
    'blobs_data': {
        '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {
            'name': 'name-111.jpg',
            'sz': '101b',
            'dimensions': '160x200 (WxH)',
            'tags': 'one/one-one, three/three-three, two',
            'has_duplicate': True,
            'album_duplicate': False,
            'has_percept': False,
            'imagefap': 'https://www.imagefap.com/photo/111/',
            'fap_id': 111,
            'duplicate_hints': ('Exact: Ben/ben-folder-20/\'name-201.jpg\' (2/20/201)\n'
                                'Exact: Luke/luke-folder-10/\'name-101.jpg\' (1/10/101)\n'
                                'Exact: Luke/luke-folder-11/\'name-111.jpg\' (1/11/111)'),
            'date': '2023/Feb/02-17:59:30-UTC',
            'gone': [],
            'verdict': 'keep',
        },
        'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e': {
            'name': 'name-103.gif',
            'sz': '434.54kb',
            'dimensions': '500x100 (WxH)',
            'tags': 'one, three/three-three, two/two-four',
            'has_duplicate': False,
            'album_duplicate': False,
            'has_percept': False,
            'imagefap': 'https://www.imagefap.com/photo/103/',
            'fap_id': 103,
            'duplicate_hints': '',
            'date': '2023/Feb/02-20:12:50-UTC',
            'gone': [
                (103, '2023/Feb/02-20:12:50-UTC', 'IMAGE_PAGE'),
            ],
            'verdict': 'new',
        },
    },
    'form_tags': _FAVORITE_CONTEXT_ALL_ON['form_tags'],
    'tag_id': 1,
    'page_depth': 1,
    'page_depth_up': 0,
    'tag_name': 'The One (1)',
    'tag_simple_name': 'The One',
    'warning_message': 'Tag one (1) renamed to The One (1)',
    'error_message': None,
}

_TAG_LEAF_CLEAR_TAG: dict[str, Any] = {
    'tags': [
        (24, 'two-four', 'two/two-four', 1),
        (246, 'deep', 'two/two-four/deep', 2),
        (22, 'two-two', 'two/two-two', 1),
    ],
    'show_duplicates': True,
    'dup_url': 'dup=1',
    'show_portraits': 1,
    'portrait_url': 'portrait=1',
    'show_landscapes': 1,
    'landscape_url': 'landscape=1',
    'locked_for_tagging': True,
    'tagging_url': 'lock=1',
    'tag_filter_1': 1,
    'tag_url_1': 'tf1=1',
    'tag_value_1': 0,
    'value_url_1': 'tv1=0',
    'tag_filter_2': 1,
    'tag_url_2': 'tf2=1',
    'tag_value_2': 0,
    'value_url_2': 'tv2=0',
    'selected_tag': 0,
    'count': 4,
    'stacked_blobs': [
        [
            (0, 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'),
            (0, 'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e'),
            (0, '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf'),
            (0, 'dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180'),
        ],
    ],
    'count_disappeared': 2,
    'stacked_disappeared': [
        [
            (0, 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'),
            (0, 'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e'),
            (0, ''),
            (0, ''),
        ],
    ],
    'blobs_data': {
        '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {
            'name': 'name-111.jpg',
            'sz': '101b',
            'dimensions': '160x200 (WxH)',
            'tags': 'one/one-one, three/three-three, two',
            'has_duplicate': True,
            'album_duplicate': False,
            'has_percept': False,
            'imagefap': 'https://www.imagefap.com/photo/111/',
            'fap_id': 111,
            'duplicate_hints': ('Exact: Ben/ben-folder-20/\'name-201.jpg\' (2/20/201)\n'
                                'Exact: Luke/luke-folder-10/\'name-101.jpg\' (1/10/101)\n'
                                'Exact: Luke/luke-folder-11/\'name-111.jpg\' (1/11/111)'),
            'date': '2023/Feb/02-17:59:30-UTC',
            'gone': [],
            'verdict': 'keep',
        },
        'dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180': {
            'name': 'name-112.jpg',
            'sz': '87.12kb',
            'dimensions': '300x222 (WxH)',
            'tags': 'two/two-four/deep',
            'has_duplicate': False,
            'album_duplicate': False,
            'has_percept': False,
            'imagefap': 'https://www.imagefap.com/photo/112/',
            'fap_id': 112,
            'duplicate_hints': '',
            'date': '2023/Feb/02-17:59:30-UTC',
            'gone': [],
            'verdict': 'new',
        },
        'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': {
            'name': 'name-104.jpg',
            'sz': '55.26kb',
            'dimensions': '200x246 (WxH)',
            'tags': 'one, two',
            'has_duplicate': True,
            'album_duplicate': False,
            'has_percept': True,
            'imagefap': 'https://www.imagefap.com/photo/104/',
            'fap_id': 104,
            'duplicate_hints': ('Exact: Ben/ben-folder-20/\'name-203.jpg\' (2/20/203)\n'
                                'Exact: Luke/luke-folder-10/\'name-100.jpg\' (1/10/100)\n'
                                'Exact: Luke/luke-folder-10/\'name-104.jpg\' (1/10/104)\n'
                                'Visual: Ben/ben-folder-20/\'name-202.png\' (2/20/202)\n'
                                'Visual: Ben/ben-folder-20/\'name-203.jpg\' (2/20/203)\n'
                                'Visual: Luke/luke-folder-10/\'name-100.jpg\' (1/10/100)\n'
                                'Visual: Luke/luke-folder-10/\'name-102.jpg\' (1/10/102)\n'
                                'Visual: Luke/luke-folder-10/\'name-104.jpg\' (1/10/104)\n'
                                'Visual: Luke/luke-folder-11/\'name-110.png\' (1/11/110)'),
            'date': '2023/Feb/02-17:59:30-UTC',
            'gone': [
                (104, '2023/Feb/02-17:59:30-UTC', 'URL_EXTRACTION'),
            ],
            'verdict': 'new',
        },
        'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e': {
            'name': 'name-103.gif',
            'sz': '434.54kb',
            'dimensions': '500x100 (WxH)',
            'tags': 'one, three/three-three, two/two-four',
            'has_duplicate': False,
            'album_duplicate': False,
            'has_percept': False,
            'imagefap': 'https://www.imagefap.com/photo/103/',
            'fap_id': 103,
            'duplicate_hints': '',
            'date': '2023/Feb/02-20:12:50-UTC',
            'gone': [
                (103, '2023/Feb/02-20:12:50-UTC', 'IMAGE_PAGE'),
            ],
            'verdict': 'new',
        },
    },
    'form_tags': _FAVORITE_CONTEXT_ALL_ON['form_tags'],
    'tag_id': 2,
    'page_depth': 1,
    'page_depth_up': 0,
    'tag_name': 'two (2)',
    'tag_simple_name': 'two',
    'warning_message': '2 images had tag two (2) cleared',
    'error_message': None,
}

_TAG_NEW_TAGS: dict[str, set[int]] = {
    '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19': {2, 3},
    '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': set(),
    '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8': {246},
    '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {2, 11},
    'dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180': {246},
    'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': {1, 2},
    'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e': {1, 24},
}

_DUPLICATES_CONTEXT_RE_RUN: dict[str, Any] = {
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
    'identical': {
        '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': {
            'action': False,
            'name': '321e59af9d70af77&hellip;',  # cspell:disable-line
            'size': 2,
            'verdicts': 'S / K',
        },
        '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {
            'action': True,
            'name': '9b162a339a3a6f9a&hellip;',  # cspell:disable-line
            'size': 3,
            'verdicts': 'S / K / N',
        },
        'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': {
            'action': True,
            'name': 'e221b76f55946176&hellip;',  # cspell:disable-line
            'size': 3,
            'verdicts': 'S / N / S',
        },
    },
    'dup_action': 1,
    'dup_count': 2,
    'img_count': 5,
    'new_count': '1 (20.0%)',
    'false_count': '2 (40.0%)',
    'keep_count': '1 (20.0%)',
    'skip_count': '1 (20.0%)',
    'id_action': 2,
    'id_count': 3,
    'id_keep_count': '2 (25.0%)',
    'id_new_count': '2 (25.0%)',
    'id_skip_count': '4 (50.0%)',
    'configs': {
        'duplicates_sensitivity_animated': {
            'average': -1,
            'cnn': 0.98,
            'diff': 4,
            'percept': 3,
            'wavelet': -1,
        },
        'duplicates_sensitivity_regular': {
            'average': 3,
            'cnn': 0.93,
            'diff': 10,
            'percept': 10,
            'wavelet': 3,
        },
    },
    'warning_message': 'Duplicate operation run, and found 88 new duplicate images',
    'error_message': None,
}

_DUPLICATES_CONTEXT_DELETE_PENDING: dict[str, Any] = {
    'identical': {
        '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': {
            'action': False,
            'name': '321e59af9d70af77&hellip;',  # cspell:disable-line
            'size': 2,
            'verdicts': 'S / K',
        },
        '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {
            'action': True,
            'name': '9b162a339a3a6f9a&hellip;',  # cspell:disable-line
            'size': 3,
            'verdicts': 'S / K / N',
        },
        'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': {
            'action': True,
            'name': 'e221b76f55946176&hellip;',  # cspell:disable-line
            'size': 3,
            'verdicts': 'S / N / S',
        },
    },
    'duplicates': {
        ('321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
         'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'): {
            'name': '(321e59af9d70af77&hellip;, e221b76f55946176&hellip;)',  # cspell:disable-line
            'size': 2,
            'action': False,
            'verdicts': 'K / S',
        },
        ('5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8',
         'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e'): {
            'name': '(5b1d83a7317f2bb1&hellip;, ed1441656a734052&hellip;)',  # cspell:disable-line
            'size': 2,
            'action': False,
            'verdicts': 'F / F',
        },
    },
    'dup_action': 0,
    'dup_count': 2,
    'img_count': 4,
    'new_count': '0 (0.0%)',
    'false_count': '2 (50.0%)',
    'keep_count': '1 (25.0%)',
    'skip_count': '1 (25.0%)',
    'id_action': 2,
    'id_count': 3,
    'id_keep_count': '2 (25.0%)',
    'id_new_count': '2 (25.0%)',
    'id_skip_count': '4 (50.0%)',
    'configs': _DUPLICATES_CONTEXT_RE_RUN['configs'],
    'warning_message': 'Deleted 0 duplicate groups containing 1 duplicate images',
    'error_message': None,
}

_DUPLICATES_CONTEXT_DELETE_ALL: dict[str, Any] = {
    'identical': {
        '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': {
            'action': False,
            'name': '321e59af9d70af77&hellip;',  # cspell:disable-line
            'size': 2,
            'verdicts': 'S / K',
        },
        '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {
            'action': True,
            'name': '9b162a339a3a6f9a&hellip;',  # cspell:disable-line
            'size': 3,
            'verdicts': 'S / K / N',
        },
        'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': {
            'action': True,
            'name': 'e221b76f55946176&hellip;',  # cspell:disable-line
            'size': 3,
            'verdicts': 'S / N / S',
        },
    },
    'dup_action': 0,
    'dup_count': 0,
    'duplicates': {},
    'false_count': '-',
    'img_count': 0,
    'keep_count': '-',
    'new_count': '-',
    'skip_count': '-',
    'id_action': 2,
    'id_count': 3,
    'id_keep_count': '2 (25.0%)',
    'id_new_count': '2 (25.0%)',
    'id_skip_count': '4 (50.0%)',
    'configs': _DUPLICATES_CONTEXT_RE_RUN['configs'],
    'warning_message': 'Deleted 2 duplicate groups containing 5 duplicate images',
    'error_message': None,
}

_DUPLICATES_CONTEXT_EDIT_PARAMETERS: dict[str, Any] = {
    'identical': {
        '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': {
            'action': False,
            'name': '321e59af9d70af77&hellip;',  # cspell:disable-line
            'size': 2,
            'verdicts': 'S / K',
        },
        '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {
            'action': True,
            'name': '9b162a339a3a6f9a&hellip;',  # cspell:disable-line
            'size': 3,
            'verdicts': 'S / K / N',
        },
        'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': {
            'action': True,
            'name': 'e221b76f55946176&hellip;',  # cspell:disable-line
            'size': 3,
            'verdicts': 'S / N / S',
        },
    },
    'dup_action': 0,
    'dup_count': 0,
    'duplicates': {},
    'false_count': '-',
    'img_count': 0,
    'keep_count': '-',
    'new_count': '-',
    'skip_count': '-',
    'id_action': 2,
    'id_count': 3,
    'id_keep_count': '2 (25.0%)',
    'id_new_count': '2 (25.0%)',
    'id_skip_count': '4 (50.0%)',
    'configs': {
        'duplicates_sensitivity_animated': {
            'average': 0,
            'cnn': 0.99,
            'diff': 2,
            'percept': -1,
            'wavelet': -1,
        },
        'duplicates_sensitivity_regular': {
            'average': 1,
            'cnn': 0.91,
            'diff': 5,
            'percept': 7,
            'wavelet': -1,
        },
    },
    'warning_message': 'Updated duplicate search parameters',
    'error_message': None,
}

_DUPLICATE_BLOB_CONTEXT: dict[str, Any] = {
    'digest': '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
    'dup_key': '9b162a339a3a6f9a&hellip;',  # cspell:disable-line
    'current_index': -1,
    'current_identical': 1,
    'previous_key': None,
    'next_key': None,
    'has_any_identical': True,
    'next_identical': 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e',
    'previous_identical': '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
    'duplicates': {
        '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {
            'action': '',
            'sz': '101b',
            'dimensions': '160x200 (WxH)',
            'tags': 'one/one-one (11), three/three-three (33), two (2)',
            'percept': 'd99ee32e586716c8',
            'average': '091b5f7761323000',
            'diff': 'ffffbf88180060c8',
            'wavelet': '737394c5d3e66431',
            'has_identical': True,
            'loc': [
                {
                    'fap_id': 101,
                    'file_name': 'name-101.jpg',
                    'user_id': 1,
                    'user_name': 'Luke',
                    'folder_id': 10,
                    'folder_name': 'luke-folder-10',
                    'imagefap': 'https://www.imagefap.com/photo/101/',
                    'verdict': 'skip',
                }, {
                    'fap_id': 111,
                    'file_name': 'name-111.jpg',
                    'user_id': 1,
                    'user_name': 'Luke',
                    'folder_id': 11,
                    'folder_name': 'luke-folder-11',
                    'imagefap': 'https://www.imagefap.com/photo/111/',
                    'verdict': 'keep',
                }, {
                    'fap_id': 201,
                    'file_name': 'name-201.jpg',
                    'user_id': 2,
                    'user_name': 'Ben',
                    'folder_id': 20,
                    'folder_name': 'ben-folder-20',
                    'imagefap': 'https://www.imagefap.com/photo/201/',
                    'verdict': 'new',
                },
            ],
        },
    },
    'sources': [],
    'error_message': None,
    'warning_message': None,
}

_DUPLICATE_SET_CONTEXT: dict[str, Any] = {
    'digest': 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e',
    'dup_key': ('(0aaef1becbd966a2&hellip;, 321e59af9d70af77&hellip;, '  # cspell:disable-line
                'e221b76f55946176&hellip;)'),                            # cspell:disable-line
    'current_index': 0,
    'previous_key': None,
    'next_key': ('5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8',
                 'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e'),
    'previous_identical': None,
    'has_any_identical': True,
    'current_identical': -1,
    'next_identical': None,
    'duplicates': {
        '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19': {
            'action': 'false',
            'sz': '53.36kb',
            'dimensions': '198x200 (WxH)',
            'tags': 'three (3), two (2)',
            'percept': 'cd4fc618316732e7',
            'average': '303830301a1c387f',
            'diff': '60e2c3c2d2b1e2ce',
            'wavelet': '303838383a1f3e7f',
            'has_identical': False,
            'loc': [
                {
                    'fap_id': 102,
                    'file_name': 'name-102.jpg',
                    'user_id': 1,
                    'user_name': 'Luke',
                    'folder_id': 10,
                    'folder_name': 'luke-folder-10',
                    'imagefap': 'https://www.imagefap.com/photo/102/',
                    'verdict': 'new',
                },
            ],
        },
        '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': {
            'action': 'skip',
            'sz': '44.25kb',
            'dimensions': '130x173 (WxH)',
            'tags': '',
            'percept': 'd99ee32e586716c8',
            'average': 'ffffff9a180060c8',
            'diff': '6854541633d5c991',
            'wavelet': 'ffffbf88180060c8',
            'has_identical': True,
            'loc': [
                {
                    'fap_id': 110,
                    'file_name': 'name-110.png',
                    'user_id': 1,
                    'user_name': 'Luke',
                    'folder_id': 11,
                    'folder_name': 'luke-folder-11',
                    'imagefap': 'https://www.imagefap.com/photo/110/',
                    'verdict': 'skip',
                }, {
                    'fap_id': 202,
                    'file_name': 'name-202.png',
                    'user_id': 2,
                    'user_name': 'Ben',
                    'folder_id': 20,
                    'folder_name': 'ben-folder-20',
                    'imagefap': 'https://www.imagefap.com/photo/202/',
                    'verdict': 'skip',
                },
            ],
        },
        'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': {
            'action': 'keep',
            'sz': '55.26kb',
            'dimensions': '200x246 (WxH)',
            'tags': 'one (1), two (2)',
            'percept': 'cc8fc37638703ee1',
            'average': '3838381810307078',
            'diff': '626176372565c3f2',
            'wavelet': '3e3f3f1b10307878',
            'has_identical': True,
            'loc': [
                {
                    'fap_id': 100,
                    'file_name': 'name-100.jpg',
                    'user_id': 1,
                    'user_name': 'Luke',
                    'folder_id': 10,
                    'folder_name': 'luke-folder-10',
                    'imagefap': 'https://www.imagefap.com/photo/100/',
                    'verdict': 'keep',
                }, {
                    'fap_id': 104,
                    'file_name': 'name-104.jpg',
                    'user_id': 1,
                    'user_name': 'Luke',
                    'folder_id': 10,
                    'folder_name': 'luke-folder-10',
                    'imagefap': 'https://www.imagefap.com/photo/104/',
                    'verdict': 'skip',
                }, {
                    'fap_id': 203,
                    'file_name': 'name-203.jpg',
                    'user_id': 2,
                    'user_name': 'Ben',
                    'folder_id': 20,
                    'folder_name': 'ben-folder-20',
                    'imagefap': 'https://www.imagefap.com/photo/203/',
                    'verdict': 'skip',
                },
            ],
        },
    },
    'sources': [
        {
            'name': 'AVERAGE',
            'scores': [
                {
                    'key1': '321e59af9d70af77&hellip;',  # cspell:disable-line
                    'key2': 'e221b76f55946176&hellip;',  # cspell:disable-line
                    'value': '2',
                    'normalized_value': '3.3',
                    'sha1': '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
                    'sha2': 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e',
                },
            ],
        }, {
            'name': 'CNN',
            'scores': [
                {
                    'key1': '0aaef1becbd966a2&hellip;',  # cspell:disable-line
                    'key2': '321e59af9d70af77&hellip;',  # cspell:disable-line
                    'value': '0.960',
                    'normalized_value': '4.3',
                    'sha1': '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19',
                    'sha2': '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
                }, {
                    'key1': '0aaef1becbd966a2&hellip;',  # cspell:disable-line
                    'key2': 'e221b76f55946176&hellip;',  # cspell:disable-line
                    'value': '0.950',
                    'normalized_value': '2.9',
                    'sha1': '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19',
                    'sha2': 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e',
                }, {
                    'key1': '321e59af9d70af77&hellip;',  # cspell:disable-line
                    'key2': 'e221b76f55946176&hellip;',  # cspell:disable-line
                    'value': '0.980',
                    'normalized_value': '7.1',
                    'sha1': '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
                    'sha2': 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e',
                },
            ],
        }, {
            'name': 'DIFF',
            'scores': [
                {
                    'key1': '0aaef1becbd966a2&hellip;',  # cspell:disable-line
                    'key2': '321e59af9d70af77&hellip;',  # cspell:disable-line
                    'value': '9',
                    'normalized_value': '1.0',
                    'sha1': '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19',
                    'sha2': '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
                },
            ],
        }, {
            'name': 'PERCEPT',
            'scores': [
                {
                    'key1': '0aaef1becbd966a2&hellip;',  # cspell:disable-line
                    'key2': 'e221b76f55946176&hellip;',  # cspell:disable-line
                    'value': '0',
                    'normalized_value': '10.0',
                    'sha1': '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19',
                    'sha2': 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e',
                }, {
                    'key1': '321e59af9d70af77&hellip;',  # cspell:disable-line
                    'key2': 'e221b76f55946176&hellip;',  # cspell:disable-line
                    'value': '10',
                    'normalized_value': '0.0',
                    'sha1': '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
                    'sha2': 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e',
                },
            ],
        }, {
            'name': 'WAVELET',
            'scores': [
                {
                    'key1': '0aaef1becbd966a2&hellip;',  # cspell:disable-line
                    'key2': 'e221b76f55946176&hellip;',  # cspell:disable-line
                    'value': '1',
                    'normalized_value': '6.7',
                    'sha1': '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19',
                    'sha2': 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e',
                },
            ],
        },
    ],
    'error_message': None,
    'warning_message': ('Key \'321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6\' '
                        'in POST data is marked "skip" so we corrected all child identical '
                        'selections to "skip" '
                        '(was {(1, 11, 110): \'skip\', (2, 20, 202): \'keep\'})'),
}

_DUPLICATE_IDENTICAL_SET = {
    'current_identical': 1,
    'current_index': -1,
    'digest': '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
    'dup_key': '9b162a339a3a6f9a&hellip;',  # cspell:disable-line
    'has_any_identical': True,
    'next_identical': 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e',
    'next_key': None,
    'previous_identical': '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
    'previous_key': None,
    'sources': [],
    'duplicates': {
        '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {
            'action': '',
            'average': '091b5f7761323000',
            'diff': 'ffffbf88180060c8',
            'dimensions': '160x200 (WxH)',
            'has_identical': True,
            'percept': 'd99ee32e586716c8',
            'sz': '101b',
            'tags': 'one/one-one (11), three/three-three (33), two (2)',
            'wavelet': '737394c5d3e66431',
            'loc': [
                {
                    'fap_id': 101,
                    'file_name': 'name-101.jpg',
                    'folder_id': 10,
                    'folder_name': 'luke-folder-10',
                    'imagefap': 'https://www.imagefap.com/photo/101/',
                    'user_id': 1,
                    'user_name': 'Luke',
                    'verdict': 'skip',
                }, {
                    'fap_id': 111,
                    'file_name': 'name-111.jpg',
                    'folder_id': 11,
                    'folder_name': 'luke-folder-11',
                    'imagefap': 'https://www.imagefap.com/photo/111/',
                    'user_id': 1,
                    'user_name': 'Luke',
                    'verdict': 'keep',
                }, {
                    'fap_id': 201,
                    'file_name': 'name-201.jpg',
                    'folder_id': 20,
                    'folder_name': 'ben-folder-20',
                    'imagefap': 'https://www.imagefap.com/photo/201/',
                    'user_id': 2,
                    'user_name': 'Ben',
                    'verdict': 'skip',
                },
            ],
        },
    },
    'error_message': None,
    'warning_message': None,
}


SUITE = unittest.TestLoader().loadTestsFromTestCase(TestDjangoViews)


if __name__ == '__main__':
  unittest.main()
