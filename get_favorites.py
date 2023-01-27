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
"""Imagefap.com image favorites (picture folder) dowloader."""

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


_DEFAULT_DB_NAME = 'imagefap.database'
_CHECKPOINT_LENGTH = 10


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
  print("Excuting GET command")
  database.AddFolderPics(user_id, folder_id)
  database.DownloadFavs(user_id, folder_id, output_path,
                        checkpoint_size=(_CHECKPOINT_LENGTH if make_db else 0))


@click.command()  # see `click` module usage in http://click.pocoo.org/
@click.argument('operation', type=click.Choice(['get']))
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
         'ex: "~/somedir/"; will default to current directory')
@click.option(
    '--db/--no-db', 'make_db', default=True,
    help='Save a imagefap.database file to output? Default is yes (--db). '
         'Keeping this option on will avoid duplication of download effort.')
@base.Timed('Total Imagefap get_favorites.py execution time')
def main(operation: str,
         user_name: str,
         user_id: int,
         favorites_name: str,
         folder_id: int,
         output_path: str,
         make_db: bool) -> None:  # noqa: D301
  """Download one imagefap.com image favorites (picture folder).

  ATTENTION: The script will deliberately pace its image fetching, taking
  much longer than required to download all images. This is done so to not
  be a bad imagefap.com customer (overload their servers). Be patient! Also,
  if you leave the database option on (recommended) you will only have to
  get a folder once, as subsequent calls will ignore known images, and the
  script will detect only new arrivals.

  You have to indicate the user by either the --user or the --id options.
  You have to indicate the image favorites (picture folder) by
  either the --name or the --folder options.

  Typical examples:

  \b
  ./imagefap-favorites.py get --user "somelogin" \\
      --name "Random Images" --output "~/somedir/"
  (in this case the login/name is used and a specific output is given)

  \b
  ./imagefap-favorites.py get --id 1234 --folder 5678
  (in this case specific numerical IDs are used and
   output will be the current directory)
  """
  print('***********************************************')
  print('**   GET IMAGEFAP FAVORITES PICTURE FOLDER   **')
  print('**   balparda@gmail.com (Daniel Balparda)    **')
  print('***********************************************')
  success_message = 'premature end? user paused?'
  random.seed()
  try:
    # check inputs, create output directory if needed
    if not user_name and not user_id:
      raise AttributeError('You have to provide either the --user or the --id options')
    if not favorites_name and not folder_id:
      raise AttributeError('You have to provide either the --name or the --folder options')
    output_path_expanded = os.path.expanduser(output_path)
    if os.path.isdir(output_path_expanded):
      logging.info('Output directory %r already exists', output_path)
    else:
      logging.info('Creating output directory %r', output_path)
      os.mkdir(output_path_expanded)
    db_path = os.path.join(output_path_expanded, _DEFAULT_DB_NAME)
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
      folder_id = database.AddFolderByName(user_id, favorites_name)[0]
    # we should now have both IDs that we need
    if operation.lower() == 'get':
      _GetOperation(database, user_id, folder_id, output_path_expanded, make_db)
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
