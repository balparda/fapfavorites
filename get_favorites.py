#!/usr/bin/python3 -O
#
# Copyright 2023 Daniel Balparda (balparda@gmail.com)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License 3 as published by
# the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see http://www.gnu.org/licenses/gpl-3.0.txt.
#
"""Imagefap.com image favorites (picture folder) downloader."""

import logging
import os
import os.path
# import pdb
import random

import click

from baselib import base
import fapdata


__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


def _GetOperation(database: fapdata.FapDatabase,
                  user_id: int,
                  folder_id: int,
                  output_path: str,
                  make_db: bool) -> None:
  """Implement `get` user operation: Straight download into a destination directory.

  Args:
    database: Active fapdata.FapDatabase
    user_id: User ID
    folder_id: Folder ID
    output_path: Output path
    make_db: The user option to save DB or not
  """
  print('Executing GET command')
  database.AddFolderPics(user_id, folder_id)
  database.DownloadFavorites(
      user_id, folder_id, output_path,
      checkpoint_size=(fapdata.CHECKPOINT_LENGTH if make_db else 0), save_as_blob=False)


def _ReadOperation(database: fapdata.FapDatabase,
                   user_id: int,
                   folder_id: int,
                   blob_path: str) -> None:
  """Implement `read` user operation: Read into database either one or all favorites.

  Args:
    database: Active fapdata.FapDatabase
    user_id: User ID
    folder_id: Folder ID
    blob_path: Blob directory path
  """
  # create blob directory, if needed
  if os.path.isdir(blob_path):
    logging.info('Blob directory %r already exists', blob_path)
  else:
    logging.info('Creating blob directory %r', blob_path)
    os.mkdir(blob_path)
  # start
  print('Executing READ command')
  found_folder_ids: set[int] = {folder_id} if folder_id else database.AddAllUserFolders(user_id)
  for f_id in sorted(found_folder_ids):
    database.AddFolderPics(user_id, f_id)
    database.DownloadFavorites(
        user_id, f_id, blob_path, checkpoint_size=fapdata.CHECKPOINT_LENGTH, save_as_blob=True)


@click.command()  # see `click` module usage in http://click.pocoo.org/
@click.argument('operation', type=click.Choice(['get', 'read']))
@click.option(
    '--user', '-u', 'user_name', type=click.STRING, default='',
    help='The imagefap.com user name, as found in https://www.imagefap.com/profile/USER; '
         'we can\'t yet properly deal with HTML escaping names, so be aware of this')
@click.option(
    '--id', '-i', 'user_id', type=click.INT, default=0,
    help='The imagefap.com user ID, as found in '
         'https://www.imagefap.com/showfavorites.php?userid=ID&folderid=FOLDER')
@click.option(
    '--name', '-n', 'favorites_name', type=click.STRING, default='',
    help='The user\'s image favorites (picture folder) name, ex: "Random Images"; '
         'we can\'t yet properly deal with HTML escaping names, so be aware of this')
@click.option(
    '--folder', '-f', 'folder_id', type=click.INT, default=0,
    help='The imagefap.com folder ID, as found in '
         'https://www.imagefap.com/showfavorites.php?userid=ID&folderid=FOLDER')
@click.option(
    '--output', '-o', 'output_path', type=click.STRING, default='~/Downloads/imagefap/',
    help='The intended local machine output directory path, '
         'ex: "~/some-dir/"; will default to ~/Downloads/imagefap/')
@click.option(
    '--db/--no-db', 'make_db', default=True,
    help='Save a imagefap.database file to output? Default is yes (--db); '
         'keeping this option on will avoid duplication of download effort; '
         'you can\'t disable the DB for the `read` command')
@base.Timed('Total Imagefap get_favorites.py execution time')
def main(operation: str,  # noqa: C901
         user_name: str,
         user_id: int,
         favorites_name: str,
         folder_id: int,
         output_path: str,
         make_db: bool) -> None:  # noqa: D301
  """Download imagefap.com image favorites (picture folder).

  ATTENTION: The script will deliberately pace its image fetching, taking
  much longer than required to download all images. This is done so to not
  be a bad imagefap.com customer (overload their servers). Be patient! Also,
  if you leave the database option on (recommended) you will only have to
  get a folder once, as subsequent calls will ignore known images, and the
  script will detect only new arrivals.

  You have to indicate the user by either the --user or the --id options.
  You have to indicate the image favorites (picture folder) by
  either the --name or the --folder options if you are using `get`.
  If you are using `read` then you can specify only the user and
  let it browse for all image favorite galleries.

  Typical examples:

  \b
  ./get_favorites.py get --user "some-login" \\
      --name "Random Images" --output "~/some-dir/"
  (in this case the login/name is used and a specific output is given)

  \b
  ./get_favorites.py get --id 1234 --folder 5678
  (in this case specific numerical IDs are used and
   output will be the current directory)

  \b
  ./get_favorites.py read --user "some-login"
  (in this case, will find all image favorite galleries for this user
   and place them in the database;)
  """
  print('***********************************************')
  print('**   GET IMAGEFAP FAVORITES PICTURE FOLDER   **')
  print('**   balparda@gmail.com (Daniel Balparda)    **')
  print('***********************************************')
  success_message = 'premature end? user paused?'
  random.seed()
  try:
    # check inputs
    if not user_name and not user_id:
      raise AttributeError('You have to provide either the --user or the --id options')
    if user_name and user_id:
      raise AttributeError('You should not provide both the --user and the --id options')
    if (not favorites_name and not folder_id) and operation.lower() != 'read':
      raise AttributeError('You have to provide either the --name or the --folder options')
    if favorites_name and folder_id:
      raise AttributeError('You should not provide both the --name and the --folder options')
    if not make_db and operation.lower() == 'read':
      raise AttributeError('The `read` command requires a database (--db option)')
    # create output directory, if needed
    output_path_expanded = os.path.expanduser(output_path)
    if os.path.isdir(output_path_expanded):
      logging.info('Output directory %r already exists', output_path)
    else:
      logging.info('Creating output directory %r', output_path)
      os.mkdir(output_path_expanded)
    db_path = os.path.join(output_path_expanded, fapdata.DEFAULT_DB_NAME)
    blob_path = os.path.join(output_path_expanded, fapdata.DEFAULT_BLOB_DIR_NAME)
    # load database, if any
    database = fapdata.FapDatabase(db_path)
    database.Load()
    # convert user to id and convert name to folder, if needed
    if user_id:
      database.AddUserByID(user_id)
    else:
      user_id = database.AddUserByName(user_name)[0]
    if folder_id:
      database.AddFolderByID(user_id, folder_id)
    else:
      if favorites_name:
        folder_id = database.AddFolderByName(user_id, favorites_name)[0]
    # we should now have both IDs that we need
    if operation.lower() == 'get':
      _GetOperation(database, user_id, folder_id, output_path_expanded, make_db)
    elif operation.lower() == 'read':
      _ReadOperation(database, user_id, folder_id, blob_path)
    else:
      raise NotImplementedError('Unrecognized/Unimplemented operation %r' % operation)
    # save DB and end
    if make_db:
      database.Save()
    success_message = 'success'
  except Exception as e:
    success_message = 'error: ' + str(e)
    raise
  finally:
    print('THE END: ' + success_message)


if __name__ == '__main__':
  main()  # pylint: disable=no-value-for-parameter
