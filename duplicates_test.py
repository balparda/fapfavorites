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
  def test_Encode(self, mock_encode_image: mock.MagicMock) -> None:
    """Test."""
    mock_encode_image.return_value = 'abc'
    dup = duplicates.Duplicates({}, {})
    self.assertEqual(dup.Encode('path'), 'abc')
    self.assertListEqual(mock_encode_image.call_args_list, [mock.call(image_file='path')])

  @mock.patch('duplicates.image_methods.PHash.find_duplicates')
  def test_FindDuplicates(self, mock_find_duplicates: mock.MagicMock) -> None:
    """Test."""
    mock_find_duplicates.return_value = _NEW_DUPLICATES
    dup = duplicates.Duplicates(_DUPLICATES_DICT_BEFORE, _DUPLICATES_INDEX_BEFORE)
    dup.FindDuplicates({'foo': 'bar'})
    self.assertListEqual(
        mock_find_duplicates.call_args_list, [mock.call(encoding_map={'foo': 'bar'})])
    self.assertDictEqual(dup.registry, _DUPLICATES_DICT_AFTER)
    self.assertDictEqual(dup.index, _DUPLICATES_INDEX_AFTER)

  def test_TrimDeletedBlob(self) -> None:
    """Test."""
    self.maxDiff = None
    dup = duplicates.Duplicates(_DUPLICATES_DICT_AFTER, _DUPLICATES_INDEX_AFTER)
    dup.registry[('ccc', 'ddd', 'eee', 'fff', 'ggg', 'hhh')]['verdicts']['fff'] = 'keep'
    dup.registry[('ccc', 'ddd', 'eee', 'fff', 'ggg', 'hhh')]['verdicts']['ggg'] = 'skip'
    dup.registry[('ccc', 'ddd', 'eee', 'fff', 'ggg', 'hhh')]['verdicts']['hhh'] = 'false'
    self.assertTrue(dup.TrimDeletedBlob('bbb'))
    self.assertFalse(dup.TrimDeletedBlob('eee'))
    self.assertFalse(dup.TrimDeletedBlob('jjj'))
    self.assertFalse(dup.TrimDeletedBlob('zzz'))
    self.assertTrue(dup.TrimDeletedBlob('xxx'))
    self.assertFalse(dup.TrimDeletedBlob('mmm'))  # key not in index
    self.assertDictEqual(dup.registry, _DUPLICATES_DICT_TRIMMED)
    self.assertDictEqual(dup.index, _DUPLICATES_INDEX_TRIMMED)


_DUPLICATES_DICT_BEFORE: duplicates.DuplicatesType = {
    ('aaa', 'bbb'): {
        'sources': {},
        'verdicts': {
            'aaa': 'keep',
            'bbb': 'skip',
        },
    },
    ('ccc', 'ddd', 'eee'): {
        'sources': {},
        'verdicts': {
            'ccc': 'new',
            'ddd': 'false',
            'eee': 'false',
        },
    },
    ('ggg', 'hhh'): {
        'sources': {},
        'verdicts': {
            'ggg': 'keep',
            'hhh': 'skip',
        },
    },
    ('iii', 'jjj'): {
        'sources': {},
        'verdicts': {
            'iii': 'keep',
            'jjj': 'skip',
        },
    },
}

_DUPLICATES_INDEX_BEFORE: duplicates.DuplicatesKeyIndexType = {
    'aaa': ('aaa', 'bbb'),
    'bbb': ('aaa', 'bbb'),
    'ccc': ('ccc', 'ddd', 'eee'),
    'ddd': ('ccc', 'ddd', 'eee'),
    'eee': ('ccc', 'ddd', 'eee'),
    'ggg': ('ggg', 'hhh'),
    'hhh': ('ggg', 'hhh'),
    'iii': ('iii', 'jjj'),
    'jjj': ('iii', 'jjj'),
}

_NEW_DUPLICATES = {
    'aaa': ['bbb'],                       # no new info
    'ddd': ['eee', 'fff', 'ggg', 'hhh'],  # new hash and will need merging
    'kkk': ['iii', 'jjj'],                # new hash for existing group
    'xxx': ['yyy', 'zzz'],                # all new group
}

_DUPLICATES_DICT_AFTER: duplicates.DuplicatesType = {
    ('aaa', 'bbb'): {
        'sources': {},
        'verdicts': {
            'aaa': 'keep',
            'bbb': 'skip',
        },
    },
    ('ccc', 'ddd', 'eee', 'fff', 'ggg', 'hhh'): {
        'sources': {},
        'verdicts': {
            'ccc': 'new',
            'ddd': 'new',
            'eee': 'new',
            'fff': 'new',
            'ggg': 'new',
            'hhh': 'new',
        },
    },
    ('iii', 'jjj', 'kkk'): {
        'sources': {},
        'verdicts': {
            'iii': 'keep',
            'jjj': 'skip',
            'kkk': 'new',
        },
    },
    ('xxx', 'yyy', 'zzz'): {
        'sources': {},
        'verdicts': {
            'xxx': 'new',
            'yyy': 'new',
            'zzz': 'new',
        },
    },
}

_DUPLICATES_INDEX_AFTER: duplicates.DuplicatesKeyIndexType = {
    'aaa': ('aaa', 'bbb'),
    'bbb': ('aaa', 'bbb'),
    'ccc': ('ccc', 'ddd', 'eee', 'fff', 'ggg', 'hhh'),
    'ddd': ('ccc', 'ddd', 'eee', 'fff', 'ggg', 'hhh'),
    'eee': ('ccc', 'ddd', 'eee', 'fff', 'ggg', 'hhh'),
    'fff': ('ccc', 'ddd', 'eee', 'fff', 'ggg', 'hhh'),
    'ggg': ('ccc', 'ddd', 'eee', 'fff', 'ggg', 'hhh'),
    'hhh': ('ccc', 'ddd', 'eee', 'fff', 'ggg', 'hhh'),
    'iii': ('iii', 'jjj', 'kkk'),
    'jjj': ('iii', 'jjj', 'kkk'),
    'kkk': ('iii', 'jjj', 'kkk'),
    'xxx': ('xxx', 'yyy', 'zzz'),
    'yyy': ('xxx', 'yyy', 'zzz'),
    'zzz': ('xxx', 'yyy', 'zzz'),
}

_DUPLICATES_DICT_TRIMMED: duplicates.DuplicatesType = {
    ('ccc', 'ddd', 'fff', 'ggg', 'hhh'): {
        'sources': {},
        'verdicts': {
            'ccc': 'new',
            'ddd': 'new',
            'fff': 'new',
            'ggg': 'new',
            'hhh': 'false',
        },
    },
    ('iii', 'kkk'): {
        'sources': {},
        'verdicts': {
            'iii': 'new',
            'kkk': 'new',
        },
    },
}

_DUPLICATES_INDEX_TRIMMED: duplicates.DuplicatesKeyIndexType = {
    'ccc': ('ccc', 'ddd', 'fff', 'ggg', 'hhh'),
    'ddd': ('ccc', 'ddd', 'fff', 'ggg', 'hhh'),
    'fff': ('ccc', 'ddd', 'fff', 'ggg', 'hhh'),
    'ggg': ('ccc', 'ddd', 'fff', 'ggg', 'hhh'),
    'hhh': ('ccc', 'ddd', 'fff', 'ggg', 'hhh'),
    'iii': ('iii', 'kkk'),
    'kkk': ('iii', 'kkk'),
}


SUITE = unittest.TestLoader().loadTestsFromTestCase(TestDuplicates)


if __name__ == '__main__':
  unittest.main()
