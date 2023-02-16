#!/usr/bin/python3 -bb
#
# Copyright 2023 Daniel Balparda (balparda@gmail.com)
#
"""duplicated.py unittest."""

import os.path
# import pdb
import unittest
from unittest import mock

import numpy as np

import duplicates

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


_TESTDATA_PATH = os.path.join(os.path.dirname(__file__), 'testdata/')


class TestDuplicates(unittest.TestCase):
  """Tests for duplicates.py."""

  @mock.patch('duplicates.image_methods.PHash.encode_image')
  @mock.patch('duplicates.image_methods.AHash.encode_image')
  @mock.patch('duplicates.image_methods.DHash.encode_image')
  @mock.patch('duplicates.image_methods.WHash.encode_image')
  @mock.patch('duplicates.image_methods.CNN.encode_image')
  def test_Encode(
      self, mock_cnn: mock.MagicMock, mock_w: mock.MagicMock, mock_d: mock.MagicMock,
      mock_a: mock.MagicMock, mock_p: mock.MagicMock) -> None:
    """Test."""
    mock_p.return_value = 'abc'
    mock_a.return_value = 'def'
    mock_d.return_value = 'ghi'
    mock_w.return_value = 'jkl'
    mock_cnn.return_value = ['array']
    dup = duplicates.Duplicates({}, {})
    self.assertTupleEqual(dup.Encode('path'), ('abc', 'def', 'ghi', 'jkl', 'array'))
    mock_p.assert_called_once_with(image_file='path')

  def test_Encode_Real_Data(self) -> None:
    """Test."""
    dup = duplicates.Duplicates({}, {})
    f_name = os.path.join(_TESTDATA_PATH, '106.jpg')
    self.assertTupleEqual(
        dup.Encode(f_name)[:4],
        ('89991f6f62a63479', '091b5f7761323000', '737394c5d3e66431', '091b7f7f71333018'))
    self.assertTupleEqual(dup.Encode(f_name)[-1].shape, (576,))

  @mock.patch('duplicates.image_methods.PHash.find_duplicates')
  @mock.patch('duplicates.image_methods.AHash.find_duplicates')
  @mock.patch('duplicates.image_methods.DHash.find_duplicates')
  @mock.patch('duplicates.image_methods.WHash.find_duplicates')
  @mock.patch('duplicates.image_methods.CNN.find_duplicates')
  def test_FindDuplicates(
      self, mock_cnn: mock.MagicMock, mock_w: mock.MagicMock, mock_d: mock.MagicMock,
      mock_a: mock.MagicMock, mock_p: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_p.return_value = _NEW_DUPLICATES['percept']
    mock_a.return_value = _NEW_DUPLICATES['average']
    mock_d.return_value = _NEW_DUPLICATES['diff']
    mock_w.return_value = _NEW_DUPLICATES['wavelet']
    mock_cnn.return_value = _NEW_DUPLICATES['cnn']
    dup = duplicates.Duplicates(_DUPLICATES_DICT_BEFORE, _DUPLICATES_INDEX_BEFORE)
    mock_encoding: duplicates.HashEncodingMapType = {
        'percept': {'foo': 'p_bar'},
        'average': {'foo': 'a_bar'},
        'diff': {'foo': 'd_bar'},
        'wavelet': {'foo': 'w_bar'},
        'cnn': {'foo': np.array([[1, 2, 3]])},
    }
    self.assertEqual(dup.FindDuplicates(mock_encoding), 5)
    mock_p.assert_called_once_with(encoding_map=mock_encoding['percept'], scores=True)
    mock_a.assert_called_once_with(encoding_map=mock_encoding['average'], scores=True)
    mock_d.assert_called_once_with(encoding_map=mock_encoding['diff'], scores=True)
    mock_w.assert_called_once_with(encoding_map=mock_encoding['wavelet'], scores=True)
    mock_cnn.assert_called_once_with(encoding_map=mock_encoding['cnn'], scores=True)
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
        'sources': {
            'wavelet': {
                ('aaa', 'bbb'): 0.9,
            },
        },
        'verdicts': {
            'aaa': 'keep',
            'bbb': 'skip',
        },
    },
    ('ccc', 'ddd', 'eee'): {
        'sources': {
            'percept': {
                ('ccc', 'ddd'): 0.7,
                ('ddd', 'eee'): 0.8,
            },
        },
        'verdicts': {
            'ccc': 'new',
            'ddd': 'false',
            'eee': 'false',
        },
    },
    ('ggg', 'hhh'): {
        'sources': {
            'cnn': {
                ('ggg', 'hhh'): 0.5,
            },
        },
        'verdicts': {
            'ggg': 'keep',
            'hhh': 'skip',
        },
    },
    ('iii', 'jjj'): {
        'sources': {
            'average': {
                ('iii', 'jjj'): 0.4,
            },
            'diff': {
                ('iii', 'jjj'): 0.3,
            },
        },
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
    'percept': {
        'aaa': [('bbb', 0.1)],  # no new info
        'bbb': [('aaa', 0.1)],
    },
    'average': {
        'kkk': [('iii', 0.5), ('jjj', 0.6)],  # new hash for existing group
        'iii': [('jjj', 0.4), ('kkk', 0.5)],
        'jjj': [('iii', 0.4), ('kkk', 0.6)],
    },
    'diff': {
        'xxx': [('yyy', 0.5), ('zzz', 0.6)],  # all new group
        'yyy': [('zzz', 0.4), ('xxx', 0.5)],
        'zzz': [('yyy', 0.4), ('xxx', 0.6)],
    },
    'wavelet': {
    },
    'cnn': {
        'ddd': [('eee', 0.1), ('fff', 0.2), ('ggg', 0.3), ('hhh', 0.4)],  # new hash & needs merging
        'eee': [('ddd', 0.1), ('fff', 0.5), ('ggg', 0.6), ('hhh', 0.7)],
        'ggg': [('eee', 0.6), ('fff', 0.8), ('ddd', 0.3), ('hhh', 0.4)],
    },
}

