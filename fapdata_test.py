#!/usr/bin/python3 -bb
#
# Copyright 2023 Daniel Balparda (balparda@gmail.com)
#
"""fapdata.py unittest."""

# import pdb
import unittest
# from unittest import mock

from baselib import base
import fapdata

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


class TestFapDatabase(unittest.TestCase):
  """Tests for fapdata.py."""

  def test_GetTag(self):
    """Test."""
    db = fapdata.FapDatabase('/foo/')
    db._db['tags'] = _TEST_TAGS_1
    self.assertListEqual(db._GetTag(0), [(0, 'plain')])
    self.assertListEqual(db._GetTag(2), [(2, 'two')])
    self.assertListEqual(db._GetTag(22), [(2, 'two'), (22, 'two-two')])
    self.assertListEqual(db._GetTag(24), [(2, 'two'), (24, 'two-four')])
    self.assertListEqual(db._GetTag(246), [(2, 'two'), (24, 'two-four'), (246, 'deep')])
    with self.assertRaisesRegex(base.Error, r'tag 11 is empty'):
      db._GetTag(11)
    with self.assertRaisesRegex(base.Error, r'tag 3 \(of 33\) is empty'):
      db._GetTag(33)

  def test_TagsWalk(self):
    """Test."""
    db = fapdata.FapDatabase('/foo/')
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
