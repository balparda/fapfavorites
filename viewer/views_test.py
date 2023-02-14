#!/usr/bin/python3 -bb
#
# Copyright 2023 Daniel Balparda (balparda@gmail.com)
#
"""views.py unittest."""

import os
# import pdb
from typing import Any
import unittest
from unittest import mock

# import duplicates
# import fapdata

os.environ['DJANGO_SETTINGS_MODULE'] = 'fapper.settings'  # cspell:disable-line
from viewer import views  # noqa: E402

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


class TestDjangoViews(unittest.TestCase):
  """Tests for views.py."""

  def test_SHA256HexDigest(self):
    """Test."""
    digest = views.SHA256HexDigest()
    self.assertEqual(digest.to_python('fOO'), 'foo')
    self.assertEqual(digest.to_url('Bar'), 'bar')

  @mock.patch('viewer.views._DBFactory')
  @mock.patch('django.shortcuts.render')
  @mock.patch('fapdata.os.path.getsize')
  def test_ServeIndex(self, mock_getsize, mock_render, mock_db):
    """Test."""
    self.maxDiff = None
    mock_db.return_value = _TestDBFactory()
    mock_getsize.return_value = 100000
    views.ServeIndex('req')  # type: ignore
    mock_render.assert_called_once_with('req', 'viewer/index.html', _INDEX_CONTEXT)


@mock.patch('fapdata.os.path.isdir')
def _TestDBFactory(mock_isdir) -> views.fapdata.FapDatabase:
  mock_isdir.return_value = True
  db = views.fapdata.FapDatabase('/foo/', create_if_needed=False)
  db._db = _MOCK_DATABASE
  db.duplicates = views.duplicates.Duplicates(db._duplicates_registry, db._duplicates_key_index)
  return db