_DUPLICATES_DICT_AFTER: duplicates.DuplicatesType = {
    ('aaa', 'bbb'): {
        'sources': {
            'percept': {
                ('aaa', 'bbb'): 0.1,
            },
            'wavelet': {
                ('aaa', 'bbb'): 0.9,
            },
        },
        'verdicts': {
            'aaa': 'keep',
            'bbb': 'skip',
        },
    },
    ('ccc', 'ddd', 'eee', 'fff', 'ggg', 'hhh'): {
        'sources': {
            'cnn': {
                ('ddd', 'eee'): 0.1,
                ('ddd', 'fff'): 0.2,
                ('ddd', 'ggg'): 0.3,
                ('ddd', 'hhh'): 0.4,
                ('eee', 'fff'): 0.5,
                ('eee', 'ggg'): 0.6,
                ('eee', 'hhh'): 0.7,
                ('fff', 'ggg'): 0.8,
                ('ggg', 'hhh'): 0.4,
            },
            'percept': {
                ('ccc', 'ddd'): 0.7,
                ('ddd', 'eee'): 0.8,
            },
        },
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
        'sources': {
            'average': {
                ('iii', 'jjj'): 0.4,
                ('iii', 'kkk'): 0.5,
                ('jjj', 'kkk'): 0.6,
            },
            'diff': {
                ('iii', 'jjj'): 0.3,
            },
        },
        'verdicts': {
            'iii': 'keep',
            'jjj': 'skip',
            'kkk': 'new',
        },
    },
    ('xxx', 'yyy', 'zzz'): {
        'sources': {
            'diff': {
                ('xxx', 'yyy'): 0.5,
                ('xxx', 'zzz'): 0.6,
                ('yyy', 'zzz'): 0.4,
            },
        },
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
        'sources': {
            'cnn': {
                ('ddd', 'fff'): 0.2,
                ('ddd', 'ggg'): 0.3,
                ('ddd', 'hhh'): 0.4,
                ('fff', 'ggg'): 0.8,
                ('ggg', 'hhh'): 0.4,
            },
            'percept': {
                ('ccc', 'ddd'): 0.7,
            },
        },
        'verdicts': {
            'ccc': 'new',
            'ddd': 'new',
            'fff': 'new',
            'ggg': 'new',
            'hhh': 'false',
        },
    },
    ('iii', 'kkk'): {
        'sources': {
            'average': {
                ('iii', 'kkk'): 0.5,
            },
        },
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
