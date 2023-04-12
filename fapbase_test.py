#!/usr/bin/python3 -bb
#
# Copyright 2023 Daniel Balparda (balparda@gmail.com)
#
# cspell:disable-next-line
# Image testdata/109.gif authored by Charly Whisky, creative commons attribution.
# (Found in https://en.wikipedia.org/wiki/File:Dopplerfrequenz.gif)
#
# pylint: disable=invalid-name,protected-access
"""fapbase.py unittest."""

import os
import os.path
# import pdb
import tempfile
from typing import Union
import unittest
from unittest import mock

from fapfavorites import fapbase

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


_TESTDATA_PATH = os.path.join(os.path.dirname(__file__), 'testdata/')


class TestFapBase(unittest.TestCase):
  """Tests for fapbase.py."""

  @mock.patch('fapfavorites.fapbase.base.INT_TIME')
  def test_Error404(self, mock_time: mock.MagicMock):
    """Test."""
    mock_time.return_value = 1675368670  # 02/feb/2023 20:11:10
    err = fapbase.Error404('foo-url')
    self.assertTupleEqual(err.FailureTuple(), (0, 1675368670, None, 'foo-url'))
    self.assertEqual(str(err), 'Error404(ID: 0, @2023/Feb/02-20:11:10-UTC, \'-\', \'foo-url\')')
    err.image_id = 999
    err.image_name = 'foo-name'
    self.assertTupleEqual(err.FailureTuple(log=True), (999, 1675368670, 'foo-name', 'foo-url'))
    self.assertEqual(
        str(err), 'Error404(ID: 999, @2023/Feb/02-20:11:10-UTC, \'foo-name\', \'foo-url\')')

  @mock.patch('fapfavorites.fapbase.urllib.request.urlopen')
  @mock.patch('fapfavorites.fapbase.time.sleep')
  def test_LimpingURLRead(self, unused_time: mock.MagicMock, mock_url: mock.MagicMock) -> None:
    """Test."""
    # test args error
    with self.assertRaises(AttributeError):
      fapbase.LimpingURLRead('no.url', min_wait=1.0, max_wait=0.5)
    # test direct success

    class _MockResponse1:

      def read(self):
        """Read."""
        return b'foo.response'

    mock_url.return_value = _MockResponse1()
    self.assertEqual(fapbase.LimpingURLRead('foo.url'), b'foo.response')
    mock_url.assert_called_once_with('foo.url', timeout=fapbase._URL_TIMEOUT)
    mock_url.reset_mock(side_effect=True)  # reset calls and side_effect
    # test exceptions and retry

    class _MockResponse2:

      def read(self):
        """Read."""
        raise fapbase.socket.timeout('timeout in page')

    fapbase._MAX_RETRY = 2
    mock_url.return_value = _MockResponse2()
    with self.assertRaises(fapbase.Error):
      fapbase.LimpingURLRead('bar.url')
    self.assertListEqual(
        mock_url.call_args_list,
        [mock.call('bar.url', timeout=15.0),   # 1st try
         mock.call('bar.url', timeout=15.0),   # retry 1
         mock.call('bar.url', timeout=15.0)])  # retry 2

  @mock.patch('fapfavorites.fapbase.LimpingURLRead')
  def test_GetFolderPics(self, mock_read: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_read.side_effect = [
        b'page-7', b'page-6', b'page-5',  # backtrack
        b'page-5', b'page-6', b'page-7', b'page-8', b'page-9', b'page-10', b'page-11',
        b'page-12', b'page-13', b'page-14', b'page-15', b'page-16', b'page-17', b'page-18']
    fapbase._FAVORITE_IMAGE = MockRegex({
        'page-5': ['102', '103', '104'],  # <- last known image (103) is here
        'page-6': ['105'],
        'page-7': ['106'],                # <- backtrack starts here
        'page-8': ['107', '108'],
        'page-9': [],                     # <- one empty page obstacle
        'page-10': ['109', '110'],
        'page-11': ['111'],
        'page-12': [],                    # <- two empty pages obstacle
        'page-13': [],
        'page-14': ['112', '113'],
        'page-15': ['114'],
        'page-16': [],                    # <- three empty pages means it should stop
        'page-17': [],
        'page-18': [],
    })
    self.assertTupleEqual(
        fapbase.GetFolderPics(10, 20, img_list_hint=[100, 101, 102, 103], seen_pages_hint=8),
        ([100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114], 16, 11))
    self.assertListEqual(
        mock_read.call_args_list,
        [mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=7&folderid=20'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=6&folderid=20'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=5&folderid=20'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=5&folderid=20'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=6&folderid=20'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=7&folderid=20'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=8&folderid=20'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=9&folderid=20'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=10&folderid=20'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=11&folderid=20'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=12&folderid=20'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=13&folderid=20'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=14&folderid=20'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=15&folderid=20'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=16&folderid=20'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=17&folderid=20'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=18&folderid=20')])
    fapbase._FAVORITE_IMAGE = None  # set to None for safety

  @mock.patch('fapfavorites.fapbase.LimpingURLRead')
  def test_GetBinary(self, mock_read: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_read.side_effect = [b'page-1', b'']
    self.assertTupleEqual(
        fapbase.GetBinary('url-1'),
        (b'page-1', '0eb236e50de35c59c03b63629624351af778cc33fbc55a92254e3c29e58e6255'))
    with self.assertRaisesRegex(fapbase.Error, r'Empty full-res'):
      fapbase.GetBinary('url-2')
    self.assertListEqual(
        mock_read.call_args_list,
        [mock.call('url-1'), mock.call('url-2')])

  @mock.patch('fapfavorites.fapbase.GetFolderPics')
  @mock.patch('fapfavorites.fapbase.ExtractFullImageURL')
  @mock.patch('fapfavorites.fapbase.GetBinary')
  def test_DownloadFavorites(
      self, get_binary: mock.MagicMock, image_url: mock.MagicMock,
      folder_pics: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    folder_pics.return_value = ([100, 101, 102], 5, 3)
    image_url.side_effect = [('url-100', 'f100.jpg', 'jpg'),  # <- this file will already exist
                             ('url-101', 'f101.gif', 'gif'),
                             ('url-102', 'f102.jpg', 'jpg')]  # <- this file's URL will 404
    get_binary.side_effect = [(b'img-101', ''), fapbase.Error404('url-102')]
    with self.assertRaisesRegex(fapbase.Error, r'Empty inputs'):
      fapbase.DownloadFavorites(10, 20, ' ')
    with tempfile.TemporaryDirectory() as db_path:
      with open(os.path.join(db_path, 'f100.jpg'), 'wb') as file_obj:  # 'f100.jpg' already exists
        file_obj.write(b'do-not-clobber')
      fapbase.DownloadFavorites(10, 20, f' {db_path} ')
      self.assertTrue(os.path.exists(os.path.join(db_path, 'f101.gif')))   # this should be created
      self.assertFalse(os.path.exists(os.path.join(db_path, 'f102.jpg')))  # this one 404-ed
      with open(os.path.join(db_path, 'f100.jpg'), 'rb') as file_obj:
        self.assertEqual(file_obj.read(), b'do-not-clobber')  # check that 'f100.jpg' wasn't touched
      with open(os.path.join(db_path, 'f101.gif'), 'rb') as file_obj:
        self.assertEqual(file_obj.read(), b'img-101')  # check 'f101.gif' content is as expected
    folder_pics.assert_called_once_with(10, 20)
    self.assertListEqual(
        image_url.call_args_list,
        [mock.call(100), mock.call(101), mock.call(102)])
    self.assertListEqual(
        get_binary.call_args_list,
        [mock.call('url-101'), mock.call('url-102')])

  @mock.patch('os.path.exists')
  @mock.patch('os.mkdir')
  @mock.patch('fapfavorites.fapbase.GetFolderPics')
  @mock.patch('fapfavorites.fapbase.ExtractFullImageURL')
  @mock.patch('fapfavorites.fapbase.GetBinary')
  def test_DownloadFavorites_Output_Creation(
      self, get_binary: mock.MagicMock, image_url: mock.MagicMock,
      folder_pics: mock.MagicMock, mkdir: mock.MagicMock, exists: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    exists.return_value = False  # <- output directory check
    mkdir.side_effect = [NotImplementedError()]
    with self.assertRaises(NotImplementedError):
      fapbase.DownloadFavorites(10, 20, ' /foo/bar ')
    exists.assert_called_once_with('/foo/bar')
    mkdir.assert_called_once_with('/foo/bar')
    get_binary.assert_not_called()
    image_url.assert_not_called()
    folder_pics.assert_not_called()

  @mock.patch('fapfavorites.fapbase.LimpingURLRead')
  def test_CheckFolderIsForImages(self, mock_read: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_read.side_effect = [b'page-10-20', b'page-11-30']
    fapbase._FIND_ONLY_IN_PICTURE_FOLDER = MockRegex({'page-10-20': ['true'], 'page-11-30': []})
    fapbase._FIND_ONLY_IN_GALLERIES_FOLDER = MockRegex({'page-10-20': [], 'page-11-30': ['true']})
    fapbase.CheckFolderIsForImages(10, 20)
    with self.assertRaisesRegex(fapbase.Error, r'not a valid images folder'):
      fapbase.CheckFolderIsForImages(11, 30)
    self.assertListEqual(
        mock_read.call_args_list,
        [mock.call('https://www.imagefap.com/showfavorites.php?userid=10&page=0&folderid=20'),
         mock.call('https://www.imagefap.com/showfavorites.php?userid=11&page=0&folderid=30')])
    fapbase._FIND_ONLY_IN_PICTURE_FOLDER = None    # set to None for safety
    fapbase._FIND_ONLY_IN_GALLERIES_FOLDER = None  # set to None for safety

  def test_NormalizeExtension(self) -> None:
    """Test."""
    self.assertEqual(fapbase.NormalizeExtension(' GIF '), 'gif')
    self.assertEqual(fapbase.NormalizeExtension(' JPEG '), 'jpg')

  @mock.patch('fapfavorites.fapbase.LimpingURLRead')
  def test_ExtractFullImageURL(self, mock_read: mock.MagicMock) -> None:
    """Test."""
    self.maxDiff = None
    mock_read.side_effect = [b'page-10', b'page-11', b'page-12', fapbase.Error404('url-13')]
    fapbase.FULL_IMAGE = MockRegex({'page-10': ['url-10'], 'page-11': [], 'page-12': ['url-12']})
    fapbase._IMAGE_NAME = MockRegex({'page-10': [' crazy/name.JPEG '], 'page-12': []})
    self.assertTupleEqual(fapbase.ExtractFullImageURL(10), ('url-10', 'crazy-name.jpg', 'jpg'))
    with self.assertRaisesRegex(fapbase.Error, r'No full resolution'):
      fapbase.ExtractFullImageURL(11)
    with self.assertRaisesRegex(fapbase.Error, r'No image name'):
      fapbase.ExtractFullImageURL(12)
    with self.assertRaisesRegex(fapbase.Error404, r'Error404\(ID: 13'):
      fapbase.ExtractFullImageURL(13)
    self.assertListEqual(
        mock_read.call_args_list,
        [mock.call('https://www.imagefap.com/photo/10/'),
         mock.call('https://www.imagefap.com/photo/11/'),
         mock.call('https://www.imagefap.com/photo/12/'),
         mock.call('https://www.imagefap.com/photo/13/')])
    fapbase.FULL_IMAGE = None  # set to None for safety
    fapbase._IMAGE_NAME = None  # set to None for safety


class MockRegex:
  """Mock regex for testing use only."""

  def __init__(self, return_values: dict[str, list[Union[str, tuple[str, ...]]]]):
    """Init."""
    self._return_values = return_values

  def findall(self, query: str) -> list[Union[str, tuple[str, ...]]]:
    """Find all."""
    return self._return_values[query]


SUITE = unittest.TestLoader().loadTestsFromTestCase(TestFapBase)


if __name__ == '__main__':
  unittest.main()
