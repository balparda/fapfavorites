#!/usr/bin/python3 -bb
#
# Copyright 2023 Daniel Balparda (balparda@gmail.com)
#
"""fapdata.py unittest."""

# import pdb
from typing import Union
import unittest
from unittest import mock

import fapdata

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


class TestFapDatabase(unittest.TestCase):
  """Tests for fapdata.py."""

  @mock.patch('fapdata.os.path.isdir')
  @mock.patch('fapdata.os.mkdir')
  @mock.patch('fapdata.os.path.expanduser')
  def test_Constructor(self, mock_expanduser, mock_mkdir, mock_is_dir):
    """Test."""
    mock_is_dir.return_value = False
    mock_expanduser.return_value = '/home/some-user/Downloads/some-dir/'
    db = fapdata.FapDatabase('~/Downloads/some-dir/')
    self.assertListEqual(
        mock_mkdir.call_args_list, [mock.call('/home/some-user/Downloads/some-dir/')])
    self.assertEqual(db._original_dir, '~/Downloads/some-dir/')
    self.assertEqual(db._db_dir, '/home/some-user/Downloads/some-dir/')
    self.assertEqual(db._db_path, '/home/some-user/Downloads/some-dir/imagefap.database')
    self.assertEqual(db._blobs_dir, '/home/some-user/Downloads/some-dir/blobs/')
    self.assertDictEqual(db._db, {k: {} for k in fapdata._DB_MAIN_KEYS})
    self.assertDictEqual(db._duplicates._index, {})
    db._users[1] = 'Luke'
    db._favorites[1] = {2: {}}
    db._tags[3] = {'name': 'three'}
    db._blobs['sha1'] = {'tags': {4}}
    db._image_ids_index[5] = 'sha2'
    db._duplicates_index[('a', 'b')] = {'a': 'new'}
    self.assertDictEqual(db._db, {
        'users': {1: 'Luke'},
        'favorites': {1: {2: {}}},
        'tags': {3: {'name': 'three'}},
        'blobs': {'sha1': {'tags': {4}}},
        'image_ids_index': {5: 'sha2'},
        'duplicates_index': {('a', 'b'): {'a': 'new'}},
    })
    self.assertDictEqual(db._duplicates._index, {('a', 'b'): {'a': 'new'}})

  @mock.patch('fapdata.os.path.isdir')
  def test_Constructor_Fail(self, mock_is_dir):
    """Test."""
    mock_is_dir.return_value = False
    with self.assertRaises(fapdata.base.Error):
      fapdata.FapDatabase('/yyy/', create_if_needed=False)
    with self.assertRaises(AttributeError):
      fapdata.FapDatabase('')

  @mock.patch('fapdata.os.path.isdir')
  def test_GetTag(self, mock_is_dir):
    """Test."""
    mock_is_dir.return_value = True
    db = fapdata.FapDatabase('/xxx/')
    db._db['tags'] = _TEST_TAGS_1
    self.assertListEqual(db._GetTag(0), [(0, 'plain')])
    self.assertListEqual(db._GetTag(2), [(2, 'two')])
    self.assertListEqual(db._GetTag(22), [(2, 'two'), (22, 'two-two')])
    self.assertListEqual(db._GetTag(24), [(2, 'two'), (24, 'two-four')])
    self.assertListEqual(db._GetTag(246), [(2, 'two'), (24, 'two-four'), (246, 'deep')])
    with self.assertRaisesRegex(fapdata.base.Error, r'tag 11 is empty'):
      db._GetTag(11)
    with self.assertRaisesRegex(fapdata.base.Error, r'tag 3 \(of 33\) is empty'):
      db._GetTag(33)

  @mock.patch('fapdata.os.path.isdir')
  def test_TagsWalk(self, mock_is_dir):
    """Test."""
    mock_is_dir.return_value = True
    db = fapdata.FapDatabase('/xxx/')
    db._db['tags'] = _TEST_TAGS_2
    self.assertListEqual(
        list((i, n, d) for i, n, d, _ in db._TagsWalk()),
        [(0, 'plain', 0),
         (1, 'one', 0), (11, 'one-one', 1),
         (2, 'two', 0), (22, 'two-two', 1), (24, 'two-four', 1), (246, 'deep', 2),
         (3, 'three', 0), (33, 'three-three', 1)])
    self.assertListEqual(
        list((i, n, d) for i, n, d, _ in db._TagsWalk(start_tag=_TEST_TAGS_2[2]['tags'])),
        [(22, 'two-two', 0), (24, 'two-four', 0), (246, 'deep', 1)])

  @mock.patch('fapdata.os.path.isdir')
  @mock.patch('fapdata._FapHTMLRead')
  def test_AddUserByID(self, mock_read, mock_is_dir):
    """Test."""
    mock_is_dir.return_value = True
    fapdata._FIND_NAME_IN_FAVORITES = _MockRegex({'user_html': ['foo &amp; user'], 'invalid': []})
    db = fapdata.FapDatabase('/xxx/')
    mock_read.return_value = 'invalid'
    with self.assertRaisesRegex(fapdata.base.Error, r'for 11'):
      db.AddUserByID(11)
    mock_read.return_value = 'user_html'
    self.assertEqual(db.AddUserByID(10), 'foo & user')
    self.assertDictEqual(db._users, {10: 'foo & user'})
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
    with self.assertRaisesRegex(fapdata.base.Error, r'ID for user \'no-user\''):
      db.AddUserByName('no-user')
    fapdata._FIND_USER_ID_RE = _MockRegex({'user_html': ['10'], 'invalid': ['12']})
    with self.assertRaisesRegex(fapdata.base.Error, r'display name for user \'no-user\''):
      db.AddUserByName('no-user')
    mock_read.return_value = 'user_html'
    self.assertTupleEqual(db.AddUserByName('foo-user'), (10, 'foo & user'))
    self.assertDictEqual(db._users, {10: 'foo & user'})
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
    with self.assertRaisesRegex(fapdata.base.Error, r'for 11/22'):
      db.AddFolderByID(11, 22)
    mock_read.return_value = 'folder_html'
    self.assertEqual(db.AddFolderByID(10, 20), 'foo & folder')
    self.assertDictEqual(
        db._favorites,
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
    with self.assertRaisesRegex(fapdata.base.Error, r'folder \'no-folder\' for user 11'):
      db.AddFolderByName(11, 'no-folder')
    mock_read.side_effect = ['folder_html_1', 'folder_html_2', 'folder_html_3', 'folder_html_test']
    self.assertTupleEqual(db.AddFolderByName(10, 'foo & folder'), (400, 'foo & folder'))
    self.assertDictEqual(
        db._favorites,
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


class _MockRegex():

  def __init__(self, return_values: dict[str, list[Union[str, tuple[str, ...]]]]):
    self._return_values = return_values

  def findall(self, query: str) -> list[Union[str, tuple[str, ...]]]:
    return self._return_values[query]


# to mock
# open(): _GetBlob, _SaveImage, _GetBinary.PILImage.open
# urlopen: _LimpingURLRead.urlopen (_FapHTMLRead, _FapBinRead)
# tempfile.NamedTemporaryFile: write, flush, name
# os: os.path.isdir: Constructor, blobs_dir_exists
# os.path.exists: Load, _HasBlob, _DownloadAll
# os.path.getsize: PrintStats
# os.mkdir: ReadFavoritesIntoBlobs

# to monkeypatch
# base.INT_TIME
# _FIND_ONLY_IN_PICTURE_FOLDER = re.compile(r'<\/a><\/td><\/tr>\s+<\/table>\s+<table')
# _FIND_ONLY_IN_GALLERIES_FOLDER = re.compile(
# _FIND_NAME_IN_FAVORITES = re.compile(
# _FIND_USER_ID_RE = re.compile(  # cspell:disable-next-line
# _FIND_ACTUAL_NAME = re.compile(r'<td\s+class=.blk_profile_hdr.*>(.*)\sProfile\s+<\/td>')
# _FIND_NAME_IN_FOLDER = re.compile(
# _FIND_FOLDERS = re.compile(
# _FAVORITE_IMAGE = re.compile(r'<td\s+class=.blk_favorites.\s+id="img-([0-9]+)"\s+align=')
# _FULL_IMAGE = re.compile(
# _IMAGE_NAME = re.compile(


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
