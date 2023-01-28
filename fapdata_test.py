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
    db._db['tags'] = _TEST_TAGS
    self.assertListEqual(db.GetTag(0), [(0, 'plain')])
    self.assertListEqual(db.GetTag(2), [(2, 'two')])
    self.assertListEqual(db.GetTag(22), [(2, 'two'), (22, 'two-two')])
    self.assertListEqual(db.GetTag(24), [(2, 'two'), (24, 'two-four')])
    self.assertListEqual(db.GetTag(246), [(2, 'two'), (24, 'two-four'), (246, 'deep')])
    with self.assertRaisesRegex(base.Error, r'tag 11 is empty'):
      db.GetTag(11)
    with self.assertRaisesRegex(base.Error, r'tag 3 \(of 33\) is empty'):
      db.GetTag(33)


_TEST_TAGS = {
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


SUITE = unittest.TestLoader().loadTestsFromTestCase(TestFapDatabase)


if __name__ == '__main__':
  unittest.main()
