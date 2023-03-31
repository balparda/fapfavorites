#!/usr/bin/python3 -bb
#
# Copyright 2023 Daniel Balparda (balparda@gmail.com)
#
# cspell:disable-next-line
# Image testdata/109.gif authored by Charly Whisky, creative commons attribution.
# (Found in https://en.wikipedia.org/wiki/File:Dopplerfrequenz.gif)
#
# pylint: disable=invalid-name,protected-access
"""fapdata.py unittest."""

import hashlib
import os
import os.path
# import pdb
import tempfile
from typing import Union
import unittest
from unittest import mock

import numpy as np

from fapfavorites import fapdata

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


_TESTDATA_PATH = os.path.join(os.path.dirname(__file__), 'testdata/')


class TestFapDatabase(unittest.TestCase):
  """Tests for fapdata.py."""

  @mock.patch('fapfavorites.fapdata.base.INT_TIME')
  def test_Error404(self, mock_time: mock.MagicMock):
    """Test."""
    mock_time.return_value = 1675368670  # 02/feb/2023 20:11:10
    err = fapdata.Error404('foo-url')
    self.assertTupleEqual(err.FailureTuple(), (0, 1675368670, None, 'foo-url'))
    self.assertEqual(str(err), 'Error404(ID: 0, @2023/Feb/02-20:11:10-UTC, \'-\', \'foo-url\')')
    err.image_id = 999
    err.image_name = 'foo-name'
    self.assertTupleEqual(err.FailureTuple(), (999, 1675368670, 'foo-name', 'foo-url'))
    self.assertEqual(
        str(err), 'Error404(ID: 999, @2023/Feb/02-20:11:10-UTC, \'foo-name\', \'foo-url\')')

  @mock.patch('fapfavorites.fapdata.os.path.isdir')
  @mock.patch('fapfavorites.fapdata.os.mkdir')
  def test_Constructor(self, mock_mkdir: mock.MagicMock, mock_is_dir: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_is_dir.return_value = False
    del os.environ['IMAGEFAP_FAVORITES_DB_PATH']
    os.environ['IMAGEFAP_FAVORITES_DB_KEY'] = 'some crypto key'
    db = fapdata.FapDatabase('~/Downloads/some-dir/')
    mock_mkdir.assert_called_once_with(os.path.expanduser('~/Downloads/some-dir/'))
    self.assertEqual(db._original_dir, '~/Downloads/some-dir/')
    self.assertEqual(os.environ['IMAGEFAP_FAVORITES_DB_PATH'], '~/Downloads/some-dir/')
    self.assertEqual(db._db_dir, os.path.expanduser('~/Downloads/some-dir/'))
    self.assertEqual(db._db_path, os.path.expanduser('~/Downloads/some-dir/imagefap.database'))
    self.assertEqual(db._blobs_dir, os.path.expanduser('~/Downloads/some-dir/blobs/'))
    self.assertEqual(db._key, b'some crypto key')
    self.assertTrue(all(k in db._db for k in fapdata._DB_MAIN_KEYS))
    self.assertDictEqual(db.duplicates.registry, {})
    db.users[1] = {'name': 'Luke'}   # type: ignore
    db.favorites[1] = {2: {}}        # type: ignore
    db.tags[3] = {'name': 'three', 'tags': {}}
    db.blobs['sha1'] = {'tags': {4}}  # type: ignore
    db.image_ids_index[5] = 'sha2'
    db._duplicates_registry[('a', 'b')] = {'sources': {}, 'verdicts': {'a': 'new'}}
    db._duplicates_key_index['a'] = ('a', 'b')
    db._duplicates_key_index['b'] = ('a', 'b')
    self.assertDictEqual(db._db, {
        'configs': {
            'duplicates_sensitivity_regular': fapdata.duplicates.METHOD_SENSITIVITY_DEFAULTS,
            'duplicates_sensitivity_animated': fapdata.duplicates.ANIMATED_SENSITIVITY_DEFAULTS,
        },
        'users': {1: {'name': 'Luke'}},
        'favorites': {1: {2: {}}},
        'tags': {3: {'name': 'three', 'tags': {}}},
        'blobs': {'sha1': {'tags': {4}}},
        'image_ids_index': {5: 'sha2'},
        'duplicates_registry': {('a', 'b'): {'sources': {}, 'verdicts': {'a': 'new'}}},
        'duplicates_key_index': {'a': ('a', 'b'), 'b': ('a', 'b')}
    })
    self.assertDictEqual(
        db.duplicates.registry, {('a', 'b'): {'sources': {}, 'verdicts': {'a': 'new'}}})
    self.assertDictEqual(db.duplicates.index, {'a': ('a', 'b'), 'b': ('a', 'b')})
    # cleanup environ so they don't interfere in other tests
    del os.environ['IMAGEFAP_FAVORITES_DB_PATH']
    del os.environ['IMAGEFAP_FAVORITES_DB_KEY']

  @mock.patch('fapfavorites.fapdata.os.path.isdir')
  def test_Constructor_Fail(self, mock_is_dir: mock.MagicMock) -> None:
    """Test."""
    mock_is_dir.return_value = False
    with self.assertRaises(fapdata.Error):
      fapdata.FapDatabase('/yyy/', create_if_needed=False)
    with self.assertRaises(AttributeError):
      fapdata.FapDatabase('')

  @mock.patch('fapfavorites.fapdata.base.INT_TIME')
  @mock.patch('fapfavorites.fapdata.getpass.getpass')
  def test_CreationCrypto(self, mock_getpass: mock.MagicMock, mock_time: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_time.return_value = 1675368670  # 02/feb/2023 20:11:10
    mock_getpass.side_effect = ['p1', 'p1-err', '', '', 'p2', 'p2', 'p2-wrong', 'p2']
    # test password mismatch and empty password
    with tempfile.TemporaryDirectory() as db_path:
      db = fapdata.FapDatabase(db_path)
      with self.assertRaisesRegex(fapdata.Error, r'Password mismatch'):
        db.Load()
      db.Load()
      self.assertIsNone(db._key)
      self.assertNotIn('IMAGEFAP_FAVORITES_DB_KEY', os.environ)
      db.Save()
      db.Load()
    del os.environ['IMAGEFAP_FAVORITES_DB_PATH']
    # test crypto
    with tempfile.TemporaryDirectory() as db_path:
      db = fapdata.FapDatabase(db_path)
      db.Load()
      self.assertEqual(db._key, b'WZcaSuzuHIacpB42jX0eyavf5j1LUmfpBbu6ZDYWv0s=')
      self.assertEqual(
          os.environ['IMAGEFAP_FAVORITES_DB_KEY'], db._key.decode('utf-8'))  # type: ignore
      db.Save()
      db.Load()
      del db
      del os.environ['IMAGEFAP_FAVORITES_DB_PATH']
      del os.environ['IMAGEFAP_FAVORITES_DB_KEY']
      db = fapdata.FapDatabase(db_path)
      with self.assertRaises(fapdata.base.bin_fernet.InvalidToken):
        db.Load()
      del db
      db = fapdata.FapDatabase(db_path)
      db.Load()
      self.assertEqual(db._key, b'WZcaSuzuHIacpB42jX0eyavf5j1LUmfpBbu6ZDYWv0s=')
      self.assertEqual(
          os.environ['IMAGEFAP_FAVORITES_DB_KEY'], db._key.decode('utf-8'))  # type: ignore
    self.assertListEqual(
        mock_getpass.call_args_list,
        [mock.call(prompt='NEW Database Password (`Enter` key for no encryption): '),
         mock.call(prompt='CONFIRM Database Password (`Enter` key for no encryption): '),
         mock.call(prompt='NEW Database Password (`Enter` key for no encryption): '),
         mock.call(prompt='CONFIRM Database Password (`Enter` key for no encryption): '),
         mock.call(prompt='NEW Database Password (`Enter` key for no encryption): '),
         mock.call(prompt='CONFIRM Database Password (`Enter` key for no encryption): '),
         mock.call(prompt='Database Password: '),
         mock.call(prompt='Database Password: ')])
    # cleanup environ so they don't interfere in other tests
    del os.environ['IMAGEFAP_FAVORITES_DB_PATH']
    del os.environ['IMAGEFAP_FAVORITES_DB_KEY']

  @mock.patch('fapfavorites.fapdata.os.path.isdir')
  def test_GetTag(self, mock_is_dir: mock.MagicMock) -> None:
    """Test."""
    mock_is_dir.return_value = True
    db = fapdata.FapDatabase('/xxx/')
    db._db['tags'] = _TEST_TAGS_1
    self.assertListEqual(db.GetTag(10), [(10, 'plain', {'name': 'plain'})])
    self.assertListEqual(db.GetTag(2), [(2, 'two', _TEST_TAGS_1[2])])
    self.assertEqual(db.TagLineageStr(2), 'two (2)')
    self.assertListEqual(
        db.GetTag(22),
        [(2, 'two', _TEST_TAGS_1[2]), (22, 'two-two', {'name': 'two-two', 'tags': {}})])
    self.assertListEqual(
        db.GetTag(24),
        [(2, 'two', _TEST_TAGS_1[2]),
         (24, 'two-four', {'name': 'two-four', 'tags': {246: {'name': 'deep'}}})])
    self.assertEqual(db.TagStr(24), 'two-four (24)')
    self.assertEqual(db.TagStr(24, add_id=False), 'two-four')
    self.assertEqual(db.TagLineageStr(24), 'two/two-four (24)')
    self.assertEqual(db.TagLineageStr(24, add_id=False), 'two/two-four')
    self.assertListEqual(
        db.GetTag(246),
        [(2, 'two', _TEST_TAGS_1[2]),
         (24, 'two-four', {'name': 'two-four', 'tags': {246: {'name': 'deep'}}}),
         (246, 'deep', {'name': 'deep'})])
    self.assertEqual(db.TagStr(246), 'deep (246)')
    self.assertEqual(db.TagLineageStr(246), 'two/two-four/deep (246)')
    with self.assertRaisesRegex(fapdata.Error, r'tag 11 is empty'):
      db.GetTag(11)
    with self.assertRaisesRegex(fapdata.Error, r'tag 3 \(of 33\) is empty'):
      db.GetTag(33)

  @mock.patch('fapfavorites.fapdata.os.path.isdir')
  def test_TagsWalk(self, mock_is_dir: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_is_dir.return_value = True
    db = fapdata.FapDatabase('/xxx/')
    self.assertListEqual(db.PrintTags(actually_print=False), ['NO TAGS CREATED'])
    db._db['tags'] = _TEST_TAGS_2
    self.assertListEqual(
        list((i, n, d) for i, n, d, _ in db.TagsWalk()),
        [
            (1, 'one', 0), (11, 'one-one', 1),
            (10, 'plain', 0),
            (3, 'three', 0), (33, 'three-three', 1),
            (2, 'two', 0), (24, 'two-four', 1), (246, 'deep', 2), (22, 'two-two', 1),
        ])
    self.assertListEqual(
        list((i, n, d) for i, n, d, _ in db.TagsWalk(
            start_tag=_TEST_TAGS_2[2]['tags'])),  # type: ignore
        [(24, 'two-four', 0), (246, 'deep', 1), (22, 'two-two', 0)])
    db._db['blobs'] = {  # type: ignore
        'a': {'tags': {1, 2, 33}, 'sz': 10}, 'b': {'tags': {246, 33}, 'sz': 55}}
    self.assertListEqual(db.PrintTags(), _PRINTED_TAGS)

  @mock.patch('fapfavorites.fapdata.os.path.isdir')
  def test_Tags_Add_Rename_Delete(self, mock_is_dir: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    # setup mock database
    mock_is_dir.return_value = True
    db = fapdata.FapDatabase('/xxx/')
    db._db['tags'] = _TEST_TAGS_2
    db._db['blobs'] = {  # type: ignore
        'a': {'tags': {1, 2, 3, 33}, 'sz': 10}, 'b': {'tags': {246, 33}, 'sz': 55}}
    # test a bunch of invalid operations
    with self.assertRaisesRegex(fapdata.Error, r'not found'):
      db.AddTag(4, 'foo')  # invalid parent
    with self.assertRaisesRegex(fapdata.Error, r'Don\'t use'):
      db.AddTag(1, 'fo/o')  # name with invalid chars
    with self.assertRaisesRegex(fapdata.Error, r'clashes with'):
      db.AddTag(1, 'Two')  # name clash
    with self.assertRaisesRegex(fapdata.Error, r'not found'):
      db.RenameTag(4, 'foo')  # invalid tag
    with self.assertRaisesRegex(fapdata.Error, r'Don\'t use'):
      db.RenameTag(1, 'fo/o')  # name with invalid chars
    with self.assertRaisesRegex(fapdata.Error, r'clashes with'):
      db.RenameTag(1, 'Two')  # name clash
    with self.assertRaisesRegex(fapdata.Error, r'not found'):
      db.DeleteTag(4)  # invalid tag
    with self.assertRaisesRegex(fapdata.Error, r'is not empty'):
      db.DeleteTag(3)  # tag not empty (has children)
    with self.assertRaisesRegex(fapdata.Error, r'cannot be empty'):
      db.DeleteTag(0)  # tries to delete root
    # adds a few tags
    self.assertEqual(db.AddTag(0, 'four'), 4)
    self.assertEqual(db.AddTag(24, 'Foo'), 5)
    self.assertEqual(db.AddTag(246, 'Bar'), 6)
    # renames a few tags
    db.RenameTag(1, 'TheOne')
    db.RenameTag(2, 'Second')
    db.RenameTag(246, 'The Deep One')
    # deletes a few tags
    self.assertSetEqual(db.DeleteTag(33), {'a', 'b'})
    self.assertSetEqual(db.DeleteTag(3), {'a'})
    self.assertSetEqual(db.DeleteTag(11), set())
    # check our DB
    self.assertDictEqual(db.tags, _TEST_TAGS_3)
    self.assertDictEqual(
        db.blobs, {'a': {'tags': {1, 2}, 'sz': 10}, 'b': {'tags': {246}, 'sz': 55}})

  @mock.patch('fapfavorites.fapdata.urllib.request.urlopen')
  @mock.patch('fapfavorites.fapdata.time.sleep')
  def test_LimpingURLRead(self, unused_time: mock.MagicMock, mock_url: mock.MagicMock) -> None:
    """Test."""
    # test args error
    with self.assertRaises(AttributeError):
      fapdata._LimpingURLRead('no.url', min_wait=1.0, max_wait=0.5)
    # test direct success

    class _MockResponse1:

      def read(self):
        """Read."""
        return b'foo.response'

    mock_url.return_value = _MockResponse1()
    self.assertEqual(fapdata._LimpingURLRead('foo.url'), b'foo.response')
    mock_url.assert_called_once_with('foo.url', timeout=fapdata._URL_TIMEOUT)
    mock_url.reset_mock(side_effect=True)  # reset calls and side_effect
    # test exceptions and retry

    class _MockResponse2:

      def read(self):
        """Read."""
        raise fapdata.socket.timeout('timeout in page')

    fapdata._MAX_RETRY = 2
    mock_url.return_value = _MockResponse2()
    with self.assertRaises(fapdata.Error):
      fapdata._LimpingURLRead('bar.url')
    self.assertListEqual(
        mock_url.call_args_list,
        [mock.call('bar.url', timeout=15.0),   # 1st try
         mock.call('bar.url', timeout=15.0),   # retry 1
         mock.call('bar.url', timeout=15.0)])  # retry 2

  @mock.patch('fapfavorites.fapdata.os.path.isdir')
  @mock.patch('fapfavorites.fapdata._FapHTMLRead')
  def test_AddUserByID(self, mock_read: mock.MagicMock, mock_is_dir: mock.MagicMock) -> None:
    """Test."""
    mock_is_dir.return_value = True
    fapdata._FIND_NAME_IN_FAVORITES = _MockRegex({'user_html': ['foo &amp; user'], 'invalid': []})
    db = fapdata.FapDatabase('/xxx/')
    mock_read.return_value = 'invalid'
    with self.assertRaisesRegex(fapdata.Error, r'for 11'):
      db.AddUserByID(11)
    mock_read.return_value = 'user_html'
    self.assertEqual(db.AddUserByID(10), 'foo & user')
    self.assertDictEqual(
        db.users,
        {10: {'date_albums': 0, 'date_finished': 0, 'date_audit': 0, 'name': 'foo & user'}})
    fapdata._FIND_NAME_IN_FAVORITES = None  # make sure is not used again in next call
    self.assertEqual(db.AddUserByID(10), 'foo & user')
    self.assertEqual(db.UserStr(10), 'foo & user (10)')
    with self.assertRaises(fapdata.Error):
      db.UserStr(5)
    self.assertListEqual(
        mock_read.call_args_list,
        [mock.call('https://www.imagefap.com/showfavorites.php?userid=11&page=0'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=0')])

  @mock.patch('fapfavorites.fapdata.os.path.isdir')
  @mock.patch('fapfavorites.fapdata._FapHTMLRead')
  def test_AddUserByName(self, mock_read: mock.MagicMock, mock_is_dir: mock.MagicMock) -> None:
    """Test."""
    mock_is_dir.return_value = True
    fapdata._FIND_USER_ID_RE = _MockRegex({'user_html': ['10'], 'invalid': []})
    fapdata._FIND_ACTUAL_NAME = _MockRegex({'user_html': ['foo &amp; user'], 'invalid': []})
    db = fapdata.FapDatabase('/xxx/')
    mock_read.return_value = 'invalid'
    with self.assertRaisesRegex(fapdata.Error, r'ID for user \'no-user\''):
      db.AddUserByName('no-user')
    fapdata._FIND_USER_ID_RE = _MockRegex({'user_html': ['10'], 'invalid': ['12']})
    with self.assertRaisesRegex(fapdata.Error, r'display name for user \'no-user\''):
      db.AddUserByName('no-user')
    mock_read.return_value = 'user_html'
    self.assertTupleEqual(db.AddUserByName('foo-user'), (10, 'foo & user'))
    self.assertDictEqual(
        db.users,
        {10: {'date_albums': 0, 'date_finished': 0, 'date_audit': 0, 'name': 'foo & user'}})
    fapdata._FIND_USER_ID_RE = None  # make sure is not used again in next call
    fapdata._FIND_ACTUAL_NAME = None
    self.assertTupleEqual(db.AddUserByName('foo & user'), (10, 'foo & user'))
    self.assertEqual(db.UserStr(10), 'foo & user (10)')
    with self.assertRaises(fapdata.Error):
      db.UserStr(5)
    self.assertListEqual(
        mock_read.call_args_list,
        [mock.call('https://www.imagefap.com/profile/no-user'),
         mock.call('https://www.imagefap.com/profile/no-user'),
         mock.call('https://www.imagefap.com/profile/foo-user')])

  @mock.patch('fapfavorites.fapdata.os.path.isdir')
  @mock.patch('fapfavorites.fapdata._FapHTMLRead')
  def test_AddFolderByID(self, mock_read: mock.MagicMock, mock_is_dir: mock.MagicMock) -> None:
    """Test."""
    mock_is_dir.return_value = True
    fapdata._FIND_NAME_IN_FOLDER = _MockRegex({'folder_html': ['foo &amp; folder'], 'invalid': []})
    fapdata._FIND_ONLY_IN_PICTURE_FOLDER = _MockRegex({'folder_html': ['true']})
    fapdata._FIND_ONLY_IN_GALLERIES_FOLDER = _MockRegex({'folder_html': []})
    db = fapdata.FapDatabase('/xxx/')
    db.users[10] = {'name': 'username'}  # type: ignore
    mock_read.return_value = 'invalid'
    with self.assertRaisesRegex(fapdata.Error, r'for 11/22'):
      db.AddFolderByID(11, 22)
    mock_read.return_value = 'folder_html'
    self.assertEqual(db.AddFolderByID(10, 20), 'foo & folder')
    self.assertDictEqual(
        db.favorites,
        {10: {20: {'date_blobs': 0, 'date_straight': 0, 'images': [], 'failed_images': set(),
                   'name': 'foo & folder', 'pages': 0}}})
    fapdata._FIND_NAME_IN_FOLDER = None  # make sure is not used again in next call
    fapdata._FIND_ONLY_IN_PICTURE_FOLDER = None
    fapdata._FIND_ONLY_IN_GALLERIES_FOLDER = None
    self.assertEqual(db.AddFolderByID(10, 20), 'foo & folder')
    self.assertEqual(db.AlbumStr(10, 20), 'username/foo & folder (10/20)')
    with self.assertRaises(fapdata.Error):
      db.AlbumStr(10, 99)
    self.assertListEqual(
        mock_read.call_args_list,
        [mock.call('https://www.imagefap.com/showfavorites.php?userid=11&page=0&folderid=22'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=0&folderid=20'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=0&folderid=20')])

  @mock.patch('fapfavorites.fapdata.os.path.isdir')
  @mock.patch('fapfavorites.fapdata._FapHTMLRead')
  def test_AddFolderByName(self, mock_read: mock.MagicMock, mock_is_dir: mock.MagicMock) -> None:
    """Test."""
    mock_is_dir.return_value = True
    fapdata._FIND_FOLDERS = _MockRegex({
        'folder_html_1': [('100', 'no1')], 'folder_html_2': [('200', 'no2'), ('300', 'no3')],
        'folder_html_3': [('400', 'foo &amp; folder'), ('500', 'no5')], 'invalid': []})
    fapdata._FIND_ONLY_IN_PICTURE_FOLDER = _MockRegex({'folder_html_test': ['true']})
    fapdata._FIND_ONLY_IN_GALLERIES_FOLDER = _MockRegex({'folder_html_test': []})
    db = fapdata.FapDatabase('/xxx/')
    db.users[10] = {'name': 'username'}  # type: ignore
    mock_read.return_value = 'invalid'
    with self.assertRaisesRegex(fapdata.Error, r'folder \'no-folder\' for user 11'):
      db.AddFolderByName(11, 'no-folder')
    mock_read.side_effect = ['folder_html_1', 'folder_html_2', 'folder_html_3', 'folder_html_test']
    self.assertTupleEqual(db.AddFolderByName(10, 'foo & folder'), (400, 'foo & folder'))
    self.assertDictEqual(
        db.favorites,
        {10: {400: {'date_blobs': 0, 'date_straight': 0, 'images': [], 'failed_images': set(),
                    'name': 'foo & folder', 'pages': 0}}})
    fapdata._FIND_NAME_IN_FOLDER = None  # make sure is not used again in next call
    fapdata._FIND_ONLY_IN_PICTURE_FOLDER = None
    fapdata._FIND_ONLY_IN_GALLERIES_FOLDER = None
    self.assertTupleEqual(db.AddFolderByName(10, 'foo & folder'), (400, 'foo & folder'))
    self.assertEqual(db.AlbumStr(10, 400), 'username/foo & folder (10/400)')
    with self.assertRaises(fapdata.Error):
      db.AlbumStr(10, 99)
    self.assertListEqual(
        mock_read.call_args_list,
        [mock.call('https://www.imagefap.com/showfavorites.php?userid=11&page=0'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=0'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=1'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=2'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=0&folderid=400')])

  @mock.patch('fapfavorites.fapdata._FapHTMLRead')
  @mock.patch('fapfavorites.fapdata._FapBinRead')
  @mock.patch('fapfavorites.fapdata.requests.get')
  @mock.patch('fapfavorites.fapdata.base.INT_TIME')
  def test_Read(  # noqa: C901
      self, mock_time: mock.MagicMock, mock_get: mock.MagicMock,
      read_bin: mock.MagicMock, read_html: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_time.return_value = 1675368670  # 02/feb/2023 20:11:10
    with tempfile.TemporaryDirectory() as db_path:
      # do the dance that does not depend on any mocking at all
      with self.assertRaises(fapdata.Error):
        fapdata.GetDatabaseTimestamp(db_path)
      db = fapdata.FapDatabase(db_path)
      db._db['users'] = {
          1: {'name': 'Luke', 'date_albums': 1675360670,
              'date_finished': 1675369670, 'date_audit': 1675369880},
          2: {'name': 'Ben', 'date_albums': 0, 'date_finished': 0, 'date_audit': 0}}
      db._db['favorites'] = {1: {11: {
          'name': 'known-folder-1', 'pages': 8, 'date_straight': 0, 'date_blobs': 1675360670,
          'images': [103, 104], 'failed_images': {(123, 1675360070, 'failed.jpg', 'f-url')}}}}
      db.Save()
      self.assertTrue(fapdata.GetDatabaseTimestamp(db_path) > 1600000000)
      del db
      db = fapdata.FapDatabase(db_path)
      db.Load()
      _PRINTED_STATS_EMPTY[0] = _PRINTED_STATS_EMPTY[0] % db_path  # type: ignore
      self.assertListEqual(db.PrintStats(), _PRINTED_STATS_EMPTY)
      self.assertListEqual(db.PrintUsersAndFavorites(), _PRINTED_USERS_EMPTY)
      self.assertListEqual(db.PrintBlobs(), _PRINTED_BLOBS_EMPTY)
      # AddAllUserFolders ##########################################################################
      read_html.side_effect = [
          'folders-page-1', 'test-new-f-0', 'test-new-f-2',  # page, then looks viability for new
          'folders-page-2', 'test-new-f-3', 'test-new-f-4',
          'folders-page-3']
      fapdata._FIND_FOLDERS = _MockRegex({
          'folders-page-1': [('10', 'new-f-0'), ('11', 'known-folder-1'), ('12', 'new-f-2')],
          'folders-page-2': [('13', 'new&amp;f-3'), ('14', 'new-f-4')],
          'folders-page-3': []})
      fapdata._FIND_ONLY_IN_PICTURE_FOLDER = _MockRegex({
          'test-new-f-0': ['true'], 'test-new-f-2': [],
          'test-new-f-3': ['true'], 'test-new-f-4': []})
      fapdata._FIND_ONLY_IN_GALLERIES_FOLDER = _MockRegex({
          'test-new-f-0': [], 'test-new-f-2': ['true'],
          'test-new-f-3': [], 'test-new-f-4': ['true']})
      self.assertSetEqual(db.AddAllUserFolders(1, True), {10, 11, 13})
      self.assertListEqual(
          read_html.call_args_list,
          [mock.call('https://www.imagefap.com/showfavorites.php?userid=1&page=0'),
           mock.call('https://www.imagefap.com/showfavorites.php?userid=1&page=0&folderid=10'),
           mock.call('https://www.imagefap.com/showfavorites.php?userid=1&page=0&folderid=12'),
           mock.call('https://www.imagefap.com/showfavorites.php?userid=1&page=1'),
           mock.call('https://www.imagefap.com/showfavorites.php?userid=1&page=0&folderid=13'),
           mock.call('https://www.imagefap.com/showfavorites.php?userid=1&page=0&folderid=14'),
           mock.call('https://www.imagefap.com/showfavorites.php?userid=1&page=2')])
      read_html.reset_mock(side_effect=True)  # reset calls and side_effect
      self.assertDictEqual(db.favorites, {1: {
          10: {'name': 'new-f-0', 'date_blobs': 0, 'date_straight': 0,
               'images': [], 'failed_images': set(), 'pages': 0},
          11: {'name': 'known-folder-1', 'date_blobs': 1675360670, 'date_straight': 0, 'pages': 8,
               'images': [103, 104], 'failed_images': {(123, 1675360070, 'failed.jpg', 'f-url')}},
          13: {'name': 'new&f-3', 'date_blobs': 0, 'date_straight': 0,
               'images': [], 'failed_images': set(), 'pages': 0}}})
      fapdata._FIND_FOLDERS = None  # set to None for safety
      fapdata._FIND_ONLY_IN_PICTURE_FOLDER = None
      fapdata._FIND_ONLY_IN_GALLERIES_FOLDER = None
      # AddFolderPics ##############################################################################
      db.favorites[1][10]['pages'] = 9  # this will help test the backtracking
      db.favorites[1][10]['images'] = [100]
      read_html.side_effect = [
          'img-page-10-8', 'img-page-10-7',                   # backtrack on favorites 10
          'img-page-10-7', 'img-page-10-8', 'img-page-10-9',  # then forward
          'img-page-10-10', 'img-page-10-11',                 # and 2 extra for paging bug
          'img-page-13-0', 'img-page-13-1', 'img-page-13-2',  # normal forward
          'img-page-13-3', 'img-page-13-4']                   # and 2 extra for paging bug
      fapdata._FAVORITE_IMAGE = _MockRegex({
          'img-page-10-7': ['100', '101'], 'img-page-10-8': ['102'],
          'img-page-10-9': [], 'img-page-10-10': [], 'img-page-10-11': [],
          'img-page-13-0': ['105', '106'], 'img-page-13-1': ['107', '108', '109'],
          'img-page-13-2': [], 'img-page-13-3': [], 'img-page-13-4': []})
      self.assertListEqual(db.AddFolderPics(1, 10, False), [100, 101, 102])
      self.assertListEqual(db.AddFolderPics(1, 11, False), [103, 104])
      self.assertListEqual(db.AddFolderPics(1, 13, False), [105, 106, 107, 108, 109])
      self.assertListEqual(
          read_html.call_args_list,
          [mock.call('https://www.imagefap.com/showfavorites.php?userid=1&page=8&folderid=10'),
           mock.call('https://www.imagefap.com/showfavorites.php?userid=1&page=7&folderid=10'),
           mock.call('https://www.imagefap.com/showfavorites.php?userid=1&page=7&folderid=10'),
           mock.call('https://www.imagefap.com/showfavorites.php?userid=1&page=8&folderid=10'),
           mock.call('https://www.imagefap.com/showfavorites.php?userid=1&page=9&folderid=10'),
           mock.call('https://www.imagefap.com/showfavorites.php?userid=1&page=10&folderid=10'),
           mock.call('https://www.imagefap.com/showfavorites.php?userid=1&page=11&folderid=10'),
           mock.call('https://www.imagefap.com/showfavorites.php?userid=1&page=0&folderid=13'),
           mock.call('https://www.imagefap.com/showfavorites.php?userid=1&page=1&folderid=13'),
           mock.call('https://www.imagefap.com/showfavorites.php?userid=1&page=2&folderid=13'),
           mock.call('https://www.imagefap.com/showfavorites.php?userid=1&page=3&folderid=13'),
           mock.call('https://www.imagefap.com/showfavorites.php?userid=1&page=4&folderid=13')])
      read_html.reset_mock(side_effect=True)  # reset calls and side_effect
      self.assertDictEqual(db.favorites, {1: {
          10: {'name': 'new-f-0', 'date_blobs': 0, 'date_straight': 0,
               'images': [100, 101, 102], 'failed_images': set(), 'pages': 9},
          11: {'name': 'known-folder-1', 'date_blobs': 1675360670, 'date_straight': 0, 'pages': 8,
               'images': [103, 104], 'failed_images': {(123, 1675360070, 'failed.jpg', 'f-url')}},
          13: {'name': 'new&f-3', 'date_blobs': 0, 'date_straight': 0,
               'images': [105, 106, 107, 108, 109], 'failed_images': set(), 'pages': 2}}})
      fapdata._FAVORITE_IMAGE = None  # set to None for safety
      # ReadFavoritesIntoBlobs #####################################################################
      # prepare data by reading files, getting some CNN, etc
      test_images: dict[str, bytes] = {}
      test_cnn: dict[str, np.ndarray] = {}  # store the CNN data because it is huge
      for name in ('100.jpg', '101.jpg', '102.jpg', '103.jpg', '104.jpg',
                   '105.jpg', '106.jpg', '107.png', '108.png', '109.gif'):
        f_name = os.path.join(_TESTDATA_PATH, name)
        with open(f_name, 'rb') as f_obj:
          test_images[name] = f_obj.read()
        test_cnn[name] = db.duplicates.Encode(f_name)[-1]
      # mock some more data
      db._db['blobs'] = {
          '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {
              'loc': {(801, 'url-1', 'some-name.jpg', 2, 20),
                      (101, 'url-2', 'name-to-use.jpg', 1, 10)},
              'tags': set(), 'sz': 101, 'sz_thumb': 0, 'ext': 'jpg', 'percept': 'd99ee32e586716c8',
              'average': 'd99ee32e586716c8', 'diff': 'd99ee32e586716c8',
              'wavelet': 'd99ee32e586716c8', 'cnn': test_cnn['108.png'],
              'width': 160, 'height': 200, 'animated': False, 'date': 1675360670, 'gone': {}},
          'sha-107': {
              'loc': {(107, 'url-1', 'some-name.gif', 2, 20)},
              'tags': set(), 'sz': 107, 'sz_thumb': 0, 'ext': 'jpg', 'percept': 'd99ee32e586716c8',
              'average': 'd99ee32e586716c8', 'diff': 'd99ee32e586716c8',
              'wavelet': 'd99ee32e586716c8', 'cnn': test_cnn['107.png'],
              'width': 107, 'height': 1070, 'animated': False, 'date': 1675360670, 'gone': {}},
      }
      db._db['image_ids_index'] = {
          101: '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
          801: '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf', 107: 'sha-107'}
      read_html.side_effect = ['img-100', 'img-102', 'img-105', 'img-106',
                               'img-107', 'img-108', 'img-109']
      os.mkdir(os.path.join(db_path, 'blobs/'))
      with open(db._BlobPath(hashlib.sha256(test_images['101.jpg']).hexdigest()), 'wb') as f_obj:
        f_obj.write(test_images['101.jpg'])
      read_bin.side_effect = [
          test_images['100.jpg'], test_images['102.jpg'], test_images['105.jpg'],
          test_images['106.jpg'], test_images['107.png'], test_images['108.png'],
          test_images['109.gif']]
      fapdata._FULL_IMAGE = _MockRegex({
          'img-100': ['url-100'], 'img-102': ['url-102'], 'img-105': ['url-105'],
          'img-106': ['url-106'], 'img-107': ['url-107'], 'img-108': ['url-108'],
          'img-109': ['url-109']})
      fapdata._IMAGE_NAME = _MockRegex({
          'img-100': ['name-100.jpg'], 'img-102': ['name-102.jpg'], 'img-105': ['name/105.jpeg'],
          'img-106': ['name-106.jpeg'], 'img-107': ['name-107.png'], 'img-108': ['na/me-108.png'],
          'img-109': ['name-109.gif']})
      self.assertEqual(db.ReadFavoritesIntoBlobs(1, 10, 2, False), 111226)
      self.assertEqual(db.ReadFavoritesIntoBlobs(1, 11, 2, False), 0)
      self.assertEqual(db.ReadFavoritesIntoBlobs(1, 13, 2, False), 652075)
      self.assertEqual(db.FindDuplicates(), 3)
      self.assertListEqual(
          read_html.call_args_list,
          [mock.call('https://www.imagefap.com/photo/100/'),
           mock.call('https://www.imagefap.com/photo/102/'),
           mock.call('https://www.imagefap.com/photo/105/'),
           mock.call('https://www.imagefap.com/photo/106/'),
           mock.call('https://www.imagefap.com/photo/107/'),
           mock.call('https://www.imagefap.com/photo/108/'),
           mock.call('https://www.imagefap.com/photo/109/')])
      self.assertListEqual(
          read_bin.call_args_list,
          [mock.call('url-100'), mock.call('url-102'), mock.call('url-105'), mock.call('url-106'),
           mock.call('url-107'), mock.call('url-108'), mock.call('url-109')])
      read_html.reset_mock(side_effect=True)  # reset calls and side_effect
      for blob in db.blobs.values():
        del blob['cnn']  # type: ignore
      for blob in _BLOBS.values():
        del blob['cnn']  # type: ignore
      self.assertDictEqual(db.blobs, _BLOBS)
      self.assertDictEqual(db.image_ids_index, _INDEX)
      for dup_val in db.duplicates.registry.values():
        for method_val in list(dup_val['sources'].values()):
          for dup_keys in list(method_val.keys()):
            method_val[dup_keys] = 0.0
      self.assertDictEqual(db.duplicates.registry, _DUPLICATES)
      self.assertDictEqual(db.duplicates.index, _DUPLICATES_INDEX)
      self.assertTrue(os.path.exists(db._BlobPath(
          '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6')))
      self.assertTrue(os.path.exists(db.ThumbnailPath(
          '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6')))
      self.assertEqual(
          db.LocationStr((101, 'url-2', 'name-to-use.jpg', 1, 10)),
          'Luke/new-f-0/name-to-use.jpg (1/10/101)')
      self.assertEqual(
          db.LocationStr((107, 'url-1', 'some-name.gif', 1, 11)),
          'Luke/known-folder-1/some-name.gif (1/11/107)')
      with self.assertRaises(fapdata.Error):
        db.LocationStr((999, 'url-1', 'some-name.gif', 9, 99))
      fapdata._FAVORITE_IMAGE = None  # set to None for safety
      ##############################################################################################
      db.GetBlob('9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf')
      db.GetBlob('321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6')
      db.tags[12] = {'name': 'tag12', 'tags': {13: {'name': 'tag13', 'tags': {}}}}
      db.tags[22] = {'name': 'tag22', 'tags': {23: {'name': 'tag23', 'tags': {}}}}
      db.blobs['9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf']['tags'].update(
          {12, 23})
      db.blobs['321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6']['tags'].update(
          {13, 22})
      db.Save()
      db.blobs['0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19']['gone'] = {
          102: (1675368671, fapdata._FailureLevel.FULL_RES, 'xxx')}
      self.assertListEqual(db.PrintStats(actually_print=False)[1:], _PRINTED_STATS_FULL)
      self.assertListEqual(db.PrintUsersAndFavorites(actually_print=False), _PRINTED_USERS_FULL)
      db.favorites[2] = {20: {'name': 'foo-bar'}}  # type: ignore
      self.assertListEqual(db.PrintBlobs(actually_print=False), _PRINTED_BLOBS_FULL)
      # DeleteUserAndAlbums & DeleteAlbum & DeleteAllDuplicates ####################################
      db.favorites[2] = {20: {'images': [107, 801]}}  # type: ignore
      db.image_ids_index[103] = 'sha-103'
      db.image_ids_index[104] = 'sha-104'
      db.blobs['sha-103'] = {'ext': 'jpg', 'loc': {(103, '', 'nm103', 1, 11)}}  # type: ignore
      db.blobs['sha-104'] = {'ext': 'jpg', 'loc': {(104, '', 'nm104', 1, 11)}}  # type: ignore
      self.assertTupleEqual(db.DeleteAlbum(1, 13), (3, 0))
      self.assertDictEqual(db.favorites, _FAVORITES_TRIMMED)
      for blob in _BLOBS_TRIMMED.values():
        if 'cnn' in blob:
          del blob['cnn']  # type: ignore
      self.assertDictEqual(db.blobs, _BLOBS_TRIMMED)
      self.assertDictEqual(db.image_ids_index, _INDEX_TRIMMED)
      self.assertDictEqual(db.duplicates.registry, _DUPLICATES_TRIMMED)
      self.assertDictEqual(db.duplicates.index, _DUPLICATES_INDEX_TRIMMED)
      self.assertTupleEqual(db.DeleteUserAndAlbums(1), (4, 0))
      self.assertDictEqual(
          db.users, {2: {'date_albums': 0, 'date_finished': 0, 'date_audit': 0, 'name': 'Ben'}})
      self.assertDictEqual(db.favorites, {2: {20: {'images': [107, 801]}}})
      for blob in _BLOBS_NO_LUKE.values():
        if 'cnn' in blob:
          del blob['cnn']  # type: ignore
      self.assertDictEqual(db.blobs, _BLOBS_NO_LUKE)
      self.assertDictEqual(db.image_ids_index, _INDEX_NO_LUKE)
      self.assertDictEqual(db.duplicates.registry, _DUPLICATES_TRIMMED)
      self.assertDictEqual(db.duplicates.index, _DUPLICATES_INDEX_TRIMMED)
      self.assertTupleEqual(db.DeletePendingDuplicates(), (1, 2))
      self.assertTupleEqual(db.DeleteAllDuplicates(), (0, 0))
      read_html.reset_mock(side_effect=True)  # reset calls and side_effect
      # Audit ######################################################################################
      db.blobs['sha-107']['loc'].add((777, 'url-777', 'some-name-7.gif', 1, 77))
      mock_time.return_value = 1675368680  # 02/feb/2023 20:11:20
      read_html.side_effect = ['img-107', 'img-777', 'img-801']
      fapdata._FULL_IMAGE = _MockRegex({
          'img-107': ['url-107'], 'img-777': ['url-777'], 'img-801': []})
      mock_get.side_effect = [_MockRequestsGet(200, 107), _MockRequestsGet(404, 1)]
      with self.assertRaisesRegex(fapdata.Error, r'not yet finished'):
        db.Audit(2, 2, True)
      db.users[2]['date_finished'] = 1675360000
      db.favorites[2][20]['name'] = 'Ben1'  # type: ignore
      db.Audit(2, 2, True)
      self.assertListEqual(
          read_html.call_args_list,
          [mock.call('https://www.imagefap.com/photo/107/'),
           mock.call('https://www.imagefap.com/photo/777/'),
           mock.call('https://www.imagefap.com/photo/801/')])
      self.assertListEqual(
          mock_get.call_args_list,
          [mock.call('url-107', stream=True, timeout=None),
           mock.call('url-777', stream=True, timeout=None)])
      self.assertDictEqual(
          db.users,
          {2: {'date_albums': 0, 'date_audit': 1675368680,
               'date_finished': 1675360000, 'name': 'Ben'}})
      self.assertDictEqual(db.blobs, _BLOBS_AUDITED)
      self.assertListEqual(mock_time.call_args_list, [mock.call() for _ in range(21)])
      self.assertEqual(db.users[2]['date_audit'], 1675368680)
      fapdata._FULL_IMAGE = None      # set to None for safety
    # cleanup environ so they don't interfere in other tests
    del os.environ['IMAGEFAP_FAVORITES_DB_PATH']


class _MockRegex:

  def __init__(self, return_values: dict[str, list[Union[str, tuple[str, ...]]]]):
    """Init."""
    self._return_values = return_values

  def findall(self, query: str) -> list[Union[str, tuple[str, ...]]]:
    """Find all."""
    return self._return_values[query]


class _MockRequestsGet:

  def __init__(self, status_code: int, content_length: int):
    self.status_code = status_code
    self.headers = {'Content-Length': content_length}

  def __enter__(self):
    return self

  def __exit__(self, unused_type, unused_value, unused_traceback):
    pass


_FAVORITES_TRIMMED: fapdata._FavoriteType = {  # type: ignore
    1: {
        10: {'date_blobs': 1675368670, 'date_straight': 0, 'images': [100, 101, 102],
             'name': 'new-f-0', 'pages': 9, 'failed_images': set()},
        11: {'date_blobs': 1675360670, 'date_straight': 0, 'images': [103, 104],
             'name': 'known-folder-1', 'pages': 8,
             'failed_images': {(123, 1675360070, 'failed.jpg', 'f-url')}},
    },
    2: {20: {'images': [107, 801]}},
}


_BLOBS: fapdata._BlobType = {
    '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19': {
        'animated': False, 'ext': 'jpg', 'height': 200,
        'loc': {(102, 'url-102', 'name-102.jpg', 1, 10)},
        'percept': 'cd4fc618316732e7', 'average': '303830301a1c387f', 'diff': '60e2c3c2d2b1e2ce',
        'wavelet': '303838383a1f3e7f', 'cnn': np.array([1, 2, 3]),
        'sz': 54643, 'sz_thumb': 54643, 'tags': set(), 'width': 168, 'date': 1675368670, 'gone': {},
    },
    '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': {
        'animated': False, 'ext': 'png', 'height': 173,
        'loc': {(108, 'url-108', 'na-me-108.png', 1, 13)},
        'percept': 'd99ee32e586716c8', 'average': 'ffffff9a180060c8', 'diff': '6854541633d5c991',
        'wavelet': 'ffffbf88180060c8', 'cnn': np.array([1, 2, 3]),
        'sz': 45309, 'sz_thumb': 45309, 'tags': set(), 'width': 130, 'date': 1675368670, 'gone': {},
    },
    '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {
        'animated': False, 'ext': 'jpg', 'height': 200,
        'loc': {(101, 'url-2', 'name-to-use.jpg', 1, 10), (801, 'url-1', 'some-name.jpg', 2, 20)},
        'percept': 'd99ee32e586716c8', 'average': 'd99ee32e586716c8', 'diff': 'd99ee32e586716c8',
        'wavelet': 'd99ee32e586716c8', 'cnn': np.array([1, 2, 3]),
        'sz': 101, 'sz_thumb': 0, 'tags': set(), 'width': 160, 'date': 1675360670, 'gone': {},
    },
    'dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180': {
        'animated': False, 'ext': 'jpg', 'height': 222,
        'loc': {(106, 'url-106', 'name-106.jpg', 1, 13)},
        'percept': '89991f6f62a63479', 'average': '091b5f7761323000', 'diff': '737394c5d3e66431',
        'wavelet': '091b7f7f71333018', 'cnn': np.array([1, 2, 3]),
        'sz': 89216, 'sz_thumb': 11890, 'tags': set(), 'width': 300, 'date': 1675368670, 'gone': {},
    },
    'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': {
        'animated': False, 'ext': 'jpg', 'height': 246,
        'loc': {(100, 'url-100', 'name-100.jpg', 1, 10), (105, 'url-105', 'name-105.jpg', 1, 13)},
        'percept': 'cc8fc37638703ee1', 'average': '3838381810307078', 'diff': '626176372565c3f2',
        'wavelet': '3e3f3f1b10307878', 'cnn': np.array([1, 2, 3]),
        'sz': 56583, 'sz_thumb': 56583, 'tags': set(), 'width': 200, 'date': 1675368670, 'gone': {},
    },
    'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e': {
        'animated': True, 'ext': 'gif', 'height': 100, 'tags': set(),
        'loc': {(109, 'url-109', 'name-109.gif', 1, 13)},
        'percept': 'e699669966739866', 'average': 'ffffffffffffe7e7', 'diff': '000000000000080c',
        'wavelet': 'ffffffffffffe7e7', 'cnn': np.array([1, 2, 3]), 'date': 1675368670, 'gone': {},
        'sz': 444973, 'sz_thumb': 302143, 'width': 500},
    'sha-107': {
        'animated': False, 'ext': 'jpg', 'height': 1070,
        'loc': {(107, 'url-1', 'some-name.gif', 2, 20), (107, 'url-107', 'name-107.png', 1, 13)},
        'percept': 'd99ee32e586716c8', 'average': 'd99ee32e586716c8', 'diff': 'd99ee32e586716c8',
        'wavelet': 'd99ee32e586716c8', 'cnn': np.array([1, 2, 3]),
        'sz': 107, 'sz_thumb': 72577, 'tags': set(), 'width': 107, 'date': 1675368670, 'gone': {},
    },
}

_BLOBS_TRIMMED: fapdata._BlobType = {  # type: ignore
    '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19': {
        'animated': False, 'ext': 'jpg', 'height': 200,
        'loc': {(102, 'url-102', 'name-102.jpg', 1, 10)},
        'percept': 'cd4fc618316732e7', 'average': '303830301a1c387f', 'diff': '60e2c3c2d2b1e2ce',
        'wavelet': '303838383a1f3e7f', 'cnn': np.array([1, 2, 3]),
        'sz': 54643, 'sz_thumb': 54643, 'tags': set(), 'width': 168, 'date': 1675368670,
        'gone': {102: (1675368671, fapdata._FailureLevel.FULL_RES, 'xxx')},
    },
    '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {
        'animated': False, 'ext': 'jpg', 'height': 200,
        'loc': {(101, 'url-2', 'name-to-use.jpg', 1, 10), (801, 'url-1', 'some-name.jpg', 2, 20)},
        'percept': 'd99ee32e586716c8', 'average': 'd99ee32e586716c8', 'diff': 'd99ee32e586716c8',
        'wavelet': 'd99ee32e586716c8', 'cnn': np.array([1, 2, 3]),
        'sz': 101, 'sz_thumb': 0, 'tags': {12, 23}, 'width': 160, 'date': 1675360670, 'gone': {},
    },
    'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': {
        'animated': False, 'ext': 'jpg', 'height': 246,
        'loc': {(100, 'url-100', 'name-100.jpg', 1, 10)},
        'percept': 'cc8fc37638703ee1', 'average': '3838381810307078', 'diff': '626176372565c3f2',
        'wavelet': '3e3f3f1b10307878', 'cnn': np.array([1, 2, 3]),
        'sz': 56583, 'sz_thumb': 56583, 'tags': set(), 'width': 200, 'date': 1675368670, 'gone': {},
    },
    'sha-107': {
        'animated': False, 'ext': 'jpg', 'height': 1070,
        'loc': {(107, 'url-1', 'some-name.gif', 2, 20)},
        'percept': 'd99ee32e586716c8', 'average': 'd99ee32e586716c8', 'diff': 'd99ee32e586716c8',
        'wavelet': 'd99ee32e586716c8', 'cnn': np.array([1, 2, 3]),
        'sz': 107, 'sz_thumb': 72577, 'tags': set(), 'width': 107, 'date': 1675368670, 'gone': {},
    },
    'sha-103': {'ext': 'jpg', 'loc': {(103, '', 'nm103', 1, 11)}},
    'sha-104': {'ext': 'jpg', 'loc': {(104, '', 'nm104', 1, 11)}},
}

_BLOBS_NO_LUKE: fapdata._BlobType = {
    '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {
        'animated': False, 'ext': 'jpg', 'height': 200,
        'loc': {(801, 'url-1', 'some-name.jpg', 2, 20)},
        'percept': 'd99ee32e586716c8', 'average': 'd99ee32e586716c8', 'diff': 'd99ee32e586716c8',
        'wavelet': 'd99ee32e586716c8', 'cnn': np.array([1, 2, 3]),
        'sz': 101, 'sz_thumb': 0, 'tags': {12, 23}, 'width': 160, 'date': 1675360670, 'gone': {},
    },
    'sha-107': {
        'animated': False, 'ext': 'jpg', 'height': 1070,
        'loc': {(107, 'url-1', 'some-name.gif', 2, 20)},
        'percept': 'd99ee32e586716c8', 'average': 'd99ee32e586716c8', 'diff': 'd99ee32e586716c8',
        'wavelet': 'd99ee32e586716c8', 'cnn': np.array([1, 2, 3]),
        'sz': 107, 'sz_thumb': 72577, 'tags': set(), 'width': 107, 'date': 1675368670, 'gone': {},
    },
}

_BLOBS_AUDITED: fapdata._BlobType = {  # type: ignore
    '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {
        'animated': False, 'ext': 'jpg', 'height': 200,
        'loc': {(801, 'url-1', 'some-name.jpg', 2, 20)},
        'percept': 'd99ee32e586716c8', 'average': 'd99ee32e586716c8', 'diff': 'd99ee32e586716c8',
        'wavelet': 'd99ee32e586716c8',
        'sz': 101, 'sz_thumb': 0, 'tags': {12, 23}, 'width': 160, 'date': 1675360670,
        'gone': {801: (1675368680, fapdata._FailureLevel.URL_EXTRACTION,
                       'https://www.imagefap.com/photo/801/')},
    },
    'sha-107': {
        'animated': False, 'ext': 'jpg', 'height': 1070,
        'loc': {(107, 'url-1', 'some-name.gif', 2, 20),
                (777, 'url-777', 'some-name-7.gif', 1, 77)},
        'percept': 'd99ee32e586716c8', 'average': 'd99ee32e586716c8', 'diff': 'd99ee32e586716c8',
        'wavelet': 'd99ee32e586716c8',
        'sz': 107, 'sz_thumb': 72577, 'tags': set(), 'width': 107, 'date': 1675368680,
        'gone': {777: (1675368680, fapdata._FailureLevel.FULL_RES, 'url-777')},
    },
}

_INDEX: fapdata._ImagesIdIndexType = {
    100: 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e',
    101: '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
    102: '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19',
    105: 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e',
    106: 'dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180',
    107: 'sha-107',
    108: '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
    109: 'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e',
    801: '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf'
}

_INDEX_TRIMMED: fapdata._ImagesIdIndexType = {
    100: 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e',
    101: '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
    102: '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19',
    103: 'sha-103',
    104: 'sha-104',
    107: 'sha-107',
    801: '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf'
}

_INDEX_NO_LUKE: fapdata._ImagesIdIndexType = {
    107: 'sha-107',
    801: '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf'
}

_DUPLICATES: fapdata.duplicates.DuplicatesType = {
    ('321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
     '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
     'sha-107'): {
        'sources': {
            'average': {
                ('9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
                 'sha-107'): 0.0,
            },
            'cnn': {
                ('321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
                 '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf'): 0.0,
                ('321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
                 'sha-107'): 0.0,
                ('9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
                 'sha-107'): 0.0,
            },
            'diff': {
                ('9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
                 'sha-107'): 0.0,
            },
            'percept': {
                ('321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
                 '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf'): 0.0,
                ('321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
                 'sha-107'): 0.0,
                ('9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
                 'sha-107'): 0.0,
            },
            'wavelet': {
                ('9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
                 'sha-107'): 0.0,
            },
        },
        'verdicts': {
            '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': 'new',
            '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': 'new',
            'sha-107': 'new',
        },
    },
}

_DUPLICATES_TRIMMED: fapdata.duplicates.DuplicatesType = {
    ('9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf', 'sha-107'): {
        'sources': {
            'average': {
                ('9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
                 'sha-107'): 0.0},
            'cnn': {
                ('9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
                 'sha-107'): 0.0},
            'diff': {
                ('9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
                 'sha-107'): 0.0},
            'percept': {
                ('9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
                 'sha-107'): 0.0},
            'wavelet': {
                ('9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
                 'sha-107'): 0.0},
        },
        'verdicts': {
            '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': 'new',
            'sha-107': 'new',
        },
    },
}

_DUPLICATES_INDEX: fapdata.duplicates.DuplicatesKeyIndexType = {
    '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': (
        '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
        '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
        'sha-107'),
    '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': (
        '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
        '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
        'sha-107'),
    'sha-107': (
        '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
        '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
        'sha-107'),
}

_DUPLICATES_INDEX_TRIMMED: fapdata.duplicates.DuplicatesKeyIndexType = {
    '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': (
        '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
        'sha-107'),
    'sha-107': (
        '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
        'sha-107'),
}

_TEST_TAGS_1 = {  # this has many places where there are missing keys
    10: {
        'name': 'plain',
    },
    1: {
        'tags': {
            11: {
                'tags': {},
            },
        },
    },
    2: {
        'name': 'two',
        'tags': {
            22: {
                'name': 'two-two',
                'tags': {},
            },
            24: {
                'name': 'two-four',
                'tags': {
                    246: {
                        'name': 'deep',
                    },
                },
            },
        },
    },
    3: {
        'tags': {
            33: {
                'name': 'three-three',
                'tags': {},
            },
        },
    },
}

_TEST_TAGS_2: fapdata._TagType = {  # this is all valid tags structure
    10: {
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
            22: {
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
}

_TEST_TAGS_3: fapdata._TagType = {
    10: {
        'name': 'plain',
        'tags': {},
    },
    1: {
        'name': 'TheOne',
        'tags': {},
    },
    2: {
        'name': 'Second',
        'tags': {
            22: {
                'name': 'two-two',
                'tags': {},
            },
            24: {
                'name': 'two-four',
                'tags': {
                    5: {
                        'name': 'Foo',
                        'tags': {},
                    },
                    246: {
                        'name': 'The Deep One',
                        'tags': {
                            6: {
                                'name': 'Bar',
                                'tags': {},
                            },
                        },
                    },
                },
            },
        },
    },
    4: {
        'name': 'four',
        'tags': {},
    },
}

_PRINTED_TAGS = """
TAG_ID: TAG_NAME (NUMBER_OF_IMAGES_WITH_TAG / SIZE_OF_IMAGES_WITH_TAG)

1: 'one' (1 / 10b)
    11: 'one-one' (0 / 0b)
10: 'plain' (0 / 0b)
3: 'three' (0 / 0b)
    33: 'three-three' (2 / 65b)
2: 'two' (1 / 10b)
    24: 'two-four' (0 / 0b)
        246: 'deep' (1 / 55b)
    22: 'two-two' (0 / 0b)
""".splitlines()[1:]

_PRINTED_STATS_EMPTY = """
Database is located in '%s/imagefap.database', and is 561b (56100.000%% of total images size)
0b total (unique) images size (- min, - max, - mean with - standard deviation, 0 are animated)

2 users
1 favorite galleries (oldest: 2023/Feb/02-17:57:50-UTC / newer: 2023/Feb/02-17:57:50-UTC)
0 unique images (0 total, 0 exact duplicates)
1 unique failed images in all user albums
0 unique images are now disappeared from imagefap site
0 perceptual duplicates in 0 groups
""".splitlines()[1:]

_PRINTED_USERS_EMPTY = """
ID: USER_NAME
    FILE STATS FOR USER
    => ID: FAVORITE_NAME (IMAGE_COUNT / FAILED_COUNT / PAGE_COUNT / DATE DOWNLOAD)
           FILE STATS FOR FAVORITES

1: 'Luke'
    0b files size (- min, - max, - mean with - standard deviation)
    => 11: 'known-folder-1' (2 / 1 / 8 / 2023/Feb/02-17:57:50-UTC)

2: 'Ben'
    0b files size (- min, - max, - mean with - standard deviation)
""".splitlines()[1:]

_PRINTED_BLOBS_EMPTY = """
SHA256_HASH: ID1/'NAME1' or ID2/'NAME2' or ..., PIXELS (WIDTH, HEIGHT) [ANIMATED]
    => {'TAG1', 'TAG2', ...}

""".splitlines()[1:]

_PRINTED_STATS_FULL = """
Database is located in '%s/imagefap.database', and is 1.74kb (0.258%% of total images size)
674.74kb total (unique) images size (101b min, 434.54kb max, 96.39kb mean with 152.34kb standard deviation, 1 are animated)
Pixel size (width, height): 22.49k pixels min (130, 173), 114.49k pixels max (107, 1070), 52.62k mean with 30.92k standard deviation
530.42kb total thumbnail size (0b min, 295.06kb max, 75.77kb mean with 99.91kb standard deviation), 78.6% of total images size

2 users
3 favorite galleries (oldest: 2023/Feb/02-17:57:50-UTC / newer: 2023/Feb/02-20:11:10-UTC)
7 unique images (10 total, 3 exact duplicates)
1 unique failed images in all user albums
1 unique images are now disappeared from imagefap site
3 perceptual duplicates in 1 groups
""".splitlines()[2:]  # noqa: E501

_PRINTED_USERS_FULL = """
ID: USER_NAME
    FILE STATS FOR USER
    => ID: FAVORITE_NAME (IMAGE_COUNT / FAILED_COUNT / PAGE_COUNT / DATE DOWNLOAD)
           FILE STATS FOR FAVORITES

1: 'Luke'
    730.00kb files size (101b min, 434.54kb max, 91.25kb mean with 141.78kb standard deviation)
    => 10: 'new-f-0' (3 / 0 / 9 / 2023/Feb/02-20:11:10-UTC)
           108.72kb files size (101b min, 55.26kb max, 36.24kb mean with 31.31kb standard deviation)
    => 11: 'known-folder-1' (2 / 1 / 8 / 2023/Feb/02-17:57:50-UTC)
    => 13: 'new&f-3' (5 / 0 / 2 / 2023/Feb/02-20:11:10-UTC)
           621.28kb files size (107b min, 434.54kb max, 124.25kb mean with 176.23kb standard deviation)

2: 'Ben'
    0b files size (- min, - max, - mean with - standard deviation)
""".splitlines()[1:]  # noqa: E501

_PRINTED_BLOBS_FULL = """
SHA256_HASH: ID1/'NAME1' or ID2/'NAME2' or ..., PIXELS (WIDTH, HEIGHT) [ANIMATED]
    => {'TAG1', 'TAG2', ...}

0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19: Luke/new-f-0/name-102.jpg (1/10/102), 33.60k (168, 200)
321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6: Luke/new&f-3/na-me-108.png (1/13/108), 22.49k (130, 173)
    => {tag13 (13), tag22 (22)}
9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf: Luke/new-f-0/name-to-use.jpg (1/10/101) or Ben/foo-bar/some-name.jpg (2/20/801), 32.00k (160, 200)
    => {tag12 (12), tag23 (23)}
dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180: Luke/new&f-3/name-106.jpg (1/13/106), 66.60k (300, 222)
e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e: Luke/new-f-0/name-100.jpg (1/10/100) or Luke/new&f-3/name-105.jpg (1/13/105), 49.20k (200, 246)
ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e: Luke/new&f-3/name-109.gif (1/13/109), 50.00k (500, 100) animated
sha-107: Luke/new&f-3/name-107.png (1/13/107) or Ben/foo-bar/some-name.gif (2/20/107), 114.49k (107, 1070)
""".splitlines()[1:]  # noqa: E501


SUITE = unittest.TestLoader().loadTestsFromTestCase(TestFapDatabase)


if __name__ == '__main__':
  unittest.main()
