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

import base64
import copy
import hashlib
import os
import os.path
# import pdb
import tempfile
import unittest
from unittest import mock

import numpy as np

from baselib import base
from fapfavorites import fapbase
from fapfavorites import fapbase_test
from fapfavorites import fapdata

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


_TESTDATA_PATH = os.path.join(os.path.dirname(__file__), 'testdata/')


class TestFapDatabase(unittest.TestCase):
  """Tests for fapdata.py."""

  @mock.patch('fapfavorites.fapdata.os.path.isdir')
  @mock.patch('fapfavorites.fapdata.os.mkdir')
  def test_Constructor(self, mock_mkdir: mock.MagicMock, mock_is_dir: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_is_dir.return_value = False
    del os.environ['IMAGEFAP_FAVORITES_DB_PATH']
    os.environ['IMAGEFAP_FAVORITES_DB_KEY'] = (
        'LRtw2A4U9PAtihUow5p_eQex6IYKM7nUoPlf1fkKPgc=')  # cspell:disable-line
    db = fapdata.FapDatabase('~/Downloads/some-dir/')
    self.assertListEqual(
        mock_is_dir.call_args_list,
        [mock.call(os.path.expanduser('~/Downloads/some-dir/')),
         mock.call(os.path.expanduser('~/Downloads/some-dir/blobs/')),
         mock.call(os.path.expanduser('~/Downloads/some-dir/thumbs/'))])
    self.assertListEqual(
        mock_mkdir.call_args_list,
        [mock.call(os.path.expanduser('~/Downloads/some-dir/')),
         mock.call(os.path.expanduser('~/Downloads/some-dir/blobs/')),
         mock.call(os.path.expanduser('~/Downloads/some-dir/thumbs/'))])
    self.assertEqual(db._original_dir, '~/Downloads/some-dir/')
    self.assertEqual(os.environ['IMAGEFAP_FAVORITES_DB_PATH'], '~/Downloads/some-dir/')
    self.assertEqual(db._db_dir, os.path.expanduser('~/Downloads/some-dir/'))
    self.assertEqual(db._db_path, os.path.expanduser('~/Downloads/some-dir/imagefap.database'))
    self.assertEqual(db._blobs_dir, os.path.expanduser('~/Downloads/some-dir/blobs/'))
    self.assertEqual(
        db._key, b'LRtw2A4U9PAtihUow5p_eQex6IYKM7nUoPlf1fkKPgc=')  # cspell:disable-line
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

  def test_SHAFromFileName(self) -> None:
    """Test."""
    db = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    self.assertEqual(  # no encryption
        db._SHAFromFileName(
            '  434FEF877249ACFD67CF5c37a082898bf151b2b30126d5f618656e1b073c0278.jpg  '),
        '434fef877249acfd67cf5c37a082898bf151b2b30126d5f618656e1b073c0278')
    db._key = b'FLx2WdoT7BvRBDeX6hRjzC7KaFn3SOQ8WPFNmXT57_M='
    db._sha_encoder = base.BlockEncoder256(base64.urlsafe_b64decode(db._key))
    self.assertEqual(  # with encryption
        db._SHAFromFileName(
            '  434FEF877249ACFD67CF5c37a082898bf151b2b30126d5f618656e1b073c0278.gif  '),
        'd97b2972cbd1db528abe1c51ab12a7c7aa2fa6e35d721b66c958be92911bdc00')
    with self.assertRaisesRegex(fapdata.Error, r'Unexpected or invalid blob/thumb file name'):
      db._SHAFromFileName(
          '434fef877249acfd67cf5c37a082898bf151.gif')
    with self.assertRaisesRegex(fapdata.Error, r'Unexpected or invalid blob/thumb file name'):
      db._SHAFromFileName(
          '434FEF877249ACFD67CF5c37a082898bf151b2b30126d5f618656e1b073c0278')

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

  @mock.patch('fapfavorites.fapdata.os.path.isdir')
  @mock.patch('fapfavorites.fapbase.FapHTMLRead')
  def test_AddUserByID(self, mock_read: mock.MagicMock, mock_is_dir: mock.MagicMock) -> None:
    """Test."""
    mock_is_dir.return_value = True
    fapbase._FIND_NAME_IN_FAVORITES = fapbase_test.MockRegex(
        {'user_html': ['foo &amp; user'], 'invalid': []})
    db = fapdata.FapDatabase('/xxx/')
    mock_read.return_value = 'invalid'
    with self.assertRaisesRegex(fapbase.Error, r'for 11'):
      db.AddUserByID(11)
    mock_read.return_value = 'user_html'
    self.assertEqual(db.AddUserByID(10), 'foo & user')
    self.assertDictEqual(
        db.users,
        {10: {'date_albums': 0, 'date_finished': 0, 'date_audit': 0, 'name': 'foo & user'}})
    fapbase._FIND_NAME_IN_FAVORITES = None  # make sure is not used again in next call
    self.assertEqual(db.AddUserByID(10), 'foo & user')
    self.assertEqual(db.UserStr(10), 'foo & user (10)')
    with self.assertRaises(fapdata.Error):
      db.UserStr(5)
    self.assertListEqual(
        mock_read.call_args_list,
        [mock.call('https://www.imagefap.com/showfavorites.php?userid=11&page=0'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=0')])
    with self.assertRaisesRegex(fapbase.Error, r'Empty'):
      fapbase.GetUserDisplayName(0)

  @mock.patch('fapfavorites.fapdata.os.path.isdir')
  @mock.patch('fapfavorites.fapbase.FapHTMLRead')
  def test_AddUserByName(self, mock_read: mock.MagicMock, mock_is_dir: mock.MagicMock) -> None:
    """Test."""
    mock_is_dir.return_value = True
    fapbase._FIND_USER_ID_RE = fapbase_test.MockRegex({'user_html': ['10'], 'invalid': []})
    fapbase._FIND_NAME_IN_FAVORITES = fapbase_test.MockRegex(
        {'user_html': ['foo &amp; user'], 'invalid': []})
    db = fapdata.FapDatabase('/xxx/')
    mock_read.return_value = 'invalid'
    with self.assertRaisesRegex(fapbase.Error, r'ID for user \'no-user\''):
      db.AddUserByName('no-user')
    fapbase._FIND_USER_ID_RE = fapbase_test.MockRegex({'user_html': ['10'], 'invalid': ['12']})
    with self.assertRaisesRegex(fapbase.Error, r'Could not find user name for 12'):
      db.AddUserByName('no-user')
    mock_read.return_value = 'user_html'
    self.assertTupleEqual(db.AddUserByName('foo-user'), (10, 'foo & user'))
    self.assertDictEqual(
        db.users,
        {10: {'date_albums': 0, 'date_finished': 0, 'date_audit': 0, 'name': 'foo & user'}})
    fapbase._FIND_USER_ID_RE = None  # make sure is not used again in next call
    fapbase._FIND_NAME_IN_FAVORITES = None
    self.assertTupleEqual(db.AddUserByName('foo & user'), (10, 'foo & user'))
    self.assertEqual(db.UserStr(10), 'foo & user (10)')
    with self.assertRaises(fapdata.Error):
      db.UserStr(5)
    self.assertListEqual(
        mock_read.call_args_list,
        [mock.call('https://www.imagefap.com/profile/no-user'),
         mock.call('https://www.imagefap.com/profile/no-user'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=12&page=0'),
         mock.call('https://www.imagefap.com/profile/foo-user'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=0')])
    with self.assertRaisesRegex(fapbase.Error, r'Empty'):
      fapbase.ConvertUserName('  ')

  @mock.patch('fapfavorites.fapdata.os.path.isdir')
  @mock.patch('fapfavorites.fapbase.FapHTMLRead')
  def test_AddFolderByID(self, mock_read: mock.MagicMock, mock_is_dir: mock.MagicMock) -> None:
    """Test."""
    mock_is_dir.return_value = True
    fapbase.FIND_NAME_IN_FOLDER = fapbase_test.MockRegex(
        {'folder_html': ['foo &amp; folder'], 'invalid': []})
    fapbase._FIND_ONLY_IN_PICTURE_FOLDER = fapbase_test.MockRegex({'folder_html': ['true']})
    fapbase._FIND_ONLY_IN_GALLERIES_FOLDER = fapbase_test.MockRegex({'folder_html': []})
    db = fapdata.FapDatabase('/xxx/')
    db.users[10] = {'name': 'username'}  # type: ignore
    mock_read.return_value = 'invalid'
    with self.assertRaisesRegex(fapdata.Error, r'for 11/22'):
      db.AddFolderByID(11, 22)
    mock_read.return_value = 'folder_html'
    self.assertEqual(db.AddFolderByID(10, 20), 'foo & folder')
    self.assertDictEqual(
        db.favorites,
        {10: {20: {'date_blobs': 0, 'images': [], 'failed_images': set(),
                   'name': 'foo & folder', 'pages': 0}}})
    fapbase.FIND_NAME_IN_FOLDER = None  # make sure is not used again in next call
    fapbase._FIND_ONLY_IN_PICTURE_FOLDER = None
    fapbase._FIND_ONLY_IN_GALLERIES_FOLDER = None
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
  @mock.patch('fapfavorites.fapbase.FapHTMLRead')
  def test_AddFolderByName(self, mock_read: mock.MagicMock, mock_is_dir: mock.MagicMock) -> None:
    """Test."""
    mock_is_dir.return_value = True
    fapbase.FIND_FOLDERS = fapbase_test.MockRegex({
        'folder_html_1': [('100', 'no1')], 'folder_html_2': [('200', 'no2'), ('300', 'no3')],
        'folder_html_3': [('400', 'foo &amp; folder'), ('500', 'no5')], 'invalid': []})
    fapbase._FIND_ONLY_IN_PICTURE_FOLDER = fapbase_test.MockRegex({'folder_html_test': ['true']})
    fapbase._FIND_ONLY_IN_GALLERIES_FOLDER = fapbase_test.MockRegex({'folder_html_test': []})
    db = fapdata.FapDatabase('/xxx/')
    db.users[10] = {'name': 'username'}  # type: ignore
    mock_read.return_value = 'invalid'
    with self.assertRaisesRegex(fapbase.Error, r'folder \'no-folder\' for user 11'):
      db.AddFolderByName(11, 'no-folder')
    mock_read.side_effect = ['folder_html_1', 'folder_html_2', 'folder_html_3', 'folder_html_test']
    self.assertTupleEqual(db.AddFolderByName(10, 'foo & folder'), (400, 'foo & folder'))
    self.assertDictEqual(
        db.favorites,
        {10: {400: {'date_blobs': 0, 'images': [], 'failed_images': set(),
                    'name': 'foo & folder', 'pages': 0}}})
    fapbase.FIND_FOLDERS = None  # make sure is not used again in next call
    fapbase._FIND_ONLY_IN_PICTURE_FOLDER = None
    fapbase._FIND_ONLY_IN_GALLERIES_FOLDER = None
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
    with self.assertRaisesRegex(fapbase.Error, r'Empty'):
      fapbase.ConvertFavoritesName(10, '  ')

  @mock.patch('fapfavorites.fapdata.os.path.isdir')
  @mock.patch('fapfavorites.fapdata.base.INT_TIME')
  @mock.patch('fapfavorites.fapbase.FapHTMLRead')
  @mock.patch('fapfavorites.fapbase.CheckFolderIsForImages')
  @mock.patch('fapfavorites.fapdata.FapDatabase._CheckWorkHysteresis')
  def test_AddAllUserFolders(
      self, hysteresis: mock.MagicMock, is_images: mock.MagicMock,
      html_read: mock.MagicMock, int_time: mock.MagicMock, is_dir: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    is_dir.return_value = True
    int_time.return_value = 1001
    hysteresis.side_effect = [False, True]
    html_read.side_effect = ['page-0', 'page-1', 'page-2']
    is_images.side_effect = [None, None, fapdata.Error()]
    # get_pics.return_value = ([100, 101, 102, 103, 104], 2, 3)
    fapbase.FIND_FOLDERS = fapbase_test.MockRegex({
        'page-0': [('15', 'fav-15'), ('20', 'fav-15')],
        'page-1': [('25', 'fav-25'), ('30', 'fav-30')],
        'page-2': []})
    db = fapdata.FapDatabase('/xxx/')
    with self.assertRaisesRegex(fapdata.Error, r'user was not added'):
      db.AddAllUserFolders(10, False)
    db.users[10] = {'name': 'user-10', 'date_albums': 400, 'date_finished': 0, 'date_audit': 0}
    db.favorites[10] = {
        20: {'name': 'fav-20', 'pages': 1, 'date_blobs': 500,
             'images': [100, 101], 'failed_images': set()}}
    self.assertSetEqual(db.AddAllUserFolders(10, False), {20})         # this call hits hysteresis
    self.assertSetEqual(db.AddAllUserFolders(10, True), {15, 20, 25})  # this doesn't
    self.assertListEqual(
        hysteresis.call_args_list,
        [mock.call(False, 400, 'Getting all image favorites for user user-10 (10)'),
         mock.call(True, 400, 'Getting all image favorites for user user-10 (10)')])
    self.assertListEqual(
        html_read.call_args_list,
        [mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=0'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=1'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=2')])
    self.assertListEqual(
        is_images.call_args_list,
        [mock.call(10, 15), mock.call(10, 25), mock.call(10, 30)])
    fapbase.FIND_FOLDERS = None  # set to None for safety

  @mock.patch('fapfavorites.fapdata.os.path.isdir')
  @mock.patch('fapfavorites.fapbase.GetFolderPics')
  @mock.patch('fapfavorites.fapdata.FapDatabase._CheckWorkHysteresis')
  def test_AddFolderPics(
      self, hysteresis: mock.MagicMock, get_pics: mock.MagicMock, is_dir: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    is_dir.return_value = True
    hysteresis.side_effect = [False, True]
    get_pics.return_value = ([100, 101, 102, 103, 104], 2, 3)
    db = fapdata.FapDatabase('/xxx/')
    with self.assertRaisesRegex(fapdata.Error, r'user/folder was not added'):
      db.AddFolderPics(10, 20, False)
    db.users[10] = {'name': 'user-10', 'date_albums': 0, 'date_finished': 0, 'date_audit': 0}
    db.favorites[10] = {
        20: {'name': 'fav-20', 'pages': 1, 'date_blobs': 500,
             'images': [100, 101], 'failed_images': set()}}
    self.assertListEqual(db.AddFolderPics(10, 20, False), [100, 101])  # this call hits hysteresis
    self.assertListEqual(db.AddFolderPics(10, 20, True), [100, 101, 102, 103, 104])  # this doesn't
    self.assertListEqual(
        hysteresis.call_args_list,
        [mock.call(False, 500, 'Reading album user-10/fav-20 (10/20) pages & IDs'),
         mock.call(True, 500, 'Reading album user-10/fav-20 (10/20) pages & IDs')])
    get_pics.assert_called_once_with(10, 20, img_list_hint=[100, 101], seen_pages_hint=1)

  @mock.patch('fapfavorites.fapdata.os.path.isdir')
  @mock.patch('fapfavorites.fapdata.base.INT_TIME')
  def test_CheckWorkHysteresis(self, int_time: mock.MagicMock, is_dir: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    is_dir.return_value = True
    int_time.return_value = 200
    db = fapdata.FapDatabase('/xxx/')
    fapdata.FAVORITES_MIN_DOWNLOAD_WAIT = 100
    self.assertFalse(db._CheckWorkHysteresis(False, 150, 'foo'))
    self.assertTrue(db._CheckWorkHysteresis(True, 150, 'foo'))
    self.assertTrue(db._CheckWorkHysteresis(False, 50, 'foo'))
    self.assertTrue(db._CheckWorkHysteresis(True, 50, 'foo'))

  @mock.patch('fapfavorites.fapdata.base.INT_TIME')
  @mock.patch('fapfavorites.fapbase.ExtractFullImageURL')
  @mock.patch('fapfavorites.fapbase.GetBinary')
  @mock.patch('fapfavorites.fapdata.FapDatabase._CheckWorkHysteresis')
  def test_DownloadAll_MakeThumbnailForBlob_SaveImage_Print_Delete(
      self, hysteresis: mock.MagicMock, get_bin: mock.MagicMock,
      img_url: mock.MagicMock, mock_time: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_time.return_value = 1675368670  # 02/feb/2023 20:11:10
    hysteresis.side_effect = [False, True, True, True]
    # prepare data by reading files
    test_images: dict[str, bytes] = {}
    test_names = ('100.jpg', '101.jpg', '102.jpg', '103.jpg', '104.png',  # 104 is actually a JPG!
                  '105.jpg', '106.jpg', '107.png', '108.png', '109.gif')
    for name in test_names:
      f_name = os.path.join(_TESTDATA_PATH, name)
      with open(f_name, 'rb') as f_obj:
        test_images[name] = f_obj.read()
    # prepare side effects
    get_bin.side_effect = [(test_images[name], hashlib.sha256(test_images[name]).hexdigest())
                           for name in test_names] + [fapbase.Error404('url-110')]
    img_url.side_effect = [('url-100', '100.jpg', 'jpg'),  # this is for album 10/20
                           ('url-101', '101.jpg', 'jpg'),
                           ('url-102', '102.jpg', 'jpg'),
                           ('url-103', '103.jpg', 'jpg'),
                           ('url-104', '104.png', 'png'),  # 104 is actually a JPG!
                           ('url-105', '105.jpg', 'jpg'),  # 105 is identical to 100
                           ('url-106', '106.jpg', 'jpg'),
                           ('url-107', '107.png', 'png'),
                           ('url-108', '108.png', 'png'),
                           ('url-109', '109.gif', 'gif'),
                           ('url-110', '110.jpg', 'jpg'),  # this last one will 404
                           ('url-104', '104.png', 'png'),  # this is for album 10/30
                           ('url-105', '105.jpg', 'jpg'),
                           fapbase.Error404('url-106')]    # this last one will 404
    with tempfile.TemporaryDirectory() as db_path:
      db = fapdata.FapDatabase(db_path, create_if_needed=True)  # create a password-less DB
      # test error case
      with self.assertRaisesRegex(fapdata.Error, r'user/folder was not added'):
        db.DownloadAll(10, 20, 5, False)
      # setup basic DB data
      db.users[10] = {'name': 'user-10', 'date_albums': 0, 'date_finished': 0, 'date_audit': 0}
      db.favorites[10] = {
          20: {'name': 'fav-20', 'pages': 1, 'date_blobs': 500, 'failed_images': set(),
               'images': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110]},
          30: {'name': 'fav-30', 'pages': 1, 'date_blobs': 600, 'failed_images': set(),
               'images': [104, 105, 106]}}
      # test hysteresis case
      self.assertEqual(db.DownloadAll(10, 20, 5, False), 0)  # this call hits hysteresis
      # test regular case
      self.assertEqual(db.DownloadAll(10, 20, 5, True), 893851)  # this doesn't
      # do the same album again
      self.assertEqual(db.DownloadAll(10, 20, 5, True), 0)  # no hysteresis, no new work done
      # do another album with some image ID duplicates
      mock_time.return_value = 1675368690  # 02/feb/2023 20:11:30
      self.assertEqual(db.DownloadAll(10, 30, 5, True), 0)
      # data checks
      test_cnn: dict[str, np.ndarray] = {}  # store the CNN data for later because it is huge
      for sha, blob in db.blobs.items():
        test_cnn[sha] = blob['cnn']
        del blob['cnn']  # type: ignore
      self.assertDictEqual(db.favorites, _FAVORITES)
      self.assertDictEqual(db.blobs, _BLOBS)
      self.assertDictEqual(db.image_ids_index, _INDEX)
      # test some auxiliary methods
      with self.assertRaisesRegex(fapdata.Error, r'Invalid location'):
        db.LocationStr((99, 99, 99), ('foo', 'new'))
      with self.assertRaisesRegex(fapdata.Error, r'Blob \'invalid-sha\' not found'):
        db._BlobPath('invalid-sha')
      with self.assertRaisesRegex(fapdata.Error, r'Thumbnail \'invalid-sha\' not found'):
        db._ThumbnailPath('invalid-sha')
      self.assertTrue(
          db.HasBlob('4c49275f4bb6ed2fd502a51a0fc3b24661483c1aa9d4acc1dc91f035877df207'))
      self.assertTrue(
          db.HasThumbnail('4c49275f4bb6ed2fd502a51a0fc3b24661483c1aa9d4acc1dc91f035877df207'))
      self.assertEqual(
          len(db.GetBlob('dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180')),
          89216)
      self.assertEqual(
          len(db.GetThumbnail('dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180')),
          11890)
      self.assertListEqual(db.PrintStats(), (_PRINTED_STATS_FULL % db_path).splitlines()[1:])
      self.assertListEqual(db.PrintUsersAndFavorites(), _PRINTED_USERS_FULL)
      db._db['tags'][1] = {'name': 'one', 'tags': {}}
      db.blobs['dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180']['tags'] = {1}
      self.assertListEqual(db.PrintBlobs(), _PRINTED_BLOBS_FULL)
      # call checks
      self.assertListEqual(
          hysteresis.call_args_list,
          [mock.call(False, 500, 'Downloading album user-10/fav-20 (10/20) images'),
           mock.call(True, 500, 'Downloading album user-10/fav-20 (10/20) images'),
           mock.call(True, 1675368670, 'Downloading album user-10/fav-20 (10/20) images'),
           mock.call(True, 600, 'Downloading album user-10/fav-30 (10/30) images')])
      self.assertListEqual(
          img_url.call_args_list,
          [mock.call(100), mock.call(101), mock.call(102), mock.call(103), mock.call(104),
           mock.call(105), mock.call(106), mock.call(107), mock.call(108), mock.call(109),
           mock.call(110), mock.call(104), mock.call(105), mock.call(106)])
      self.assertListEqual(
          get_bin.call_args_list,
          [mock.call('url-100'), mock.call('url-101'), mock.call('url-102'), mock.call('url-103'),
           mock.call('url-104'), mock.call('url-105'), mock.call('url-106'), mock.call('url-107'),
           mock.call('url-108'), mock.call('url-109'), mock.call('url-110')])
      # duplicates
      for sha, blob in db.blobs.items():  # put CNN data back in
        blob['cnn'] = test_cnn[sha]
      db.blobs['9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf']['loc'][
          (10, 20, 101)] = ('101.jpg', 'skip')
      self.assertEqual(db.FindDuplicates(), 2)
      self.assertSetEqual(
          set(db.duplicates.registry.keys()),
          {('321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
            '4c49275f4bb6ed2fd502a51a0fc3b24661483c1aa9d4acc1dc91f035877df207')})
      self.assertDictEqual(db.duplicates.index, _DUPLICATES_INDEX)
      # delete all
      with self.assertRaisesRegex(fapdata.Error, r'Invalid user'):
        db.DeleteUserAndAlbums(99)
      with self.assertRaisesRegex(fapdata.Error, r'Invalid user'):
        db.DeleteAlbum(99, 99)
      with self.assertRaisesRegex(fapdata.Error, r'Invalid folder'):
        db.DeleteAlbum(10, 99)
      self.assertTupleEqual(db.DeleteUserAndAlbums(10), (9, 1))
      self.assertDictEqual(db.users, {})
      self.assertDictEqual(db.favorites, {})
      self.assertDictEqual(db.blobs, {})
      self.assertDictEqual(db.image_ids_index, {})

  @mock.patch('fapfavorites.fapdata.FapDatabase._UsersIntegrityCheck')
  @mock.patch('fapfavorites.fapdata.FapDatabase._AlbumIdsIntegrityCheck')
  @mock.patch('fapfavorites.fapdata.FapDatabase._CheckForIndexOrphans')
  @mock.patch('fapfavorites.fapdata.FapDatabase._CheckLocationIntegrity')
  @mock.patch('fapfavorites.fapdata.FapDatabase._CheckTagsIntegrity')
  @mock.patch('fapfavorites.fapdata.FapDatabase.Save')
  def test_AlbumIntegrityCheck(
      self, save: mock.MagicMock, tags: mock.MagicMock, location: mock.MagicMock,
      index: mock.MagicMock, albums: mock.MagicMock, users: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    db = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    albums.return_value = {1, 2, 3}
    db.AlbumIntegrityCheck()
    users.assert_called_once_with()
    albums.assert_called_once_with()
    index.assert_called_once_with({1, 2, 3})
    location.assert_called_once_with()
    tags.assert_called_once_with()
    save.assert_called_once_with()

  @mock.patch('fapfavorites.fapdata.FapDatabase._FileOrphanedCheck')
  @mock.patch('fapfavorites.fapdata.FapDatabase._SHAOrphanedCheck')
  def test_BlobIntegrityCheck(
      self, sha_orphaned: mock.MagicMock, file_orphaned: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    db = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    db.BlobIntegrityCheck()
    sha_orphaned.assert_called_once_with()
    file_orphaned.assert_called_once_with()

  @mock.patch('fapfavorites.fapdata.FapDatabase.AddUserByID')
  def test_UsersIntegrityCheck(self, add_user: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    db = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    db.favorites[99] = {}  # add extra user

    def _NewUser(uid: int) -> None:
      db.users[uid] = {'name': f'user{uid}'}  # type: ignore

    add_user.side_effect = _NewUser
    db._UsersIntegrityCheck()
    add_user.assert_called_once_with(99)

  @mock.patch('fapfavorites.fapdata.FapDatabase._CreateFilesOnDiskAndProposeBlob')
  @mock.patch('fapfavorites.fapdata.base.INT_TIME')
  def test_AlbumIdsIntegrityCheck(
      self, int_time: mock.MagicMock, create_blob: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    int_time.return_value = 9999
    db = _TestDBFactory()     # pylint: disable=no-value-for-parameter
    db.favorites[10][99] = {  # add album to be skipped (b/c is unfinished)
        'name': 'unfinished', 'date_blobs': 0, 'pages': 1,
        'failed_images': set(), 'images': [1, 2]}
    db.favorites[10][30]['images'].extend(
        [1000, 1001, 1002, 1003, 1004, 1005])   # add 6 spurious IDs to the list
    db.image_ids_index[1003] = 'unknown-sha-3'  # add the last 3 to the index, pointing
    db.image_ids_index[1004] = 'unknown-sha-4'  # to unknown SHA entries
    db.image_ids_index[1005] = 'unknown-sha-5'
    db.favorites[10][30]['failed_images'] = {        # add 3 failed images that we will add to index
        (1010, 1675368670, '1010.jpg', 'url-1010'),  # this one with invalid SHA
        (1011, 1675368670, '1011.jpg', 'url-1011'),  # this with valid SHA and name
        (1012, 1675368670, None, None)}              # this with valid SHA but empty name field
    db.image_ids_index[1010] = 'unknown-sha-10'
    db.image_ids_index[1011] = 'ed257bbbcb316f05f852f80b705d0c911e8ee51c7962fa207962b40a653fd5f9'
    db.image_ids_index[1012] = 'ed257bbbcb316f05f852f80b705d0c911e8ee51c7962fa207962b40a653fd5f9'
    create_blob.side_effect = [
        ('74bab8c9b692a582f7b90c27a0d80fe0a073f70991c1c8aa1815745127e5c449',  # 1000: known SHA
         {'loc': {(10, 30, 1000): ('1000.png', 'new')}}),
        ('new-sha', {'loc': {(10, 30, 1001): ('1001.jpg', 'new')}}),          # 1001: new SHA
        fapbase.Error404('url-1002'),                                         # 1002: 404 error
        ('unknown-sha-3', {'loc': {(10, 30, 1003): ('1003.jpg', 'new')}}),    # 1003: success in add
        ('different-sha-4', {'loc': {(10, 30, 1004): ('1004.jpg', 'new')}}),  # 1004: invalid SHA
        fapbase.Error404('url-1005')]                                         # 1005: 404 error
    self.assertSetEqual(
        db._AlbumIdsIntegrityCheck(),
        {100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 1, 2, 1000, 1001, 1003, 1011, 1012})
    self.assertListEqual(
        create_blob.call_args_list,
        [mock.call(10, 30, 1000), mock.call(10, 30, 1001), mock.call(10, 30, 1002),
         mock.call(10, 30, 1003), mock.call(10, 30, 1004), mock.call(10, 30, 1005)])
    self.assertListEqual(
        db.favorites[10][30]['images'], [104, 105, 106, 1000, 1001, 1003, 1011, 1012])
    self.assertSetEqual(
        db.favorites[10][30]['failed_images'],
        {(1002, 9999, None, 'url-1002'),
         (1004, 9999, '1004.jpg', None),
         (1005, 9999, None, 'url-1005'),
         (1010, 1675368670, '1010.jpg', 'url-1010')})
    self.assertSetEqual(
        set(db.image_ids_index),
        {100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 1000, 1001, 1003, 1011, 1012})
    self.assertEqual(
        db.image_ids_index[1000],
        '74bab8c9b692a582f7b90c27a0d80fe0a073f70991c1c8aa1815745127e5c449')
    self.assertEqual(db.image_ids_index[1001], 'new-sha')
    self.assertEqual(db.image_ids_index[1003], 'unknown-sha-3')
    self.assertDictEqual(
        db.blobs['74bab8c9b692a582f7b90c27a0d80fe0a073f70991c1c8aa1815745127e5c449']['loc'],
        {(10, 20, 104): ('104.png', 'new'),
         (10, 30, 104): ('104.png', 'new'),
         (10, 30, 1000): ('1000.png', 'new')})
    self.assertDictEqual(
        db.blobs['ed257bbbcb316f05f852f80b705d0c911e8ee51c7962fa207962b40a653fd5f9']['loc'],
        {(10, 20, 103): ('103.jpg', 'new'),
         (10, 30, 1011): ('1011.jpg', 'new'),
         (10, 30, 1012): ('unknown', 'new')})
    self.assertDictEqual(db.blobs['new-sha'], {'loc': {(10, 30, 1001): ('1001.jpg', 'new')}})
    self.assertDictEqual(db.blobs['unknown-sha-3'], {'loc': {(10, 30, 1003): ('1003.jpg', 'new')}})

  def test_CheckForIndexOrphans(self) -> None:
    """Test."""
    self.maxDiff = None
    db = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    valid_ids = {100, 101, 102, 103, 104, 106, 107, 108, 109}  # 105 is missing
    db._CheckForIndexOrphans(valid_ids)
    self.assertSetEqual(set(db.image_ids_index), valid_ids)

  def test_CheckLocationIntegrity(self) -> None:
    """Test."""
    self.maxDiff = None
    db = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    db.favorites[10][20]['images'].remove(108)  # only loc in the blob
    db.favorites[10][30]['images'].remove(104)  # one of 2 loc in the blob
    db._CheckLocationIntegrity()
    self.assertDictEqual(
        db.blobs['74bab8c9b692a582f7b90c27a0d80fe0a073f70991c1c8aa1815745127e5c449']['loc'],
        {(10, 20, 104): ('104.png', 'new')})
    self.assertIn(104, db.image_ids_index)
    self.assertNotIn('321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6', db.blobs)
    self.assertNotIn(108, db.image_ids_index)

  def test_CheckTagsIntegrity(self) -> None:
    """Test."""
    self.maxDiff = None    # note: the valid tags are {1, 33, 3, 2, 10, 11, 246, 22, 24}
    db = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    db.blobs['0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19'][
        'tags'] = {3, 2, 10, 11}     # all valid
    db.blobs['74bab8c9b692a582f7b90c27a0d80fe0a073f70991c1c8aa1815745127e5c449'][
        'tags'] = {1, 33, 333, 666}  # 333 & 666 are invalid
    db.blobs['e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'][
        'tags'] = {9, 99}            # all invalid
    db._CheckTagsIntegrity()
    self.assertSetEqual(
        db.blobs['0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19']['tags'],
        {3, 2, 10, 11})
    self.assertSetEqual(
        db.blobs['74bab8c9b692a582f7b90c27a0d80fe0a073f70991c1c8aa1815745127e5c449']['tags'],
        {1, 33})
    self.assertSetEqual(
        db.blobs['e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e']['tags'], set())

  @mock.patch('fapfavorites.fapdata.FapDatabase.HasBlob')
  @mock.patch('fapfavorites.fapdata.FapDatabase.HasThumbnail')
  @mock.patch('fapfavorites.fapdata.FapDatabase.GetBlob')
  @mock.patch('fapfavorites.fapdata.FapDatabase.GetThumbnail')
  @mock.patch('fapfavorites.fapdata.FapDatabase.Save')
  @mock.patch('fapfavorites.fapdata.FapDatabase._CreateFilesOnDiskAndProposeBlob')
  def test_SHAOrphanedCheck(
      self, propose_blob: mock.MagicMock, save: mock.MagicMock, get_thumb: mock.MagicMock,
      get_blob: mock.MagicMock, has_thumb: mock.MagicMock, has_blob: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    # correct keys and sizes are as follows:
    # 0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19: (54643, 54643)
    # 321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6: (45309, 45309)
    # 4c49275f4bb6ed2fd502a51a0fc3b24661483c1aa9d4acc1dc91f035877df207: (72577, 72577) no blob
    # 74bab8c9b692a582f7b90c27a0d80fe0a073f70991c1c8aa1815745127e5c449: (48259, 48259) no thumb
    # 9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf: (39147, 39147)
    # dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180: (89216, 11890) blob sz
    # e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e: (56583, 56583) decrypt err
    # ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e: (444973, 302143) thumb sz
    # ed257bbbcb316f05f852f80b705d0c911e8ee51c7962fa207962b40a653fd5f9: (43144, 43144)
    db = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    has_blob.side_effect = [True, True, False, True, True, True, True, True, True]
    has_thumb.side_effect = [True, True, True, False, True, True, True, True, True]
    get_blob.side_effect = ['0' * 54643, '3' * 45309, '9' * 39147, 'd' * 99,
                            'e' * 56583, 'e' * 444973, 'e' * 43144]
    get_thumb.side_effect = ['0' * 54643, '3' * 45309, '9' * 39147, 'd' * 11890,
                             fapdata.base.bin_fernet.InvalidToken, 'e' * 99, 'e' * 43144]
    propose_blob.side_effect = [
        ('4c49275f4bb6ed2fd502a51a0fc3b24661483c1aa9d4acc1dc91f035877df207',
         {'loc': {}, 'tags': {}, 'gone': {}, 'flag': True}),
        ('74bab8c9b692a582f7b90c27a0d80fe0a073f70991c1c8aa1815745127e5c449',
         {'loc': {}, 'tags': {}, 'gone': {}, 'flag': True}),
        ('wrong-sha', {'loc': {}, 'tags': {}, 'gone': {}, 'flag': True}),  # 1st try, will do again
        ('dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180',
         {'loc': {}, 'tags': {}, 'gone': {}, 'flag': True}),  # 2nd try will succeed
        ('e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e',
         {'loc': {}, 'tags': {}, 'gone': {}, 'flag': True}),
        fapbase.Error404('url')]
    db._SHAOrphanedCheck()
    for sha in ['4c49275f4bb6ed2fd502a51a0fc3b24661483c1aa9d4acc1dc91f035877df207',
                '74bab8c9b692a582f7b90c27a0d80fe0a073f70991c1c8aa1815745127e5c449',
                'dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180',
                'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e']:
      # make sure these guys got corrected by checking the 'flag' we introduced
      self.assertTrue(db.blobs[sha]['flag'])  # type: ignore
    self.assertListEqual(has_blob.call_args_list, [mock.call(k) for k in sorted(db.blobs.keys())])
    self.assertListEqual(has_thumb.call_args_list, [mock.call(k) for k in sorted(db.blobs.keys())])
    get_calls = [mock.call('0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19'),
                 mock.call('321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6'),
                 mock.call('9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf'),
                 mock.call('dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180'),
                 mock.call('e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'),
                 mock.call('ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e'),
                 mock.call('ed257bbbcb316f05f852f80b705d0c911e8ee51c7962fa207962b40a653fd5f9')]
    self.assertListEqual(get_blob.call_args_list, get_calls)
    self.assertListEqual(get_thumb.call_args_list, get_calls)
    self.assertListEqual(
        propose_blob.call_args_list,
        [mock.call(10, 20, 107), mock.call(10, 20, 104), mock.call(10, 20, 106),
         mock.call(10, 30, 106), mock.call(10, 20, 100), mock.call(10, 20, 109)])
    save.assert_called_once_with()

  @mock.patch('fapfavorites.fapbase.ExtractFullImageURL')
  @mock.patch('fapfavorites.fapbase.GetBinary')
  @mock.patch('fapfavorites.fapdata.FapDatabase._SaveImage')
  @mock.patch('fapfavorites.fapdata.base.INT_TIME')
  def test_CreateFilesOnDiskAndProposeBlob(
      self, int_time: mock.MagicMock, save: mock.MagicMock,
      get_bin: mock.MagicMock, img_url: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    with open(os.path.join(_TESTDATA_PATH, '109.gif'), 'rb') as f_obj:
      test_image = f_obj.read()
    int_time.return_value = 9000
    img_url.return_value = ('url-109', '109.jpg', 'jpg')  # (is actually a gif)
    get_bin.return_value = (test_image, 'sha-109')
    with tempfile.TemporaryDirectory() as db_path:
      db = fapdata.FapDatabase(db_path, create_if_needed=True)  # create a password-less DB
      sha, blob = db._CreateFilesOnDiskAndProposeBlob(10, 20, 30)
      self.assertEqual(sha, 'sha-109')
      del blob['cnn']  # type: ignore
      self.assertDictEqual(blob, {
          'animated': True, 'average': 'ffffffffffffe7e7', 'date': 9000,
          'diff': '000000000000080c', 'ext': 'gif', 'gone': {}, 'height': 100,
          'loc': {(10, 20, 30): ('109.jpg', 'new')}, 'percept': 'e699669966739866', 'sz': 444973,
          'sz_thumb': 302143, 'tags': set(), 'wavelet': 'ffffffffffffe7e7', 'width': 500})
      int_time.assert_called_once_with()
      img_url.assert_called_once_with(30)
      get_bin.assert_called_once_with('url-109')
      save.assert_called_once_with(f'{db_path}/blobs/sha-109.gif', test_image)
      self.assertTrue(os.path.exists(f'{db_path}/thumbs/sha-109.gif'))

  @mock.patch('os.walk')
  @mock.patch('os.remove')
  def test_FileOrphanedCheck(self, remove: mock.MagicMock, walk: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    db = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    walk.side_effect = [   # the '43FEF...' files are the ones that do not exist in the loaded DB
        [(None, None, ['unencrypted.anything.jpg',
                       'dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180.jpg  ',
                       '  434FEF877249ACFD67CF5c37a082898bf151b2b30126d5f618656e1b073c0278.jpg  ']),
         (None, None, ['invalid'])],
        [(None, None, ['unencrypted.anything.jpg',
                       '  74bab8c9b692a582f7b90c27a0d80fe0a073f70991c1c8aa1815745127e5c449.jpg',
                       '  434FEF877249ACFD67CF5c37a082898bf151b2b30126d5f618656e1b073c0279.jpg  ']),
         (None, None, ['invalid'])]]
    db._FileOrphanedCheck()
    self.assertListEqual(walk.call_args_list, [mock.call('/foo/blobs/'), mock.call('/foo/thumbs/')])
    self.assertListEqual(
        remove.call_args_list,
        [mock.call('/foo/blobs/unencrypted.anything.jpg'),
         mock.call('/foo/thumbs/unencrypted.anything.jpg'),
         mock.call(
             '/foo/blobs/434FEF877249ACFD67CF5c37a082898bf151b2b30126d5f618656e1b073c0278.jpg'),
         mock.call(
             '/foo/thumbs/434FEF877249ACFD67CF5c37a082898bf151b2b30126d5f618656e1b073c0279.jpg')])

  @mock.patch('fapfavorites.fapdata.base.INT_TIME')
  @mock.patch('fapfavorites.fapdata.requests.get')
  @mock.patch('fapfavorites.fapbase.FapHTMLRead')
  @mock.patch('fapfavorites.fapdata.FapDatabase.Save')
  def test_Audit(
      self, mock_save: mock.MagicMock, mock_read: mock.MagicMock, mock_get: mock.MagicMock,
      int_time: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    int_time.return_value = 1676368670
    db = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    with self.assertRaisesRegex(fapdata.Error, r'Unknown user'):
      db.Audit(99, 5, False)
    mock_read.side_effect = ['page-100', 'page-105', 'page-101', 'page-102',
                             fapbase.Error404('page-103'), 'page-104', 'page-106', 'page-107',
                             fapbase.Error404('page-108'), 'page-109']  # 103 & 108 fail here
    fapbase.FULL_IMAGE = fapbase_test.MockRegex({
        'page-100': ['url-100'], 'page-101': ['url-101'], 'page-102': [],
        'page-104': ['url-104'], 'page-105': ['url-105'], 'page-106': [],
        'page-107': ['url-107'], 'page-109': []})  # 102 & 106 & 109 fail here
    mock_get.side_effect = [_MockRequestsGet(200, 56583),  # id 100, correct size
                            _MockRequestsGet(200, 56583),  # id 105, correct size
                            _MockRequestsGet(200, 39147),  # id 101, correct size
                            _MockRequestsGet(404, 1),      # id 104, error 404
                            _MockRequestsGet(200, 99)]     # id 107, INCORRECT size
    db.Audit(10, 5, False)
    self.assertListEqual(
        mock_read.call_args_list,
        [mock.call('https://www.imagefap.com/photo/100/'),
         mock.call('https://www.imagefap.com/photo/105/'),
         mock.call('https://www.imagefap.com/photo/101/'),
         mock.call('https://www.imagefap.com/photo/102/'),
         mock.call('https://www.imagefap.com/photo/103/'),
         mock.call('https://www.imagefap.com/photo/104/'),
         mock.call('https://www.imagefap.com/photo/106/'),
         mock.call('https://www.imagefap.com/photo/107/'),
         mock.call('https://www.imagefap.com/photo/108/'),
         mock.call('https://www.imagefap.com/photo/109/')])
    self.assertListEqual(
        mock_get.call_args_list,
        [mock.call('url-100', stream=True, timeout=None),
         mock.call('url-105', stream=True, timeout=None),
         mock.call('url-101', stream=True, timeout=None),
         mock.call('url-104', stream=True, timeout=None),
         mock.call('url-107', stream=True, timeout=None)])
    self.assertListEqual(mock_save.call_args_list, [mock.call(), mock.call()])
    self.assertEqual(db.users[10]['date_audit'], 1676368670)
    self.assertDictEqual(db.blobs, _BLOBS_AUDITED)
    fapbase.FULL_IMAGE = None  # set to None for safety

  @mock.patch('fapfavorites.fapdata.FapDatabase.TagsWalk')
  @mock.patch('fapfavorites.fapdata.FapDatabase.ExportTag')
  def test_ExportAll(self, export: mock.MagicMock, walk: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    db = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    walk.return_value = [(10, None, None, None), (20, None, None, None)]
    export.side_effect = [5, 6]
    self.assertEqual(db.ExportAll(re_number_files=True), 11)
    walk.assert_called_once_with()
    self.assertListEqual(
        export.call_args_list,
        [mock.call(10, re_number_files=True), mock.call(20, re_number_files=True)])

  @mock.patch('os.path.isdir')
  @mock.patch('os.path.exists')
  @mock.patch('os.mkdir')
  @mock.patch('os.remove')
  @mock.patch('os.listdir')
  @mock.patch('fapfavorites.fapdata.FapDatabase.GetBlob')
  @mock.patch('fapfavorites.fapdata.hashlib.sha256')
  def test_ExportTag_No_Renumber(
      self, digest: mock.MagicMock, get_blob: mock.MagicMock, listdir: mock.MagicMock,
      remove: mock.MagicMock, mkdir: mock.MagicMock, exists: mock.MagicMock,
      isdir: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    db = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    db.blobs['0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19']['tags'] = {22, 33}
    db.blobs['4c49275f4bb6ed2fd502a51a0fc3b24661483c1aa9d4acc1dc91f035877df207']['tags'] = {1, 22}
    self.assertEqual(db.ExportTag(246), 0)
    isdir.return_value = False
    exists.return_value = True
    get_blob.return_value = b'file'

    class _Sha256:

      def __init__(self, digest):
        self._digest = digest

      def hexdigest(self):  # pylint: disable=missing-function-docstring
        return self._digest

    digest.side_effect = [
        _Sha256('0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19'), _Sha256('no')]
    op = mock.mock_open(read_data=b'some data')
    with mock.patch('builtins.open', op):
      self.assertEqual(db.ExportTag(22), 2)
    self.assertListEqual(
        isdir.call_args_list,
        [mock.call('/foo/tag_export/'),
         mock.call('/foo/tag_export/two'), mock.call('/foo/tag_export/two/two-two')])
    self.assertListEqual(
        mkdir.call_args_list,
        [mock.call('/foo/tag_export/'),
         mock.call('/foo/tag_export/two'), mock.call('/foo/tag_export/two/two-two')])
    self.assertListEqual(
        exists.call_args_list,
        [mock.call('/foo/tag_export/two/two-two/102.jpg'),
         mock.call('/foo/tag_export/two/two-two/107.png')])
    self.assertListEqual(digest.call_args_list, [mock.call(b'some data'), mock.call(b'some data')])
    get_blob.assert_called_once_with(
        '4c49275f4bb6ed2fd502a51a0fc3b24661483c1aa9d4acc1dc91f035877df207')
    self.assertListEqual(
        op.call_args_list,
        [mock.call('/foo/tag_export/two/two-two/102.jpg', 'rb'),
         mock.call('/foo/tag_export/two/two-two/107.png', 'rb'),
         mock.call('/foo/tag_export/two/two-two/4c49275f4b-107.png', 'wb')])
    handle = op()
    self.assertListEqual(handle.write.call_args_list, [mock.call(b'file')])
    listdir.assert_not_called()
    remove.assert_not_called()

  @mock.patch('os.path.isdir')
  @mock.patch('os.path.exists')
  @mock.patch('os.mkdir')
  @mock.patch('os.remove')
  @mock.patch('os.listdir')
  @mock.patch('fapfavorites.fapdata.FapDatabase.GetBlob')
  @mock.patch('fapfavorites.fapdata.hashlib.sha256')
  def test_ExportTag_With_Renumber(
      self, digest: mock.MagicMock, get_blob: mock.MagicMock, listdir: mock.MagicMock,
      remove: mock.MagicMock, mkdir: mock.MagicMock, exists: mock.MagicMock,
      isdir: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    db = _TestDBFactory()  # pylint: disable=no-value-for-parameter
    db.blobs['0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19']['tags'] = {22, 33}
    db.blobs['4c49275f4bb6ed2fd502a51a0fc3b24661483c1aa9d4acc1dc91f035877df207']['tags'] = {1, 22}
    isdir.return_value = False
    get_blob.side_effect = [b'file1', b'file2']
    listdir.return_value = ['list1', 'list2']
    op = mock.mock_open(read_data=b'some data')
    with mock.patch('builtins.open', op):
      self.assertEqual(db.ExportTag(22, re_number_files=True), 2)
    self.assertListEqual(
        isdir.call_args_list,
        [mock.call('/foo/tag_export/'),
         mock.call('/foo/tag_export/two'), mock.call('/foo/tag_export/two/two-two')])
    self.assertListEqual(
        mkdir.call_args_list,
        [mock.call('/foo/tag_export/'),
         mock.call('/foo/tag_export/two'), mock.call('/foo/tag_export/two/two-two')])
    self.assertListEqual(
        op.call_args_list,
        [mock.call('/foo/tag_export/two/two-two/00001-102.jpg', 'wb'),
         mock.call('/foo/tag_export/two/two-two/00002-107.png', 'wb')])
    handle = op()
    self.assertListEqual(handle.write.call_args_list, [mock.call(b'file1'), mock.call(b'file2')])
    listdir.assert_called_once_with('/foo/tag_export/two/two-two')
    self.assertListEqual(
        remove.call_args_list,
        [mock.call('/foo/tag_export/two/two-two/list1'),
         mock.call('/foo/tag_export/two/two-two/list2')])
    digest.assert_not_called()
    exists.assert_not_called()

  @mock.patch('os.path.exists')
  @mock.patch('os.path.getmtime')
  def test_GetDatabaseTimestamp(self, getmtime: mock.MagicMock, exists: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    exists.side_effect = [True, False]
    getmtime.return_value = 100.93
    self.assertEqual(fapdata.GetDatabaseTimestamp(), 101)
    with self.assertRaisesRegex(fapdata.Error, r''):
      fapdata.GetDatabaseTimestamp('/foo/bar')
    self.assertListEqual(
        exists.call_args_list,
        [mock.call(os.path.expanduser('~/Downloads/imagefap/imagefap.database')),
         mock.call('/foo/bar/imagefap.database')])
    getmtime.assert_called_once_with(os.path.expanduser('~/Downloads/imagefap/imagefap.database'))


class _MockRequestsGet:

  def __init__(self, status_code: int, content_length: int):
    self.status_code = status_code
    self.headers = {'Content-Length': content_length}

  def __enter__(self):
    return self

  def __exit__(self, unused_type, unused_value, unused_traceback):
    pass


@mock.patch('fapfavorites.fapdata.os.path.isdir')
def _TestDBFactory(mock_isdir: mock.MagicMock) -> fapdata.FapDatabase:
  mock_isdir.return_value = True
  db = fapdata.FapDatabase('/foo/', create_if_needed=False)
  # need to deepcopy: some of the test methods will change the dict!
  db._db['users'] = copy.deepcopy(_USERS)
  db._db['favorites'] = copy.deepcopy(_FAVORITES)
  db._db['blobs'] = copy.deepcopy(_BLOBS)
  db._db['image_ids_index'] = copy.deepcopy(_INDEX)
  db._db['tags'] = copy.deepcopy(_TEST_TAGS_2)
  db.duplicates = fapdata.duplicates.Duplicates(
      copy.deepcopy(_DUPLICATES), copy.deepcopy(_DUPLICATES_INDEX))
  return db


_USERS: fapdata._UserType = {
    10: {
        'name': 'user-10',
        'date_albums': 1675368670,
        'date_finished': 1675368690,
        'date_audit': 0,
    },
}


_FAVORITES: fapdata._FavoriteType = {
    10: {
        20: {
            'date_blobs': 1675368670,
            'failed_images': {(110, 1675368670, '110.jpg', 'url-110')},
            'images': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            'name': 'fav-20',
            'pages': 1,
        },
        30: {
            'date_blobs': 1675368690,
            'failed_images': set(),
            'images': [104, 105, 106],
            'name': 'fav-30',
            'pages': 1,
        },
    },
}


_BLOBS: fapdata._BlobType = {  # type: ignore
    '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19': {
        'animated': False,
        'average': '303830301a1c387f',
        'date': 1675368670,
        'diff': '60e2c3c2d2b1e2ce',
        'ext': 'jpg',
        'gone': {},
        'height': 200,
        'loc': {(10, 20, 102): ('102.jpg', 'new')},
        'percept': 'cd4fc618316732e7',
        'sz': 54643,
        'sz_thumb': 54643,
        'tags': set(),
        'wavelet': '303838383a1f3e7f',
        'width': 168,
    },
    '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': {
        'animated': False,
        'average': 'ffffff9a180060c8',
        'date': 1675368670,
        'diff': '6854541633d5c991',
        'ext': 'png',
        'gone': {},
        'height': 173,
        'loc': {(10, 20, 108): ('108.png', 'new')},
        'percept': 'd99ee32e586716c8',
        'sz': 45309,
        'sz_thumb': 45309,
        'tags': set(),
        'wavelet': 'ffffbf88180060c8',
        'width': 130,
    },
    '4c49275f4bb6ed2fd502a51a0fc3b24661483c1aa9d4acc1dc91f035877df207': {
        'animated': False,
        'average': 'ffffff9a180060c8',
        'date': 1675368670,
        'diff': '6854541633d5c991',
        'ext': 'png',
        'gone': {},
        'height': 225,
        'loc': {(10, 20, 107): ('107.png', 'new')},
        'percept': 'd99ee32e586716c8',
        'sz': 72577,
        'sz_thumb': 72577,
        'tags': set(),
        'wavelet': 'ffffbf88180060c8',
        'width': 170,
    },
    '74bab8c9b692a582f7b90c27a0d80fe0a073f70991c1c8aa1815745127e5c449': {
        'animated': False,
        'average': '3e3c343e7c7c3800',
        'date': 1675368690,
        'diff': 'f0e0ece4f0d0f078',
        'ext': 'jpg',  # 104 is actually a JPG!
        'gone': {},
        'height': 200,
        'loc': {
            (10, 20, 104): ('104.png', 'new'),
            (10, 30, 104): ('104.png', 'new'),
        },
        'percept': 'c6867d8998cf626b',
        'sz': 48259,
        'sz_thumb': 48259,
        'tags': set(),
        'wavelet': '3e7c347e7c7c3800',
        'width': 154,
    },
    '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {
        'animated': False,
        'average': '98181c1cc8f0e000',
        'date': 1675368670,
        'diff': '303031359101c9cc',
        'ext': 'jpg',
        'gone': {},
        'height': 200,
        'loc': {(10, 20, 101): ('101.jpg', 'new')},
        'percept': 'd89c67e130f63e61',
        'sz': 39147,
        'sz_thumb': 39147,
        'tags': set(),
        'wavelet': 'dcbe1c1cd8f8f060',
        'width': 160,
    },
    'dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180': {
        'animated': False,
        'average': '091b5f7761323000',
        'date': 1675368670,
        'diff': '737394c5d3e66431',
        'ext': 'jpg',
        'gone': {},
        'height': 222,
        'loc': {
            (10, 20, 106): ('106.jpg', 'new'),
            (10, 30, 106): ('unknown', 'new'),
        },
        'percept': '89991f6f62a63479',
        'sz': 89216,
        'sz_thumb': 11890,
        'tags': set(),
        'wavelet': '091b7f7f71333018',
        'width': 300,
    },
    'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': {
        'animated': False,
        'average': '3838381810307078',
        'date': 1675368690,
        'diff': '626176372565c3f2',
        'ext': 'jpg',
        'gone': {},
        'height': 246,
        'loc': {
            (10, 20, 100): ('100.jpg', 'new'),
            (10, 20, 105): ('105.jpg', 'new'),
            (10, 30, 105): ('105.jpg', 'new'),
        },
        'percept': 'cc8fc37638703ee1',
        'sz': 56583,
        'sz_thumb': 56583,
        'tags': set(),
        'wavelet': '3e3f3f1b10307878',
        'width': 200,
    },
    'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e': {
        'animated': True,
        'average': 'ffffffffffffe7e7',
        'date': 1675368670,
        'diff': '000000000000080c',
        'ext': 'gif',
        'gone': {},
        'height': 100,
        'loc': {(10, 20, 109): ('109.gif', 'new')},
        'percept': 'e699669966739866',
        'sz': 444973,
        'sz_thumb': 302143,
        'tags': set(),
        'wavelet': 'ffffffffffffe7e7',
        'width': 500,
    },
    'ed257bbbcb316f05f852f80b705d0c911e8ee51c7962fa207962b40a653fd5f9': {
        'animated': False,
        'average': '183b3f7ffb030300',
        'date': 1675368670,
        'diff': 'b3e3e3e5d21e2603',
        'ext': 'jpg',
        'gone': {},
        'height': 199,
        'loc': {(10, 20, 103): ('103.jpg', 'new')},
        'percept': '8dce3a31783633cb',
        'sz': 43144,
        'sz_thumb': 43144,
        'tags': set(),
        'wavelet': '083f7f7ffb030300',
        'width': 158,
    },
}

_BLOBS_AUDITED: fapdata._BlobType = {  # type: ignore
    '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19': {
        'animated': False,
        'average': '303830301a1c387f',
        'date': 1675368670,
        'diff': '60e2c3c2d2b1e2ce',
        'ext': 'jpg',
        'gone': {
            102: (1676368670, fapdata._FailureLevel.URL_EXTRACTION,
                  'https://www.imagefap.com/photo/102/'),
        },
        'height': 200,
        'loc': {(10, 20, 102): ('102.jpg', 'new')},
        'percept': 'cd4fc618316732e7',
        'sz': 54643,
        'sz_thumb': 54643,
        'tags': set(),
        'wavelet': '303838383a1f3e7f',
        'width': 168,
    },
    '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': {
        'animated': False,
        'average': 'ffffff9a180060c8',
        'date': 1675368670,
        'diff': '6854541633d5c991',
        'ext': 'png',
        'gone': {
            108: (1676368670, fapdata._FailureLevel.IMAGE_PAGE,
                  'https://www.imagefap.com/photo/108/'),
        },
        'height': 173,
        'loc': {(10, 20, 108): ('108.png', 'new')},
        'percept': 'd99ee32e586716c8',
        'sz': 45309,
        'sz_thumb': 45309,
        'tags': set(),
        'wavelet': 'ffffbf88180060c8',
        'width': 130,
    },
    '4c49275f4bb6ed2fd502a51a0fc3b24661483c1aa9d4acc1dc91f035877df207': {
        'animated': False,
        'average': 'ffffff9a180060c8',
        'date': 1675368670,
        'diff': '6854541633d5c991',
        'ext': 'png',
        'gone': {
            107: (1676368670, fapdata._FailureLevel.FULL_RES, 'url-107'),
        },
        'height': 225,
        'loc': {(10, 20, 107): ('107.png', 'new')},
        'percept': 'd99ee32e586716c8',
        'sz': 72577,
        'sz_thumb': 72577,
        'tags': set(),
        'wavelet': 'ffffbf88180060c8',
        'width': 170,
    },
    '74bab8c9b692a582f7b90c27a0d80fe0a073f70991c1c8aa1815745127e5c449': {
        'animated': False,
        'average': '3e3c343e7c7c3800',
        'date': 1675368690,
        'diff': 'f0e0ece4f0d0f078',
        'ext': 'jpg',  # 104 is actually a JPG!
        'gone': {
            104: (1676368670, fapdata._FailureLevel.FULL_RES, 'url-104'),
        },
        'height': 200,
        'loc': {
            (10, 20, 104): ('104.png', 'new'),
            (10, 30, 104): ('104.png', 'new'),
        },
        'percept': 'c6867d8998cf626b',
        'sz': 48259,
        'sz_thumb': 48259,
        'tags': set(),
        'wavelet': '3e7c347e7c7c3800',
        'width': 154,
    },
    '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {
        'animated': False,
        'average': '98181c1cc8f0e000',
        'date': 1676368670,
        'diff': '303031359101c9cc',
        'ext': 'jpg',
        'gone': {},
        'height': 200,
        'loc': {(10, 20, 101): ('101.jpg', 'new')},
        'percept': 'd89c67e130f63e61',
        'sz': 39147,
        'sz_thumb': 39147,
        'tags': set(),
        'wavelet': 'dcbe1c1cd8f8f060',
        'width': 160,
    },
    'dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180': {
        'animated': False,
        'average': '091b5f7761323000',
        'date': 1675368670,
        'diff': '737394c5d3e66431',
        'ext': 'jpg',
        'gone': {
            106: (1676368670, fapdata._FailureLevel.URL_EXTRACTION,
                  'https://www.imagefap.com/photo/106/'),
        },
        'height': 222,
        'loc': {
            (10, 20, 106): ('106.jpg', 'new'),
            (10, 30, 106): ('unknown', 'new'),
        },
        'percept': '89991f6f62a63479',
        'sz': 89216,
        'sz_thumb': 11890,
        'tags': set(),
        'wavelet': '091b7f7f71333018',
        'width': 300,
    },
    'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': {
        'animated': False,
        'average': '3838381810307078',
        'date': 1676368670,
        'diff': '626176372565c3f2',
        'ext': 'jpg',
        'gone': {},
        'height': 246,
        'loc': {
            (10, 20, 100): ('100.jpg', 'new'),
            (10, 20, 105): ('105.jpg', 'new'),
            (10, 30, 105): ('105.jpg', 'new'),
        },
        'percept': 'cc8fc37638703ee1',
        'sz': 56583,
        'sz_thumb': 56583,
        'tags': set(),
        'wavelet': '3e3f3f1b10307878',
        'width': 200,
    },
    'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e': {
        'animated': True,
        'average': 'ffffffffffffe7e7',
        'date': 1675368670,
        'diff': '000000000000080c',
        'ext': 'gif',
        'gone': {
            109: (1676368670, fapdata._FailureLevel.URL_EXTRACTION,
                  'https://www.imagefap.com/photo/109/'),
        },
        'height': 100,
        'loc': {(10, 20, 109): ('109.gif', 'new')},
        'percept': 'e699669966739866',
        'sz': 444973,
        'sz_thumb': 302143,
        'tags': set(),
        'wavelet': 'ffffffffffffe7e7',
        'width': 500,
    },
    'ed257bbbcb316f05f852f80b705d0c911e8ee51c7962fa207962b40a653fd5f9': {
        'animated': False,
        'average': '183b3f7ffb030300',
        'date': 1675368670,
        'diff': 'b3e3e3e5d21e2603',
        'ext': 'jpg',
        'gone': {
            103: (1676368670, fapdata._FailureLevel.IMAGE_PAGE,
                  'https://www.imagefap.com/photo/103/'),
        },
        'height': 199,
        'loc': {(10, 20, 103): ('103.jpg', 'new')},
        'percept': '8dce3a31783633cb',
        'sz': 43144,
        'sz_thumb': 43144,
        'tags': set(),
        'wavelet': '083f7f7ffb030300',
        'width': 158,
    },
}

_INDEX: fapdata._ImagesIdIndexType = {
    100: 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e',
    101: '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
    102: '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19',
    103: 'ed257bbbcb316f05f852f80b705d0c911e8ee51c7962fa207962b40a653fd5f9',
    104: '74bab8c9b692a582f7b90c27a0d80fe0a073f70991c1c8aa1815745127e5c449',
    105: 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e',
    106: 'dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180',
    107: '4c49275f4bb6ed2fd502a51a0fc3b24661483c1aa9d4acc1dc91f035877df207',
    108: '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
    109: 'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e',
}

_DUPLICATES: fapdata.duplicates.DuplicatesType = {
    ('321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
     '4c49275f4bb6ed2fd502a51a0fc3b24661483c1aa9d4acc1dc91f035877df207'): {
        'sources': {
            'average': {
                ('321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
                 '4c49275f4bb6ed2fd502a51a0fc3b24661483c1aa9d4acc1dc91f035877df207'): 0,
            },
            'cnn': {
                ('321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
                 '4c49275f4bb6ed2fd502a51a0fc3b24661483c1aa9d4acc1dc91f035877df207'): 0.98712325,
            },
            'diff': {
                ('321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
                 '4c49275f4bb6ed2fd502a51a0fc3b24661483c1aa9d4acc1dc91f035877df207'): 0,
            },
            'percept': {
                ('321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
                 '4c49275f4bb6ed2fd502a51a0fc3b24661483c1aa9d4acc1dc91f035877df207'): 0,
            },
            'wavelet': {
                ('321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
                 '4c49275f4bb6ed2fd502a51a0fc3b24661483c1aa9d4acc1dc91f035877df207'): 0,
            },
        },
        'verdicts': {
            '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': 'new',
            '4c49275f4bb6ed2fd502a51a0fc3b24661483c1aa9d4acc1dc91f035877df207': 'new',
        },
    },
}

_DUPLICATES_INDEX: fapdata.duplicates.DuplicatesKeyIndexType = {
    '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': (
        '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
        '4c49275f4bb6ed2fd502a51a0fc3b24661483c1aa9d4acc1dc91f035877df207',
    ),
    '4c49275f4bb6ed2fd502a51a0fc3b24661483c1aa9d4acc1dc91f035877df207': (
        '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
        '4c49275f4bb6ed2fd502a51a0fc3b24661483c1aa9d4acc1dc91f035877df207',
    ),
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

_PRINTED_STATS_FULL = """
Database is located in '%s/imagefap.database', and is 23.34kb (2.674%% of total images size)
872.90kb total (unique) images size (38.23kb min, 434.54kb max, 96.99kb mean with 127.52kb standard deviation, 1 are animated)
Pixel size (width, height): 22.49k pixels min (130, 173), 66.60k pixels max (300, 222), 39.38k mean with 13.51k standard deviation
657.91kb total thumbnail size (11.61kb min, 295.06kb max, 73.10kb mean with 84.74kb standard deviation), 75.4%% of total images size

1 users
2 favorite galleries (oldest: 2023/Feb/02-20:11:10-UTC / newer: 2023/Feb/02-20:11:30-UTC)
9 unique images (13 total, 7 exact duplicates)
1 unique failed images in all user albums
0 unique images are now disappeared from imagefap site
0 perceptual duplicates in 0 groups
"""  # noqa: E501

_PRINTED_USERS_FULL = """
ID: USER_NAME
    FILE STATS FOR USER
    => ID: FAVORITE_NAME (IMAGE_COUNT / FAILED_COUNT / PAGE_COUNT / DATE DOWNLOAD)
           FILE STATS FOR FAVORITES

10: 'user-10'
    1.09Mb files size (38.23kb min, 434.54kb max, 85.97kb mean with 105.90kb standard deviation)
    => 20: 'fav-20' (10 / 1 / 1 / 2023/Feb/02-20:11:10-UTC)
           928.16kb files size (38.23kb min, 434.54kb max, 92.82kb mean with 120.95kb standard deviation)
    => 30: 'fav-30' (3 / 0 / 1 / 2023/Feb/02-20:11:30-UTC)
           189.51kb files size (47.13kb min, 87.12kb max, 63.17kb mean with 21.14kb standard deviation)
""".splitlines()[1:]  # noqa: E501

_PRINTED_BLOBS_FULL = """
SHA256_HASH: ID1/'NAME1' or ID2/'NAME2' or ..., PIXELS (WIDTH, HEIGHT) [ANIMATED]
    => {'TAG1', 'TAG2', ...}

0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19: user-10/fav-20/'102.jpg' (10/20/102), 33.60k (168, 200)
321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6: user-10/fav-20/'108.png' (10/20/108), 22.49k (130, 173)
4c49275f4bb6ed2fd502a51a0fc3b24661483c1aa9d4acc1dc91f035877df207: user-10/fav-20/'107.png' (10/20/107), 38.25k (170, 225)
74bab8c9b692a582f7b90c27a0d80fe0a073f70991c1c8aa1815745127e5c449: user-10/fav-20/'104.png' (10/20/104) + user-10/fav-30/'104.png' (10/30/104), 30.80k (154, 200)
9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf: user-10/fav-20/'101.jpg' (10/20/101), 32.00k (160, 200)
dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180: user-10/fav-20/'106.jpg' (10/20/106) + user-10/fav-30/'unknown' (10/30/106), 66.60k (300, 222)
    => {one (1)}
e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e: user-10/fav-20/'100.jpg' (10/20/100) + user-10/fav-20/'105.jpg' (10/20/105) + user-10/fav-30/'105.jpg' (10/30/105), 49.20k (200, 246)
ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e: user-10/fav-20/'109.gif' (10/20/109), 50.00k (500, 100) animated
ed257bbbcb316f05f852f80b705d0c911e8ee51c7962fa207962b40a653fd5f9: user-10/fav-20/'103.jpg' (10/20/103), 31.44k (158, 199)
""".splitlines()[1:]  # noqa: E501


SUITE = unittest.TestLoader().loadTestsFromTestCase(TestFapDatabase)


if __name__ == '__main__':
  unittest.main()
