#!/usr/bin/python3 -bb
#
# Copyright 2023 Daniel Balparda (balparda@gmail.com)
#
"""duplicated.py unittest."""

# import pdb
import unittest
from unittest import mock

import duplicates

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


class TestDuplicates(unittest.TestCase):
  """Tests for duplicates.py."""

  @mock.patch('duplicates.image_methods.PHash.encode_image')
  def test_Encode(self, mock_encode_image):
    """Test."""
    mock_encode_image.return_value = 'abc'
    dup = duplicates.Duplicates({})
    self.assertEqual(dup.Encode('path'), 'abc')
    self.assertListEqual(mock_encode_image.call_args_list, [mock.call(image_file='path')])

  @mock.patch('duplicates.image_methods.PHash.find_duplicates')
  def test_FindDuplicates(self, mock_find_duplicates):
    """Test."""
    mock_find_duplicates.return_value = _NEW_DUPLICATES
    dup = duplicates.Duplicates(_DUPLICATES_DICT_BEFORE)  # type: ignore
    self.assertSetEqual(dup.hashes, {'aaa', 'bbb', 'ccc', 'ddd', 'eee'})
    dup.FindDuplicates({'foo': 'bar'})
    self.assertListEqual(
        mock_find_duplicates.call_args_list, [mock.call(encoding_map={'foo': 'bar'})])
    self.assertDictEqual(dup.index, _DUPLICATES_DICT_AFTER)
    self.assertSetEqual(
        dup.hashes, {'aaa', 'bbb', 'ccc', 'ddd', 'eee', 'fff', 'ggg', 'xxx', 'yyy', 'zzz'})


_DUPLICATES_DICT_BEFORE = {
    ('aaa', 'bbb'): {
        'aaa': 'keep',
        'bbb': 'skip',
    },
    ('ccc', 'ddd', 'eee'): {
        'ccc': 'new',
        'ddd': 'false',
        'eee': 'false',
    },
}

_NEW_DUPLICATES = {
    'aaa': ['bbb'],
    'ddd': ['ccc', 'eee', 'fff', 'ggg'],
    'xxx': ['yyy', 'zzz'],
}

_DUPLICATES_DICT_AFTER = {
    ('aaa', 'bbb'): {
        'aaa': 'keep',
        'bbb': 'skip',
    },
    ('ccc', 'ddd', 'eee', 'fff', 'ggg'): {
        'ccc': 'new',
        'ddd': 'false',
        'eee': 'false',
        'fff': 'new',
        'ggg': 'new',
    },
    ('xxx', 'yyy', 'zzz'): {
        'xxx': 'new',
        'yyy': 'new',
        'zzz': 'new',
    },
}


SUITE = unittest.TestLoader().loadTestsFromTestCase(TestDuplicates)


if __name__ == '__main__':
  unittest.main()
