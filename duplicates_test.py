#!/usr/bin/python3 -bb
#
# Copyright 2023 Daniel Balparda (balparda@gmail.com)
#
# pylint: disable=invalid-name,protected-access
"""duplicated.py unittest."""

import copy
import os.path
# import pdb
import unittest
from unittest import mock

import numpy as np

from fapfavorites import duplicates

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


_TESTDATA_PATH = os.path.join(os.path.dirname(__file__), 'testdata/')


class TestDuplicates(unittest.TestCase):
  """Tests for duplicates.py."""

  @mock.patch('fapfavorites.duplicates.image_methods.PHash.encode_image')
  @mock.patch('fapfavorites.duplicates.image_methods.AHash.encode_image')
  @mock.patch('fapfavorites.duplicates.image_methods.DHash.encode_image')
  @mock.patch('fapfavorites.duplicates.image_methods.WHash.encode_image')
  @mock.patch('fapfavorites.duplicates.image_methods.CNN.encode_image')
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

  @mock.patch('fapfavorites.duplicates.image_methods.PHash.find_duplicates')
  @mock.patch('fapfavorites.duplicates.image_methods.AHash.find_duplicates')
  @mock.patch('fapfavorites.duplicates.image_methods.DHash.find_duplicates')
  @mock.patch('fapfavorites.duplicates.image_methods.WHash.find_duplicates')
  @mock.patch('fapfavorites.duplicates.image_methods.CNN.find_duplicates')
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
    dup = duplicates.Duplicates(
        copy.deepcopy(_DUPLICATES_DICT_BEFORE), copy.deepcopy(_DUPLICATES_INDEX_BEFORE))
    mock_encoding: duplicates.HashEncodingMapType = {
        'percept': {'foo': 'p_bar'},
        'average': {'foo': 'a_bar'},
        'diff': {'foo': 'd_bar'},
        'wavelet': {'foo': 'w_bar'},
        'cnn': {'foo': np.array([[1, 2, 3]])},
    }
    # test error cases, with invalid animated configs
    bogus_animated = copy.deepcopy(duplicates.ANIMATED_SENSITIVITY_DEFAULTS)
    with self.assertRaisesRegex(duplicates.Error, r'PERCEPT.*must be stricter'):
      bogus_animated['percept'] = duplicates.METHOD_SENSITIVITY_DEFAULTS['percept'] + 2
      dup.FindDuplicates(
          mock_encoding, set(), duplicates.METHOD_SENSITIVITY_DEFAULTS, bogus_animated)
    bogus_animated = copy.deepcopy(duplicates.ANIMATED_SENSITIVITY_DEFAULTS)
    with self.assertRaisesRegex(duplicates.Error, r'CNN.*must be stricter'):
      bogus_animated['cnn'] = duplicates.METHOD_SENSITIVITY_DEFAULTS['cnn'] - 0.02
      dup.FindDuplicates(
          mock_encoding, set(), duplicates.METHOD_SENSITIVITY_DEFAULTS, bogus_animated)
    # test success case
    self.assertEqual(
        dup.FindDuplicates(
            mock_encoding, {'yyy'},
            duplicates.METHOD_SENSITIVITY_DEFAULTS, duplicates.ANIMATED_SENSITIVITY_DEFAULTS), 4)
    mock_p.assert_called_once_with(
        encoding_map=mock_encoding['percept'], max_distance_threshold=4, scores=True)
    mock_a.assert_called_once_with(
        encoding_map=mock_encoding['average'], max_distance_threshold=1, scores=True)
    mock_d.assert_called_once_with(
        encoding_map=mock_encoding['diff'], max_distance_threshold=4, scores=True)
    mock_w.assert_called_once_with(
        encoding_map=mock_encoding['wavelet'], max_distance_threshold=1, scores=True)
    mock_cnn.assert_called_once_with(
        encoding_map=mock_encoding['cnn'], min_similarity_threshold=0.95, scores=True)
    self.assertDictEqual(dup.registry, _DUPLICATES_DICT_AFTER)
    self.assertDictEqual(dup.index, _DUPLICATES_INDEX_AFTER)

  def test_TrimDeletedBlob(self) -> None:
    """Test."""
    self.maxDiff = None
    dup = duplicates.Duplicates(
        copy.deepcopy(_DUPLICATES_DICT_AFTER), copy.deepcopy(_DUPLICATES_INDEX_AFTER))
    dup.registry[('ccc', 'ddd', 'eee', 'fff', 'ggg', 'hhh')]['verdicts']['fff'] = 'keep'
    dup.registry[('ccc', 'ddd', 'eee', 'fff', 'ggg', 'hhh')]['verdicts']['ggg'] = 'skip'
    dup.registry[('ccc', 'ddd', 'eee', 'fff', 'ggg', 'hhh')]['verdicts']['hhh'] = 'false'
    self.assertTrue(dup.TrimDeletedBlob('bbb'))
    self.assertFalse(dup.TrimDeletedBlob('eee'))
    self.assertFalse(dup.TrimDeletedBlob('jjj'))
    self.assertTrue(dup.TrimDeletedBlob('xxx'))
    self.assertFalse(dup.TrimDeletedBlob('mmm'))  # key not in index
    self.assertDictEqual(dup.registry, _DUPLICATES_DICT_TRIMMED)
    self.assertDictEqual(dup.index, _DUPLICATES_INDEX_TRIMMED)

  def test_DeletePendingDuplicates(self) -> None:
    """Test."""
    self.maxDiff = None
    dup = duplicates.Duplicates(
        copy.deepcopy(_DUPLICATES_DICT_AFTER), copy.deepcopy(_DUPLICATES_INDEX_AFTER))
    self.assertTupleEqual(dup.DeletePendingDuplicates(), (2, 9))
    self.assertDictEqual(dup.registry, _DUPLICATES_DICT_NO_PENDING)
    self.assertDictEqual(dup.index, _DUPLICATES_INDEX_NO_PENDING)

  def test_DeleteAllDuplicates(self) -> None:
    """Test."""
    self.maxDiff = None
    dup = duplicates.Duplicates(
        copy.deepcopy(_DUPLICATES_DICT_AFTER), copy.deepcopy(_DUPLICATES_INDEX_AFTER))
    self.assertTupleEqual(dup.DeleteAllDuplicates(), (4, 13))
    self.assertDictEqual(dup.registry, {})
    self.assertDictEqual(dup.index, {})


