#!/usr/bin/python3 -bb
#
# Copyright 2023 Daniel Balparda (balparda@gmail.com)
#
# cspell:disable-next-line
# Image testdata/109.gif authored by Charly Whisky, creative commons attribution.
# (Found in https://en.wikipedia.org/wiki/File:Dopplerfrequenz.gif)
#
"""fapdata.py unittest."""

import hashlib
import os
import os.path
# import pdb
import tempfile
from typing import Union
import unittest
from unittest import mock

import fapdata

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


_TESTDATA_PATH = os.path.join(os.path.dirname(__file__), 'testdata/')


class TestFapDatabase(unittest.TestCase):
  """Tests for fapdata.py."""

  @mock.patch('fapdata.os.path.isdir')
  @mock.patch('fapdata.os.mkdir')
  @mock.patch('fapdata.os.path.expanduser')
  def test_Constructor(self, mock_expanduser, mock_mkdir, mock_is_dir):
    """Test."""
    mock_is_dir.return_value = False
    del os.environ['IMAGEFAP_FAVORITES_DB_PATH']
    mock_expanduser.return_value = '/home/some-user/Downloads/some-dir/'
    db = fapdata.FapDatabase('~/Downloads/some-dir/')
    self.assertListEqual(
        mock_mkdir.call_args_list, [mock.call('/home/some-user/Downloads/some-dir/')])
    self.assertEqual(db._original_dir, '~/Downloads/some-dir/')
    self.assertEqual(os.environ['IMAGEFAP_FAVORITES_DB_PATH'], '~/Downloads/some-dir/')
    self.assertEqual(db._db_dir, '/home/some-user/Downloads/some-dir/')
    self.assertEqual(db._db_path, '/home/some-user/Downloads/some-dir/imagefap.database')
    self.assertEqual(db._blobs_dir, '/home/some-user/Downloads/some-dir/blobs/')
    self.assertDictEqual(db._db, {k: {} for k in fapdata._DB_MAIN_KEYS})
    self.assertDictEqual(db.duplicates.index, {})
    db.users[1] = 'Luke'
    db.favorites[1] = {2: {}}
    db.tags[3] = {'name': 'three'}
    db.blobs['sha1'] = {'tags': {4}}
    db.image_ids_index[5] = 'sha2'
    db.duplicates_index[('a', 'b')] = {'a': 'new'}
    self.assertDictEqual(db._db, {
        'users': {1: 'Luke'},
        'favorites': {1: {2: {}}},
        'tags': {3: {'name': 'three'}},
        'blobs': {'sha1': {'tags': {4}}},
        'image_ids_index': {5: 'sha2'},
        'duplicates_index': {('a', 'b'): {'a': 'new'}},
    })
    self.assertDictEqual(db.duplicates.index, {('a', 'b'): {'a': 'new'}})
    del os.environ['IMAGEFAP_FAVORITES_DB_PATH']

  @mock.patch('fapdata.os.path.isdir')
  def test_Constructor_Fail(self, mock_is_dir):
    """Test."""
    mock_is_dir.return_value = False
    with self.assertRaises(fapdata.Error):
      fapdata.FapDatabase('/yyy/', create_if_needed=False)
    with self.assertRaises(AttributeError):
      fapdata.FapDatabase('')

  @mock.patch('fapdata.os.path.isdir')
  def test_GetTag(self, mock_is_dir):
    """Test."""
    mock_is_dir.return_value = True
    db = fapdata.FapDatabase('/xxx/')
    db._db['tags'] = _TEST_TAGS_1
    self.assertListEqual(db.GetTag(0), [(0, 'plain', {'name': 'plain'})])
    self.assertListEqual(db.GetTag(2), [(2, 'two', _TEST_TAGS_1[2])])
    self.assertEqual(db.PrintableTag(2), 'two')
    self.assertListEqual(
        db.GetTag(22),
        [(2, 'two', _TEST_TAGS_1[2]), (22, 'two-two', {'name': 'two-two', 'tags': {}})])
    self.assertListEqual(
        db.GetTag(24),
        [(2, 'two', _TEST_TAGS_1[2]),
         (24, 'two-four', {'name': 'two-four', 'tags': {246: {'name': 'deep'}}})])
    self.assertEqual(db.PrintableTag(24), 'two/two-four')
    self.assertListEqual(
        db.GetTag(246),
        [(2, 'two', _TEST_TAGS_1[2]),
         (24, 'two-four', {'name': 'two-four', 'tags': {246: {'name': 'deep'}}}),
         (246, 'deep', {'name': 'deep'})])
    self.assertEqual(db.PrintableTag(246), 'two/two-four/deep')
    with self.assertRaisesRegex(fapdata.Error, r'tag 11 is empty'):
      db.GetTag(11)
    with self.assertRaisesRegex(fapdata.Error, r'tag 3 \(of 33\) is empty'):
      db.GetTag(33)

  @mock.patch('fapdata.os.path.isdir')
  def test_TagsWalk(self, mock_is_dir):
    """Test."""
    mock_is_dir.return_value = True
    db = fapdata.FapDatabase('/xxx/')
    db._db['tags'] = _TEST_TAGS_2
    self.assertListEqual(
        list((i, n, d) for i, n, d, _ in db.TagsWalk()),
        [(0, 'plain', 0),
         (1, 'one', 0), (11, 'one-one', 1),
         (2, 'two', 0), (22, 'two-two', 1), (24, 'two-four', 1), (246, 'deep', 2),
         (3, 'three', 0), (33, 'three-three', 1)])
    self.assertListEqual(
        list((i, n, d) for i, n, d, _ in db.TagsWalk(start_tag=_TEST_TAGS_2[2]['tags'])),
        [(22, 'two-two', 0), (24, 'two-four', 0), (246, 'deep', 1)])
    db.PrintTags()

  @mock.patch('fapdata.os.path.isdir')
  @mock.patch('fapdata._FapHTMLRead')
  def test_AddUserByID(self, mock_read, mock_is_dir):
    """Test."""
    mock_is_dir.return_value = True
    fapdata._FIND_NAME_IN_FAVORITES = _MockRegex({'user_html': ['foo &amp; user'], 'invalid': []})
    db = fapdata.FapDatabase('/xxx/')
    mock_read.return_value = 'invalid'
    with self.assertRaisesRegex(fapdata.Error, r'for 11'):
      db.AddUserByID(11)
    mock_read.return_value = 'user_html'
    self.assertEqual(db.AddUserByID(10), 'foo & user')
    self.assertDictEqual(db.users, {10: 'foo & user'})
    fapdata._FIND_NAME_IN_FAVORITES = None  # make sure is not used again in next call
    self.assertEqual(db.AddUserByID(10), 'foo & user')
    self.assertListEqual(
        mock_read.call_args_list,
        [mock.call('https://www.imagefap.com/showfavorites.php?userid=11&page=0'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=0')])

  @mock.patch('fapdata.os.path.isdir')
  @mock.patch('fapdata._FapHTMLRead')
  def test_AddUserByName(self, mock_read, mock_is_dir):
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
    self.assertDictEqual(db.users, {10: 'foo & user'})
    fapdata._FIND_USER_ID_RE = None  # make sure is not used again in next call
    fapdata._FIND_ACTUAL_NAME = None
    self.assertTupleEqual(db.AddUserByName('foo & user'), (10, 'foo & user'))
    self.assertListEqual(
        mock_read.call_args_list,
        [mock.call('https://www.imagefap.com/profile/no-user'),
         mock.call('https://www.imagefap.com/profile/no-user'),
         mock.call('https://www.imagefap.com/profile/foo-user')])

  @mock.patch('fapdata.os.path.isdir')
  @mock.patch('fapdata._FapHTMLRead')
  def test_AddFolderByID(self, mock_read, mock_is_dir):
    """Test."""
    mock_is_dir.return_value = True
    fapdata._FIND_NAME_IN_FOLDER = _MockRegex({'folder_html': ['foo &amp; folder'], 'invalid': []})
    fapdata._FIND_ONLY_IN_PICTURE_FOLDER = _MockRegex({'folder_html': ['true']})
    fapdata._FIND_ONLY_IN_GALLERIES_FOLDER = _MockRegex({'folder_html': []})
    db = fapdata.FapDatabase('/xxx/')
    mock_read.return_value = 'invalid'
    with self.assertRaisesRegex(fapdata.Error, r'for 11/22'):
      db.AddFolderByID(11, 22)
    mock_read.return_value = 'folder_html'
    self.assertEqual(db.AddFolderByID(10, 20), 'foo & folder')
    self.assertDictEqual(
        db.favorites,
        {10: {20: {'date_blobs': 0, 'date_straight': 0, 'images': [],
                   'name': 'foo & folder', 'pages': 0}}})
    fapdata._FIND_NAME_IN_FOLDER = None  # make sure is not used again in next call
    fapdata._FIND_ONLY_IN_PICTURE_FOLDER = None
    fapdata._FIND_ONLY_IN_GALLERIES_FOLDER = None
    self.assertEqual(db.AddFolderByID(10, 20), 'foo & folder')
    self.assertListEqual(
        mock_read.call_args_list,
        [mock.call('https://www.imagefap.com/showfavorites.php?userid=11&page=0&folderid=22'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=0&folderid=20'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=0&folderid=20')])

  @mock.patch('fapdata.os.path.isdir')
  @mock.patch('fapdata._FapHTMLRead')
  def test_AddFolderByName(self, mock_read, mock_is_dir):
    """Test."""
    mock_is_dir.return_value = True
    fapdata._FIND_FOLDERS = _MockRegex({
        'folder_html_1': [('100', 'no1')], 'folder_html_2': [('200', 'no2'), ('300', 'no3')],
        'folder_html_3': [('400', 'foo &amp; folder'), ('500', 'no5')], 'invalid': []})
    fapdata._FIND_ONLY_IN_PICTURE_FOLDER = _MockRegex({'folder_html_test': ['true']})
    fapdata._FIND_ONLY_IN_GALLERIES_FOLDER = _MockRegex({'folder_html_test': []})
    db = fapdata.FapDatabase('/xxx/')
    mock_read.return_value = 'invalid'
    with self.assertRaisesRegex(fapdata.Error, r'folder \'no-folder\' for user 11'):
      db.AddFolderByName(11, 'no-folder')
    mock_read.side_effect = ['folder_html_1', 'folder_html_2', 'folder_html_3', 'folder_html_test']
    self.assertTupleEqual(db.AddFolderByName(10, 'foo & folder'), (400, 'foo & folder'))
    self.assertDictEqual(
        db.favorites,
        {10: {400: {'date_blobs': 0, 'date_straight': 0, 'images': [],
                    'name': 'foo & folder', 'pages': 0}}})
    fapdata._FIND_NAME_IN_FOLDER = None  # make sure is not used again in next call
    fapdata._FIND_ONLY_IN_PICTURE_FOLDER = None
    fapdata._FIND_ONLY_IN_GALLERIES_FOLDER = None
    self.assertTupleEqual(db.AddFolderByName(10, 'foo & folder'), (400, 'foo & folder'))
    self.assertListEqual(
        mock_read.call_args_list,
        [mock.call('https://www.imagefap.com/showfavorites.php?userid=11&page=0'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=0'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=1'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=2'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=0&folderid=400')])

  @mock.patch('fapdata._FapHTMLRead')
  @mock.patch('fapdata._FapBinRead')
  def test_Read(self, read_bin, read_html):
    """Test."""
    self.maxDiff = None
    fapdata.base.INT_TIME = lambda: 1675368670  # 02/feb/2023 20:11
    with tempfile.TemporaryDirectory() as db_path:
      # do the dance that does not depend on any mocking at all
      with self.assertRaises(fapdata.Error):
        fapdata.GetDatabaseTimestamp(db_path)
      db = fapdata.FapDatabase(db_path)
      db._db['users'] = {1: 'Luke', 2: 'Ben'}
      db._db['favorites'] = {1: {11: {
          'name': 'known-folder-1', 'pages': 8,
          'date_straight': 0, 'date_blobs': 1675360670, 'images': [103, 104]}}}
      db.Save()
      self.assertTrue(fapdata.GetDatabaseTimestamp(db_path) > 1600000000)
      del db
      db = fapdata.FapDatabase(db_path)
      db.Load()
      db.PrintStats()
      db.PrintUsersAndFavorites()
      db.PrintTags()
      db.PrintBlobs()
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
      self.assertSetEqual(db.AddAllUserFolders(1), {10, 11, 13})
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
          10: {'name': 'new-f-0', 'date_blobs': 0, 'date_straight': 0, 'images': [], 'pages': 0},
          11: {'name': 'known-folder-1', 'date_blobs': 1675360670, 'date_straight': 0,
               'images': [103, 104], 'pages': 8},
          13: {'name': 'new&f-3', 'date_blobs': 0, 'date_straight': 0, 'images': [], 'pages': 0}}})
      fapdata._FIND_FOLDERS = None  # set to None for safety
      fapdata._FIND_ONLY_IN_PICTURE_FOLDER = None
      fapdata._FIND_ONLY_IN_GALLERIES_FOLDER = None
      # AddFolderPics ##############################################################################
      db.favorites[1][10]['pages'] = 9  # this will help test the backtracking
      db.favorites[1][10]['images'] = [100]
      read_html.side_effect = [
          'img-page-10-8', 'img-page-10-7',                   # backtrack on favorites 10
          'img-page-10-7', 'img-page-10-8', 'img-page-10-9',  # then forward
          'img-page-13-0', 'img-page-13-1', 'img-page-13-2']
      fapdata._FAVORITE_IMAGE = _MockRegex({
          'img-page-10-7': ['100', '101'], 'img-page-10-8': ['102'], 'img-page-10-9': [],
          'img-page-13-0': ['105', '106'], 'img-page-13-1': ['107', '108', '109'],
          'img-page-13-2': []})
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
           mock.call('https://www.imagefap.com/showfavorites.php?userid=1&page=0&folderid=13'),
           mock.call('https://www.imagefap.com/showfavorites.php?userid=1&page=1&folderid=13'),
           mock.call('https://www.imagefap.com/showfavorites.php?userid=1&page=2&folderid=13')])
      read_html.reset_mock(side_effect=True)  # reset calls and side_effect
      self.assertDictEqual(db.favorites, {1: {
          10: {'name': 'new-f-0', 'date_blobs': 0, 'date_straight': 0,
               'images': [100, 101, 102], 'pages': 9},
          11: {'name': 'known-folder-1', 'date_blobs': 1675360670, 'date_straight': 0,
               'images': [103, 104], 'pages': 8},
          13: {'name': 'new&f-3', 'date_blobs': 0, 'date_straight': 0,
               'images': [105, 106, 107, 108, 109], 'pages': 2}}})
      fapdata._FAVORITE_IMAGE = None  # set to None for safety
      # ReadFavoritesIntoBlobs #####################################################################
      db._db['blobs'] = {
          '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {
              'loc': {(801, 'url-1', 'some-name.jpg', 2, 20),
                      (101, 'url-2', 'name-to-use.jpg', 1, 10)},
              'tags': {}, 'sz': 101, 'sz_thumb': 0, 'ext': 'jpg', 'percept': 'd99ee32e586716c8',
              'width': 160, 'height': 200, 'animated': False},
          'sha-107': {
              'loc': {(107, 'url-1', 'some-name.gif', 2, 20)},
              'tags': {}, 'sz': 107, 'sz_thumb': 0, 'ext': 'jpg', 'percept': 'd99ee32e586716c8',
              'width': 107, 'height': 1070, 'animated': False},
      }
      db._db['image_ids_index'] = {
          101: '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
          801: '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf', 107: 'sha-107'}
      read_html.side_effect = ['img-100', 'img-102', 'img-105', 'img-106',
                               'img-107', 'img-108', 'img-109']
      test_images = {}
      for n in ('100.jpg', '101.jpg', '102.jpg', '103.jpg', '104.jpg',
                '105.jpg', '106.jpg', '107.png', '108.png', '109.gif'):
        with open(os.path.join(_TESTDATA_PATH, n), 'rb') as f:
          test_images[n] = f.read()
      os.mkdir(os.path.join(db_path, 'blobs/'))
      with open(db._BlobPath(hashlib.sha256(test_images['101.jpg']).hexdigest()), 'wb') as f:
        f.write(test_images['101.jpg'])
      read_bin.side_effect = [
          test_images['100.jpg'], test_images['102.jpg'], test_images['105.jpg'],
          test_images['106.jpg'], test_images['107.png'], test_images['108.png'],
          test_images['109.gif']]
      fapdata._FULL_IMAGE = _MockRegex({
          'img-100': ['url-100'], 'img-102': ['url-102'], 'img-105': ['url-105'],
          'img-106': ['url-106'], 'img-107': ['url-107'], 'img-108': ['url-108'],
          'img-109': ['url-109']})
      fapdata._IMAGE_NAME = _MockRegex({
          'img-100': ['name-100.jpg'], 'img-102': ['name-102.jpg'], 'img-105': ['name-105.jpeg'],
          'img-106': ['name-106.jpeg'], 'img-107': ['name-107.png'], 'img-108': ['name-108.png'],
          'img-109': ['name-109.gif']})
      self.assertEqual(db.ReadFavoritesIntoBlobs(1, 10, 2, False), 111226)
      self.assertEqual(db.ReadFavoritesIntoBlobs(1, 11, 2, False), 0)
      self.assertEqual(db.ReadFavoritesIntoBlobs(1, 13, 2, False), 652075)
      db.FindDuplicates()
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
      self.assertDictEqual(db.blobs, _BLOBS)
      self.assertDictEqual(db.image_ids_index, _INDEX)
      self.assertDictEqual(db.duplicates.index, _DUPLICATES)
      self.assertTrue(os.path.exists(db._BlobPath(
          '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6')))
      self.assertTrue(os.path.exists(db.ThumbnailPath(
          '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6')))
      fapdata._FAVORITE_IMAGE = None  # set to None for safety
      ##############################################################################################
      db.GetBlob('9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf')
      db.GetBlob('321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6')
      db.PrintStats()
      db.PrintUsersAndFavorites()
      db.PrintTags()
      db.PrintBlobs()


