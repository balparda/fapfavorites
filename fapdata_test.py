#!/usr/bin/python3 -bb
#
# Copyright 2023 Daniel Balparda (balparda@gmail.com)
#
"""fapdata.py unittest."""

# import pdb
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
