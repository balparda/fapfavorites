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
"""Imagefap.com image database operations."""

# import logging
import os
import os.path
# import pdb
import random

import click

from baselib import base
import fapdata


__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


def _StatsOperation(database: fapdata.FapDatabase) -> None:
  """Implement `stats` user operation: Print statistics.

  Args:
    database: Active fapdata.FapDatabase
  """
  print('Executing STATS command')
  print()
  print()
  database.PrintStats()
  print()
  print()


def _PrintOperation(database: fapdata.FapDatabase) -> None:
  """Implement `print` user operation: Print statistics.

  Args:
    database: Active fapdata.FapDatabase
  """
  print('Executing PRINT command')
  print()
  print()
  print('=' * 80)
  print('=' * 80)
  print()
  print('                             **** USERS & FAVORITES ****')
  print()
  database.PrintUsers()
  print()
  print('=' * 80)
  print()
  print('                             **** TAGS ****')
  print()
  database.PrintTags()
  print()
  print('=' * 80)
  print()
  print('                             **** IMAGE BLOBS METADATA ****')
  print()
  database.PrintBlobs()
  print()
  print('=' * 80)
  print('=' * 80)
  print()
  print()


@click.command()  # see `click` module usage in http://click.pocoo.org/
@click.argument('operation', type=click.Choice(['stats', 'print']))
@click.option(
    '--dir', '-d', 'db_dir', type=click.STRING, default='~/Downloads/imagefap/',
    help='The local machine database directory path to use, '
         'ex: "~/some-dir/"; will default to ~/Downloads/imagefap/')
@base.Timed('Total Imagefap process.py execution time')
def main(operation: str, db_dir: str) -> None:  # noqa: D301
  """imagefap.com database operations utility.

  This is intended to be used on a database that has been constructed
  by reading imagefap.com data. To construct a database, use the `get_favorites.py`
  utility.

  The `stats` command prints interesting info on the database's metadata.

  The `print` command will do a "pretty" print of useful database metadata
  for a closer inspection. Can print a lot for a big database!

  Typical examples:

  \b
  ./process.py stats --dir "~/some-dir/"
  (print statistics for database in "~/some-dir/")

  \b
  ./process.py print
  (pretty-print useful data from the default database location)
  """
  print('***********************************************')
  print('**    IMAGEFAP DATABASE PROCESSING UTILS     **')
  print('**   balparda@gmail.com (Daniel Balparda)    **')
  print('***********************************************')
  success_message = 'premature end? user paused?'
  random.seed()
  try:
    # check inputs, make sure we have a database to load
    db_dir_expanded = os.path.expanduser(db_dir)
    db_path = os.path.join(db_dir_expanded, fapdata.DEFAULT_DB_NAME)
    blob_path = os.path.join(db_dir_expanded, fapdata.DEFAULT_BLOB_DIR_NAME)
    if not os.path.isdir(db_dir_expanded):
      raise base.Error('Given database directory does not exist: %r' % db_dir)
    if not os.path.isdir(blob_path):
      raise base.Error('Database blobs directory does not exist: %r' % blob_path)
    if not os.path.exists(db_path):
      raise base.Error('Database file does not exist: %r' % db_path)
    # load database
    database = fapdata.FapDatabase(db_path)
    database.Load()
    # we should now have both IDs that we need
    if operation.lower() == 'stats':
      _StatsOperation(database)
    elif operation.lower() == 'print':
      _PrintOperation(database)
    else:
      raise NotImplementedError('Unrecognized/Unimplemented operation %r' % operation)
    # save DB and end
    database.Save()
    success_message = 'success'
  except Exception as e:
    success_message = 'error: ' + str(e)
    raise
  finally:
    print('THE END: ' + success_message)


if __name__ == '__main__':
  main()  # pylint: disable=no-value-for-parameter
