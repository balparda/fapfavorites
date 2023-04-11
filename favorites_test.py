#!/usr/bin/python3 -bb
#
# Copyright 2023 Daniel Balparda (balparda@gmail.com)
#
# pylint: disable=invalid-name,protected-access
"""favorites.py unittest."""

# import pdb
import unittest
from unittest import mock

from fapfavorites import favorites

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


class TestFavorites(unittest.TestCase):
  """Tests for favorites.py."""

  def test_ParameterErrors(self) -> None:
    """Test."""
    with self.assertRaisesRegex(AttributeError, r'either the --user or the --id'):
      favorites.Main(  # pylint: disable=no-value-for-parameter
          ['read', '--output', '/path/'])
    with self.assertRaisesRegex(AttributeError, r'both the --user and the --id'):
      favorites.Main(  # pylint: disable=no-value-for-parameter
          ['read', '--user', 'foo', '--id', '10', '--output', '/path/'])
    with self.assertRaisesRegex(AttributeError, r'both the --name and the --folder'):
      favorites.Main(  # pylint: disable=no-value-for-parameter
          ['read', '--user', 'foo', '--name', 'bar', '--folder', '20', '--output', '/path/'])
    with self.assertRaisesRegex(AttributeError, r'either the --name or the --folder'):
      favorites.Main(  # pylint: disable=no-value-for-parameter
          ['get', '--user', 'foo', '--output', '/path/'])
    with self.assertRaisesRegex(AttributeError, r'should not provide --name or --folder'):
      favorites.Main(  # pylint: disable=no-value-for-parameter
          ['audit', '--user', 'foo', '--name', 'bar', '--output', '/path/'])

  @mock.patch('fapfavorites.favorites.fapdata.os.path.isdir')
  @mock.patch('fapfavorites.favorites.fapdata.ConvertUserName')
  @mock.patch('fapfavorites.favorites.fapdata.ConvertFavoritesName')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.Load')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.Save')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddUserByID')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddUserByName')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddFolderByID')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddFolderByName')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddFolderPics')
  @mock.patch('fapfavorites.favorites.fapdata.DownloadFavorites')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.DownloadAll')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.FindDuplicates')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddAllUserFolders')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.Audit')
  def test_GetOperation(
      self, audit: mock.MagicMock, add_all: mock.MagicMock, find_duplicates: mock.MagicMock,
      read_favorites: mock.MagicMock, download_favorites: mock.MagicMock,
      add_folder_pics: mock.MagicMock, add_folder_by_name: mock.MagicMock,
      add_folder_by_id: mock.MagicMock, add_user_by_name: mock.MagicMock,
      add_user_by_id: mock.MagicMock, save: mock.MagicMock, load: mock.MagicMock,
      convert_favorites: mock.MagicMock, convert_name: mock.MagicMock,
      mock_is_dir: mock.MagicMock) -> None:
    """Test."""
    mock_is_dir.return_value = True
    convert_name.return_value = 10
    convert_favorites.return_value = (20, 'some name')
    try:
      favorites.Main(  # pylint: disable=no-value-for-parameter
          ['get', '--user', 'foo', '--name', 'bar', '--output', '/path/'])
    except SystemExit as err:
      if err.code:  # pylint: disable=using-constant-test
        raise
    convert_name.assert_called_once_with('foo')
    convert_favorites.assert_called_once_with(10, 'bar')
    download_favorites.assert_called_once_with(10, 20, '/path/')
    mock_is_dir.assert_not_called()
    load.assert_not_called()
    save.assert_not_called()
    add_user_by_id.assert_not_called()
    add_folder_by_id.assert_not_called()
    add_folder_pics.assert_not_called()
    add_user_by_name.assert_not_called()
    add_folder_by_name.assert_not_called()
    read_favorites.assert_not_called()
    find_duplicates.assert_not_called()
    add_all.assert_not_called()
    audit.assert_not_called()

  @mock.patch('fapfavorites.favorites.fapdata.os.path.isdir')
  @mock.patch('fapfavorites.favorites.fapdata.ConvertUserName')
  @mock.patch('fapfavorites.favorites.fapdata.ConvertFavoritesName')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.Load')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.Save')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddUserByID')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddUserByName')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddFolderByID')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddFolderByName')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddFolderPics')
  @mock.patch('fapfavorites.favorites.fapdata.DownloadFavorites')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.DownloadAll')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.FindDuplicates')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddAllUserFolders')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.Audit')
  def test_ReadOperation(
      self, audit: mock.MagicMock, add_all: mock.MagicMock, find_duplicates: mock.MagicMock,
      read_favorites: mock.MagicMock, download_favorites: mock.MagicMock,
      add_folder_pics: mock.MagicMock, add_folder_by_name: mock.MagicMock,
      add_folder_by_id: mock.MagicMock, add_user_by_name: mock.MagicMock,
      add_user_by_id: mock.MagicMock, save: mock.MagicMock, load: mock.MagicMock,
      convert_favorites: mock.MagicMock, convert_name: mock.MagicMock,
      mock_is_dir: mock.MagicMock) -> None:
    """Test."""
    mock_is_dir.return_value = True
    add_user_by_name.return_value = (10, 'some-user')
    add_folder_by_name.return_value = (20, 'some-folder')
    add_all.return_value = {100, 200}
    read_favorites.return_value = 45394857
    try:
      favorites.Main(  # pylint: disable=no-value-for-parameter
          ['read', '--user', '"foo-user"', '--output', '/path/', '--force'])
    except SystemExit as err:
      if err.code:  # pylint: disable=using-constant-test
        raise
    self.assertListEqual(
        mock_is_dir.call_args_list,
        [mock.call('/path/'), mock.call('/path/blobs/'), mock.call('/path/thumbs/')])
    load.assert_called_once_with()
    add_user_by_name.assert_called_once_with('"foo-user"')
    self.assertListEqual(
        add_folder_pics.call_args_list, [mock.call(10, 100, True), mock.call(10, 200, True)])
    self.assertListEqual(
        read_favorites.call_args_list, [mock.call(10, 100, 10, True), mock.call(10, 200, 10, True)])
    add_all.assert_called_once_with(10, True)
    find_duplicates.assert_called_once_with()
    save.assert_called_once_with()
    convert_favorites.assert_not_called()
    convert_name.assert_not_called()
    add_user_by_id.assert_not_called()
    add_folder_by_id.assert_not_called()
    add_folder_by_name.assert_not_called()
    download_favorites.assert_not_called()
    audit.assert_not_called()

  @mock.patch('fapfavorites.favorites.fapdata.os.path.isdir')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.Load')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddUserByID')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddUserByName')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddFolderByID')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddFolderByName')
  @mock.patch('fapfavorites.favorites._GetOperation')
  @mock.patch('fapfavorites.favorites._ReadOperation')
  @mock.patch('fapfavorites.favorites._AuditOperation')
  def test_ReadOperation_ID_Call(
      self, audit_operation: mock.MagicMock, read_operation: mock.MagicMock,
      get_operation: mock.MagicMock, add_folder_by_name: mock.MagicMock,
      add_folder_by_id: mock.MagicMock, add_user_by_name: mock.MagicMock,
      add_user_by_id: mock.MagicMock, load: mock.MagicMock, mock_is_dir: mock.MagicMock) -> None:
    """Test."""
    mock_is_dir.return_value = True
    try:
      favorites.Main(  # pylint: disable=no-value-for-parameter
          ['read', '--id', '10', '--folder', '20', '--output', '/path/'])
    except SystemExit as err:
      if err.code:  # pylint: disable=using-constant-test
        raise
    self.assertListEqual(
        mock_is_dir.call_args_list,
        [mock.call('/path/'), mock.call('/path/blobs/'), mock.call('/path/thumbs/')])
    load.assert_called_once_with()
    add_user_by_id.assert_called_once_with(10)
    add_folder_by_id.assert_called_once_with(10, 20)
    read_operation.assert_called_once_with(mock.ANY, 10, 20, False)
    add_user_by_name.assert_not_called()
    audit_operation.assert_not_called()
    get_operation.assert_not_called()
    add_folder_by_name.assert_not_called()

  @mock.patch('fapfavorites.favorites.fapdata.os.path.isdir')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.Load')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddUserByID')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddUserByName')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddFolderByID')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddFolderByName')
  @mock.patch('fapfavorites.favorites._GetOperation')
  @mock.patch('fapfavorites.favorites._ReadOperation')
  @mock.patch('fapfavorites.favorites._AuditOperation')
  def test_ReadOperation_Folder_Name_Call(
      self, audit_operation: mock.MagicMock, read_operation: mock.MagicMock,
      get_operation: mock.MagicMock, add_folder_by_name: mock.MagicMock,
      add_folder_by_id: mock.MagicMock, add_user_by_name: mock.MagicMock,
      add_user_by_id: mock.MagicMock, load: mock.MagicMock, mock_is_dir: mock.MagicMock) -> None:
    """Test."""
    mock_is_dir.return_value = True
    add_folder_by_name.return_value = (20, 'Bar')
    try:
      favorites.Main(  # pylint: disable=no-value-for-parameter
          ['read', '--id', '10', '--name', 'bar', '--output', '/path/', '--force'])
    except SystemExit as err:
      if err.code:  # pylint: disable=using-constant-test
        raise
    self.assertListEqual(
        mock_is_dir.call_args_list,
        [mock.call('/path/'), mock.call('/path/blobs/'), mock.call('/path/thumbs/')])
    load.assert_called_once_with()
    add_user_by_id.assert_called_once_with(10)
    add_folder_by_name.assert_called_once_with(10, 'bar')
    read_operation.assert_called_once_with(mock.ANY, 10, 20, True)
    add_folder_by_id.assert_not_called()
    add_user_by_name.assert_not_called()
    audit_operation.assert_not_called()
    get_operation.assert_not_called()

  @mock.patch('fapfavorites.favorites.fapdata.os.path.isdir')
  @mock.patch('fapfavorites.favorites.fapdata.ConvertUserName')
  @mock.patch('fapfavorites.favorites.fapdata.ConvertFavoritesName')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.Load')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.Save')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddUserByID')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddUserByName')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddFolderByID')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddFolderByName')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddFolderPics')
  @mock.patch('fapfavorites.favorites.fapdata.DownloadFavorites')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.DownloadAll')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.FindDuplicates')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.AddAllUserFolders')
  @mock.patch('fapfavorites.favorites.fapdata.FapDatabase.Audit')
  def test_AuditOperation(
      self, audit: mock.MagicMock, add_all: mock.MagicMock, find_duplicates: mock.MagicMock,
      read_favorites: mock.MagicMock, download_favorites: mock.MagicMock,
      add_folder_pics: mock.MagicMock, add_folder_by_name: mock.MagicMock,
      add_folder_by_id: mock.MagicMock, add_user_by_name: mock.MagicMock,
      add_user_by_id: mock.MagicMock, save: mock.MagicMock, load: mock.MagicMock,
      convert_favorites: mock.MagicMock, convert_name: mock.MagicMock,
      mock_is_dir: mock.MagicMock) -> None:
    """Test."""
    mock_is_dir.return_value = True
    add_user_by_name.return_value = (10, 'some-user')
    try:
      favorites.Main(  # pylint: disable=no-value-for-parameter
          ['audit', '--user', '"foo-user"', '--output', '/path/'])
    except SystemExit as err:
      if err.code:  # pylint: disable=using-constant-test
        raise
    self.assertListEqual(
        mock_is_dir.call_args_list,
        [mock.call('/path/'), mock.call('/path/blobs/'), mock.call('/path/thumbs/')])
    load.assert_called_once_with()
    add_user_by_name.assert_called_once_with('"foo-user"')
    audit.assert_called_once_with(10, 100, False)
    save.assert_called_once_with()
    convert_favorites.assert_not_called()
    convert_name.assert_not_called()
    add_user_by_id.assert_not_called()
    add_folder_by_id.assert_not_called()
    add_folder_by_name.assert_not_called()
    add_folder_pics.assert_not_called()
    read_favorites.assert_not_called()
    find_duplicates.assert_not_called()
    download_favorites.assert_not_called()
    add_all.assert_not_called()


SUITE = unittest.TestLoader().loadTestsFromTestCase(TestFavorites)


if __name__ == '__main__':
  unittest.main()