_MOCK_DATABASE: views.fapdata._DatabaseType = {
    'users': {
        1: 'Luke',  # has 2 albums
        2: 'Ben',   # has 1 album
        3: 'Yoda',  # has 0 albums
    },
    'favorites': {
        1: {  # Luke
            10: {
                'date_blobs': 1675300000,
                'date_straight': 0,
                'images': [100, 101, 102, 103, 104],
                'name': 'luke-folder-10',
                'pages': 9,
            },
            11: {
                'date_blobs': 1671000000,
                'date_straight': 1675300000,
                'images': [110, 111, 112],
                'name': 'luke-folder-11',
                'pages': 8,
            },
        },
        2: {  # Ben
            20: {
                'date_blobs': 1673000000,
                'date_straight': 0,
                'images': [200, 201, 202, 203],
                'name': 'ben-folder-20',
                'pages': 3,
            },
        },
    },
    'blobs': {
        '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19': {
            'animated': False,
            'ext': 'jpg',
            'height': 200,
            'loc': {
                (102, 'url-102', 'name-102.jpg', 1, 10),
            },
            'percept': 'cd4fc618316732e7',
            'sz': 54643,
            'sz_thumb': 54643,
            'tags': {3},
            'width': 168,
        },
        '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': {
            'animated': False,
            'ext': 'png',
            'height': 173,
            'loc': {
                (110, 'url-110', 'name-110.png', 1, 11),
                (202, 'url-202', 'name-202.png', 2, 20),
            },
            'percept': 'd99ee32e586716c8',
            'sz': 45309,
            'sz_thumb': 45309,
            'tags': set(),  # untagged!
            'width': 130,
        },
        '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8': {
            'animated': True,
            'ext': 'gif',
            'height': 500,
            'tags': {246, 33},
            'loc': {
                (200, 'url-200', 'name-200.gif', 2, 20),
            },
            'percept': 'e699669966739866',
            'sz': 444973,
            'sz_thumb': 302143,
            'width': 100,
        },
        '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf': {
            'animated': False,
            'ext': 'jpg',
            'height': 200,
            'loc': {
                (101, 'url-101', 'name-101.jpg', 1, 10),
                (111, 'url-111', 'name-111.jpg', 1, 11),
                (201, 'url-201', 'name-201.jpg', 2, 20),
            },
            'percept': 'd99ee32e586716c8',
            'sz': 101,
            'sz_thumb': 0,
            'tags': {11, 33},
            'width': 160,
        },
        'dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180': {
            'animated': False,
            'ext': 'jpg',
            'height': 222,
            'loc': {
                (112, 'url-112', 'name-112.jpg', 1, 11),
            },
            'percept': '89991f6f62a63479',
            'sz': 89216,
            'sz_thumb': 11890,
            'tags': {246},
            'width': 300,
        },
        'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': {
            'animated': False,
            'ext': 'jpg',
            'height': 246,
            'loc': {
                (100, 'url-100', 'name-100.jpg', 1, 10),
                (104, 'url-104', 'name-104.jpg', 1, 10),  # dup in same album as above!
                (203, 'url-203', 'name-203.jpg', 2, 20),
            },
            'percept': 'cc8fc37638703ee1',
            'sz': 56583,
            'sz_thumb': 56583,
            'tags': {1, 2},
            'width': 200,
        },
        'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e': {
            'animated': True,
            'ext': 'gif',
            'height': 100,
            'tags': {1, 24, 33},
            'loc': {
                (103, 'url-103', 'name-103.gif', 1, 10),
            },
            'percept': 'e699669966739866',
            'sz': 444973,
            'sz_thumb': 302143,
            'width': 500,
        },
    },
    'image_ids_index': {
        100: 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e',
        101: '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
        102: '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19',
        103: 'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e',
        104: 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e',
        110: '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
        111: '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
        112: 'dfc28d8c6ba0553ac749780af2d0cdf5305798befc04a1569f63657892a2e180',
        200: '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8',
        201: '9b162a339a3a6f9a4c2980b508b6ee552fd90a0bcd2658f85c3b15ba8f0c44bf',
        202: '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
        203: 'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e',
    },
    'duplicates_registry': {
        ('0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19',
         '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
         'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'): {
            '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19': 'new',
            '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': 'keep',
            'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': 'skip',
        },
        ('5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8',
         'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e'): {
            '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8': 'false',
            'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e': 'false',
        },
    },
    'duplicates_key_index': {
        '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19': (
            '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19',
            '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
            'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'),
        '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6': (
            '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19',
            '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
            'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'),
        'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e': (
            '0aaef1becbd966a2adcb970069f6cdaa62ee832fbb24e3c827a39fbc463c0e19',
            '321e59af9d70af771fb9bb55e4a4f76bca5af024fca1c78709ee1b0259cd58e6',
            'e221b76f559461769777a772a58e44960d85ffec73627d9911260ae13825e60e'),
        '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8': (
            '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8',
            'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e'),
        'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e': (
            '5b1d83a7317f2bb145eea34e865bf413c600c5d4c0f36b61a404813fee4a53e8',
            'ed1441656a734052e310f30837cc706d738813602fcc468132aebaf0f316870e'),
    },
    'tags': {
        0: {  # unused tag!
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
                22: {  # unused tag!
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
    },
}

_INDEX_CONTEXT: dict[str, Any] = {
    'users': 3,
    'tags': 9,
    'duplicates': 2,
    'dup_action': 1,
    'n_images': 7,
    'database_stats': [
        ('Database is located in \'/foo/imagefap.database\', and is 97.66kb '
         '(8.80438% of total images size)'),
        ('1.08Mb total (unique) images size (101b min, 434.54kb max, '
         '158.45kb mean with 190.33kb standard deviation, 2 are animated)'),
        ('Pixel size (width, height): 22.49k pixels min (130, 173), '
         '66.60k pixels max (300, 222), 43.41k mean with 14.84k standard deviation'),
        ('754.60kb total thumbnail size (0b min, 295.06kb max, 107.80kb mean with '
         '129.59kb standard deviation), 68.0% of total images size'),
        '',
        '3 users',
        '3 favorite galleries (oldest: 2023/Jan/06-10:13:20-UTC / newer: 2023/Feb/02-01:06:40-UTC)',
        '7 unique images (12 total, 5 exact duplicates)',
        '5 perceptual duplicates in 2 groups',
    ],
}


SUITE = unittest.TestLoader().loadTestsFromTestCase(TestDjangoViews)


if __name__ == '__main__':
  unittest.main()