_DUPLICATES_DICT_BEFORE: duplicates.DuplicatesType = {
    ('aaa', 'bbb'): {
        'sources': {
            'wavelet': {
                ('aaa', 'bbb'): 4,
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
                ('ccc', 'ddd'): 2,
                ('ddd', 'eee'): 3,
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
                ('ggg', 'hhh'): 0.94,
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
                ('iii', 'jjj'): 0,
            },
            'diff': {
                ('iii', 'jjj'): 1,
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
        'aaa': [('bbb', 4)],  # no new info
        'bbb': [('aaa', 4)],
    },
    'average': {
        'kkk': [('iii', 2), ('jjj', 1)],  # new hash for existing group
        'iii': [('jjj', 0), ('kkk', 2)],
        'jjj': [('iii', 0), ('kkk', 1)],
    },
    'diff': {
        'xxx': [('yyy', 2), ('zzz', 1)],  # all new group
        'yyy': [('zzz', 2), ('xxx', 2)],  # 'yyy' will be marked as animated and not enough score
        'zzz': [('yyy', 2), ('xxx', 1)],
    },
    'wavelet': {
    },
    'cnn': {
        'ddd': [('eee', 0.91), ('fff', 0.92), ('ggg', 0.93), ('hhh', 0.94)],  # new hash -> merge
        'eee': [('ddd', 0.91), ('fff', 0.95), ('ggg', 0.96), ('hhh', 0.97)],
        'ggg': [('eee', 0.96), ('fff', 0.98), ('ddd', 0.93), ('hhh', 0.94)],
    },
}

_DUPLICATES_DICT_AFTER: duplicates.DuplicatesType = {
    ('aaa', 'bbb'): {
        'sources': {
            'percept': {
                ('aaa', 'bbb'): 4,
            },
            'wavelet': {
                ('aaa', 'bbb'): 4,
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
                ('ddd', 'eee'): 0.91,
                ('ddd', 'fff'): 0.92,
                ('ddd', 'ggg'): 0.93,
                ('ddd', 'hhh'): 0.94,
                ('eee', 'fff'): 0.95,
                ('eee', 'ggg'): 0.96,
                ('eee', 'hhh'): 0.97,
                ('fff', 'ggg'): 0.98,
                ('ggg', 'hhh'): 0.94,
            },
            'percept': {
                ('ccc', 'ddd'): 2,
                ('ddd', 'eee'): 3,
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
                ('iii', 'jjj'): 0,
                ('iii', 'kkk'): 2,
                ('jjj', 'kkk'): 1,
            },
            'diff': {
                ('iii', 'jjj'): 1,
            },
        },
        'verdicts': {
            'iii': 'keep',
            'jjj': 'skip',
            'kkk': 'new',
        },
    },
    ('xxx', 'zzz'): {
        'sources': {
            'diff': {
                ('xxx', 'zzz'): 1,
            },
        },
        'verdicts': {
            'xxx': 'new',
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
    'xxx': ('xxx', 'zzz'),
    'zzz': ('xxx', 'zzz'),
}

_DUPLICATES_DICT_TRIMMED: duplicates.DuplicatesType = {
    ('ccc', 'ddd', 'fff', 'ggg', 'hhh'): {
        'sources': {
            'cnn': {
                ('ddd', 'fff'): 0.92,
                ('ddd', 'ggg'): 0.93,
                ('ddd', 'hhh'): 0.94,
                ('fff', 'ggg'): 0.98,
                ('ggg', 'hhh'): 0.94,
            },
            'percept': {
                ('ccc', 'ddd'): 2,
            },
        },
        'verdicts': {
            'ccc': 'new',
            'ddd': 'new',
            'fff': 'keep',
            'ggg': 'skip',
            'hhh': 'false',
        },
    },
    ('iii', 'kkk'): {
        'sources': {
            'average': {
                ('iii', 'kkk'): 2,
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

_DUPLICATES_DICT_NO_PENDING: duplicates.DuplicatesType = {
    ('aaa', 'bbb'): {
        'sources': {
            'percept': {
                ('aaa', 'bbb'): 4,
            },
            'wavelet': {
                ('aaa', 'bbb'): 4,
            },
        },
        'verdicts': {
            'aaa': 'keep',
            'bbb': 'skip',
        },
    },
    ('iii', 'jjj'): {
        'sources': {
            'average': {
                ('iii', 'jjj'): 0,
            },
            'diff': {
                ('iii', 'jjj'): 1,
            },
        },
        'verdicts': {
            'iii': 'keep',
            'jjj': 'skip',
        },
    },
}

_DUPLICATES_INDEX_NO_PENDING: duplicates.DuplicatesKeyIndexType = {
    'aaa': ('aaa', 'bbb'),
    'bbb': ('aaa', 'bbb'),
    'iii': ('iii', 'jjj'),
    'jjj': ('iii', 'jjj'),
}


SUITE = unittest.TestLoader().loadTestsFromTestCase(TestDuplicates)


if __name__ == '__main__':
  unittest.main()