class _MockRegex:

  def __init__(self, return_values: dict[str, list[Union[str, tuple[str, ...]]]]):
    self._return_values = return_values

  def findall(self, query: str) -> list[Union[str, tuple[str, ...]]]:
    return self._return_values[query]


_BLOBS = {
    '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19': {
        'animated': False, 'ext': 'jpg', 'height': 200,
        'loc': {(102, 'url-102', 'name-102.jpg', 1, 10)},
        'percept': 'cd4fc618316732e7', 'sz': 54643, 'sz_thumb': 54643, 'tags': set(), 'width': 168,
    },
    '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': {
        'animated': False, 'ext': 'png', 'height': 173,
        'loc': {(108, 'url-108', 'name-108.png', 1, 13)},
        'percept': 'd99ee32e586716c8', 'sz': 45309, 'sz_thumb': 45309, 'tags': set(), 'width': 130,
    },
    '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {
        'animated': False, 'ext': 'jpg', 'height': 200,
        'loc': {(101, 'url-2', 'name-to-use.jpg', 1, 10), (801, 'url-1', 'some-name.jpg', 2, 20)},
        'percept': 'd99ee32e586716c8', 'sz': 101, 'sz_thumb': 0, 'tags': {}, 'width': 160,
    },
    'dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180': {
        'animated': False, 'ext': 'jpg', 'height': 222,
        'loc': {(106, 'url-106', 'name-106.jpg', 1, 13)},
        'percept': '89991f6f62a63479', 'sz': 89216, 'sz_thumb': 11890, 'tags': set(), 'width': 300,
    },
    'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': {
        'animated': False, 'ext': 'jpg', 'height': 246,
        'loc': {(100, 'url-100', 'name-100.jpg', 1, 10), (105, 'url-105', 'name-105.jpg', 1, 13)},
        'percept': 'cc8fc37638703ee1', 'sz': 56583, 'sz_thumb': 56583, 'tags': set(), 'width': 200,
    },
    'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e': {
        'animated': True, 'ext': 'gif', 'height': 100, 'tags': set(),
        'loc': {(109, 'url-109', 'name-109.gif', 1, 13)},
        'percept': 'e699669966739866', 'sz': 444973, 'sz_thumb': 302143, 'width': 500},
    'sha-107': {
        'animated': False, 'ext': 'jpg', 'height': 1070,
        'loc': {(107, 'url-1', 'some-name.gif', 2, 20), (107, 'url-107', 'name-107.png', 1, 13)},
        'percept': 'd99ee32e586716c8', 'sz': 107, 'sz_thumb': 72577, 'tags': {}, 'width': 107,
    },
}

_INDEX = {
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

_DUPLICATES = {
    ('321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
     '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
     'sha-107'): {
        '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': 'new',
        '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': 'new',
        'sha-107': 'new',
    },
}

_TEST_TAGS_1 = {  # this has many places where there are missing keys
    0: {
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

_TEST_TAGS_2 = {  # this is all valid tags structure
    0: {
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


SUITE = unittest.TestLoader().loadTestsFromTestCase(TestFapDatabase)


if __name__ == '__main__':
  unittest.main()
