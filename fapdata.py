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
"""Imagefap.com database."""

import hashlib
import html
import http.client
import logging
import math
import os
import os.path
# import pdb
import random
import re
import shutil
import socket
import statistics
import tempfile
import time
from typing import Iterator, Literal, Optional, TypedDict
import urllib.error
import urllib.request

from PIL import Image, ImageSequence
import numpy as np
import sanitize_filename

from baselib import base
import duplicates


__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


# useful globals
DEFAULT_DB_DIRECTORY = '~/Downloads/imagefap/'
_DEFAULT_DB_NAME = 'imagefap.database'
_DEFAULT_BLOB_DIR_NAME = 'blobs/'
DEFAULT_THUMBS_DIR_NAME = 'thumbs/'
_THUMBNAIL_MAX_DIMENSION = 280
_MAX_RETRY = 10         # int number of retries for URL get
_URL_TIMEOUT = 15.0     # URL timeout, in seconds
CHECKPOINT_LENGTH = 10  # int number of images to download between database checkpoints
_PAGE_BACKTRACKING_THRESHOLD = 5
FAVORITES_MIN_DOWNLOAD_WAIT = 3 * (60 * 60 * 24)  # 3 days (in seconds)

# internal types definitions
LocationTupleType = tuple[int, str, str, int, int]
FailedTupleType = tuple[int, int, Optional[str], Optional[str]]


class _UserObjType(TypedDict):
  """User object type."""

  name: str
  date_albums: int
  date_finished: int


class _FavoriteObjType(TypedDict):
  """Favorite object type."""

  name: str
  pages: int
  date_straight: int
  date_blobs: int
  images: list[int]
  failed_images: set[FailedTupleType]


class TagObjType(TypedDict):
  """Tag object type."""

  name: str
  tags: dict[int, dict]


class _BlobObjType(TypedDict):
  """Blob object type."""

  loc: set[LocationTupleType]
  tags: set[int]
  sz: int
  sz_thumb: int
  ext: str
  percept: str
  average: str
  diff: str
  wavelet: str
  cnn: np.ndarray
  width: int
  height: int
  animated: bool


_UserType = dict[int, _UserObjType]
_FavoriteType = dict[int, dict[int, _FavoriteObjType]]
_TagType = dict[int, TagObjType]
_BlobType = dict[str, _BlobObjType]
_ImagesIdIndexType = dict[int, str]
_DB_MAIN_KEYS = {'users', 'favorites', 'tags', 'blobs', 'image_ids_index',
                 'duplicates_registry', 'duplicates_key_index'}


class _DatabaseType(TypedDict):
  """Database type."""

  users: _UserType
  favorites: _FavoriteType
  tags: _TagType
  blobs: _BlobType
  image_ids_index: _ImagesIdIndexType
  duplicates_registry: duplicates.DuplicatesType
  duplicates_key_index: duplicates.DuplicatesKeyIndexType


# the site page templates we need
_USER_PAGE_URL = lambda n: 'https://www.imagefap.com/profile/%s' % n
_FAVORITES_URL = (
    lambda u, p: 'https://www.imagefap.com/showfavorites.php?userid=%d&page=%d' % (u, p))
_FOLDER_URL = lambda u, f, p: '%s&folderid=%d' % (_FAVORITES_URL(u, p), f)  # cspell:disable-line
IMG_URL = lambda id: 'https://www.imagefap.com/photo/%d/' % id

# the regular expressions we use to navigate the pages
_FIND_ONLY_IN_PICTURE_FOLDER = re.compile(r'<\/a><\/td><\/tr>\s+<\/table>\s+<table')
_FIND_ONLY_IN_GALLERIES_FOLDER = re.compile(
    r'<td\s+class=.blk_favorites_hdr.*<b>Gallery Name<\/span>')
_FIND_NAME_IN_FAVORITES = re.compile(
    r'<a\s+class=.blk_header.\s+href="\/profile\.php\?user=(.*)"\s+style="')
_FIND_USER_ID_RE = re.compile(  # cspell:disable-next-line
    r'<a\s+class=.blk_header.\s+href="\/showfavorites.php\?userid=([0-9]+)".*>')
_FIND_ACTUAL_NAME = re.compile(r'<td\s+class=.blk_profile_hdr.*>(.*)\sProfile\s+<\/td>')
_FIND_NAME_IN_FOLDER = re.compile(
    r'<a\s+class=.blk_favorites.\s+href=".*none;">(.*)<\/a><\/td><\/tr>')
_FIND_FOLDERS = re.compile(
    r'<td\s+class=.blk_favorites.><a\s+class=.blk_galleries.\s+href="'
    r'https:\/\/www.imagefap.com\/showfavorites.php\?userid=[0-9]+'  # cspell:disable-line
    r'&folderid=([0-9]+)".*>(.*)<\/a><\/td>')                        # cspell:disable-line
_FAVORITE_IMAGE = re.compile(r'<td\s+class=.blk_favorites.\s+id="img-([0-9]+)"\s+align=')
_FULL_IMAGE = re.compile(
    r'<img\s+id="mainPhoto".*src="(https:\/\/.*\/images\/full\/.*)">')
_IMAGE_NAME = re.compile(
    r'<meta\s+name="description"\s+content="View this hot (.*) porn pic uploaded by')


class Error(base.Error):
  """Base fap exception."""


class Error404(Error):
  """Imagefap HTTP 404 exception."""

  def __init__(self, url: str):
    """Construct a 404 error."""
    self.image_id: Optional[int] = None
    self.timestamp: int = base.INT_TIME()
    self.image_name: Optional[str] = None
    self.url: str = url

  def __str__(self) -> str:
    """Get string representation."""
    failure = self.FailureTuple()
    return 'Error404(ID: %d, @%s, %r, %r)' % (
        failure[0],
        base.STD_TIME_STRING(failure[1]),
        '-' if failure[2] is None else failure[2],
        '-' if failure[3] is None else failure[3])

  def FailureTuple(self) -> FailedTupleType:
    """Get a failure tuple for this 404."""
    return (
        0 if self.image_id is None else self.image_id,
        self.timestamp,
        self.image_name,
        self.url)


class FapDatabase:
  """Imagefap.com database."""

  def __init__(self, dir_path: str, create_if_needed: bool = True):
    """Construct a clean database. Does *not* load or save or create/check files at this stage.

    Also initializes random number generator, as it should only be called once anyway.

    Args:
      path: The directory path to load/save DB and images from/to
      create_if_needed: (default True) If True, Creates DB directory if not present;
          If False, will raise Error if not present

    Raises:
      AttributeError: on empty dir_path, or for create_if_needed==False, if dir_path not present
    """
    random.seed()
    if not dir_path:
      raise AttributeError('Output directory path cannot be empty')
    logging.info('Initializing database. Output directory will be: %r', dir_path)
    # start with a clean DB; see README.md for format
    self._original_dir = dir_path                                            # what the user gave us
    self._db_dir = os.path.expanduser(self._original_dir)                    # where to put DB
    self._db_path = os.path.join(self._db_dir, _DEFAULT_DB_NAME)             # actual DB path
    self._blobs_dir = os.path.join(self._db_dir, _DEFAULT_BLOB_DIR_NAME)     # where to put blobs
    self._thumbs_dir = os.path.join(self._db_dir, DEFAULT_THUMBS_DIR_NAME)   # thumbnails dir
    self._db: _DatabaseType = {  # creates empty DB
        'users': {},
        'favorites': {},
        'tags': {},
        'blobs': {},
        'image_ids_index': {},
        'duplicates_registry': {},
        'duplicates_key_index': {},
    }
    self.duplicates = duplicates.Duplicates(self._duplicates_registry, self._duplicates_key_index)
    # check output directory, create if needed
    if not os.path.isdir(self._db_dir):
      if not create_if_needed:
        raise Error('Output directory %r does not exist' % self._original_dir)
      logging.info('Creating output directory %r', self._original_dir)
      os.mkdir(self._db_dir)
    # save to environment
    os.environ['IMAGEFAP_FAVORITES_DB_PATH'] = self._original_dir

  @property
  def users(self) -> _UserType:
    """Users dictionary."""
    return self._db['users']

  @property
  def favorites(self) -> _FavoriteType:
    """Favorites dictionary."""
    return self._db['favorites']

  @property
  def tags(self) -> _TagType:
    """Tags dictionary."""
    return self._db['tags']

  @property
  def blobs(self) -> _BlobType:
    """Blobs dictionary."""
    return self._db['blobs']

  @property
  def image_ids_index(self) -> _ImagesIdIndexType:
    """Images IDs index dictionary."""
    return self._db['image_ids_index']

  @property
  def _duplicates_registry(self) -> duplicates.DuplicatesType:
    """Duplicates dictionary."""
    return self._db['duplicates_registry']

  @property
  def _duplicates_key_index(self) -> duplicates.DuplicatesKeyIndexType:
    """Duplicates key index."""
    return self._db['duplicates_key_index']

  @property
  def blobs_dir_exists(self) -> bool:
    """True if blobs directory path is in existence."""
    return os.path.isdir(self._blobs_dir)

  @property
  def thumbs_dir_exists(self) -> bool:
    """True if thumbnails directory path is in existence."""
    return os.path.isdir(self._thumbs_dir)

  def Load(self) -> bool:
    """Load DB from file. If no DB file does not do anything.

    Returns:
      True if a file was found and loaded, False if not

    Raises:
      Error: if found DB does not check out
    """
    if os.path.exists(self._db_path):
      self._db: _DatabaseType = base.BinDeSerialize(file_path=self._db_path)
      # just a quick dirty check that we got what we expected
      if any(k not in self._db for k in _DB_MAIN_KEYS):
        raise Error('Loaded DB is invalid!')
      self.duplicates = duplicates.Duplicates(  # has to be reloaded!
          self._duplicates_registry, self._duplicates_key_index)
      logging.info('Loaded DB from %r', self._db_path)
      return True
    logging.warning('No DB found in %r', self._db_path)
    return False

  def Save(self) -> None:
    """Save DB to file."""
    base.BinSerialize(self._db, self._db_path)
    logging.info('Saved DB to %r', self._db_path)

  def UserStr(self, user_id: int) -> str:
    """Produce standard user representation, like 'UserName (id)'."""
    try:
      return '%s (%d)' % (self.users[user_id]['name'], user_id)
    except KeyError:
      raise Error('User %d not found' % user_id)

  def AlbumStr(self, user_id: int, folder_id: int) -> str:
    """Produce standard album representation, like 'UserName/FolderName (uid/fid)'."""
    try:
      return '%s/%s (%d/%d)' % (
          self.users[user_id]['name'], self.favorites[user_id][folder_id]['name'],
          user_id, folder_id)
    except KeyError:
      raise Error('Album %d/%d not found' % (user_id, folder_id))

  def LocationStr(self, loc: LocationTupleType) -> str:
    """Produce standard location repr, like 'UserName/FolderName/ImageName (uid/fid/img_id)'."""
    try:
      return '%s/%s/%s (%d/%d/%d)' % (
          self.users[loc[3]]['name'], self.favorites[loc[3]][loc[4]]['name'],
          loc[2], loc[3], loc[4], loc[0])
    except KeyError:
      raise Error('Location %s had inconsistencies' % repr(loc))

  def TagStr(self, tag_id: int, add_id: bool = True) -> str:
    """Produce standard tag representation, like 'TagName (id)'."""
    name = self.GetTag(tag_id)[-1][1]
    return '%s (%d)' % (name, tag_id) if add_id else name

  def TagLineageStr(self, tag_id: int, add_id: bool = True) -> str:
    """Print tag name together with parents, like 'grand_name/parent_name/tag_name (id)'."""
    name = '/'.join(n for _, n, _ in self.GetTag(tag_id))
    return '%s (%d)' % (name, tag_id) if add_id else name

  def _BlobPath(self, sha: str) -> str:
    """Get full file path for a blob hash (`sha`)."""
    try:
      return os.path.join(self._blobs_dir, '%s.%s' % (sha, self.blobs[sha]['ext']))
    except KeyError:
      raise Error('Blob %r not found' % sha)

  def ThumbnailPath(self, sha: str) -> str:
    """Get full file path for a thumbnail, based on its blob hash (`sha`)."""
    try:
      return os.path.join(self._thumbs_dir, '%s.%s' % (sha, self.blobs[sha]['ext']))
    except KeyError:
      raise Error('Blob %r not found' % sha)

  def HasBlob(self, sha: str) -> bool:
    """Check if blob `sha` is available in blobs/ directory."""
    return os.path.exists(self._BlobPath(sha))

  def GetBlob(self, sha: str) -> bytes:
    """Get the blob binary data for `sha` entry."""
    with open(self._BlobPath(sha), 'rb') as f:
      return f.read()

  def GetTag(self, tag_id: int) -> list[tuple[int, str, TagObjType]]:  # noqa: C901
    """Search recursively for specific tag object, returning parents too, if any.

    Args:
      tag_id: The wanted tag ID

    Returns:
      list of (id, name, tag_obj), starting with the parents and ending with the wanted tag;
      this means that GetTag(id)[-1] is always the wanted tag tuple

    Raises:
      Error: not found or invalid
    """
    hierarchy: list[tuple[int, str, TagObjType]] = []

    def _get_recursive(obj: _TagType) -> bool:
      if tag_id in obj:
        try:
          hierarchy.append((tag_id, obj[tag_id]['name'], obj[tag_id]))  # found!
        except KeyError:
          raise Error('Found tag %d is empty (has no \'name\')!' % tag_id)
        return True
      for i, o in obj.items():
        if o.get('tags', {}):
          if _get_recursive(o['tags']):  # type: ignore
            try:
              hierarchy.append((i, o['name'], o))  # parent to a found tag
            except KeyError:
              raise Error('Parent tag %d (of %d) is empty (has no \'name\')!' % (i, tag_id))
            return True
      return False

    if not _get_recursive(self.tags):
      raise Error('Tag ID %d was not found' % tag_id)
    hierarchy.reverse()
    return hierarchy

  def TagsWalk(
      self, start_tag: Optional[_TagType] = None, depth: int = 0) -> Iterator[
          tuple[int, str, int, _TagType]]:
    """Walk all tags recursively, depth first.

    Args:
      start_tag: (Default None) The tag to start at; None means start at root
      depth: (Default 0) DO NOT USE - Internal depth count

    Yields:
      (tag_id, tag_name, depth, sub_tags)
    """
    if start_tag is None:
      start_tag = self.tags
    for tag_name, tag_id, tag_tags in sorted(
        (t['name'], k, t['tags']) for k, t in start_tag.items()):  # will sort by name in this level
      yield (tag_id, tag_name, depth, tag_tags)  # type: ignore
      if start_tag[tag_id]['tags']:
        for o in self.TagsWalk(
            start_tag=start_tag[tag_id]['tags'], depth=(depth + 1)):  # type: ignore
          yield o

  def PrintStats(self, actually_print=True) -> list[str]:
    """Print database stats.

    Args:
      actually_print: (default True) If true will print() the lines; else won't

    Returns:
      list of strings to print as status
    """
    file_sizes: list[int] = [s['sz'] for s in self.blobs.values()]
    thumb_sizes: list[int] = [s['sz_thumb'] for s in self.blobs.values()]
    all_files_size, all_thumb_size = sum(file_sizes), sum(thumb_sizes)
    db_size = os.path.getsize(self._db_path)
    all_lines: list[str] = []

    def _PrintLine(line: str = ''):
      all_lines.append(line)
      if actually_print:
        print(line)

    _PrintLine('Database is located in %r, and is %s (%0.3f%% of total images size)' % (
        self._db_path, base.HumanizedBytes(db_size),
        (100.0 * db_size) / (all_files_size if all_files_size else 1)))
    _PrintLine(
        '%s total (unique) images size (%s min, %s max, '
        '%s mean with %s standard deviation, %d are animated)' % (
            base.HumanizedBytes(all_files_size),
            base.HumanizedBytes(min(file_sizes)) if file_sizes else '-',
            base.HumanizedBytes(max(file_sizes)) if file_sizes else '-',
            base.HumanizedBytes(int(statistics.mean(file_sizes))) if file_sizes else '-',
            base.HumanizedBytes(int(statistics.stdev(file_sizes))) if len(file_sizes) > 2 else '-',
            sum(int(s['animated']) for s in self.blobs.values())))
    if file_sizes:
      wh_sizes: list[tuple[int, int]] = [
          (s['width'], s['height']) for s in self.blobs.values()]
      pixel_sizes: list[int] = [
          s['width'] * s['height'] for s in self.blobs.values()]
      _PrintLine(
          'Pixel size (width, height): %s pixels min %r, %s pixels max %r, '  # cspell:disable-line
          '%s mean with %s standard deviation' % (
              base.HumanizedDecimal(min(pixel_sizes)),
              wh_sizes[pixel_sizes.index(min(pixel_sizes))],
              base.HumanizedDecimal(max(pixel_sizes)),
              wh_sizes[pixel_sizes.index(max(pixel_sizes))],
              base.HumanizedDecimal(int(statistics.mean(pixel_sizes))),
              base.HumanizedDecimal(
                  int(statistics.stdev(pixel_sizes))) if len(pixel_sizes) > 2 else '-'))
    if all_files_size and all_thumb_size:
      _PrintLine(
          '%s total thumbnail size (%s min, %s max, %s mean with %s standard deviation), '
          '%0.1f%% of total images size' % (
              base.HumanizedBytes(all_thumb_size),
              base.HumanizedBytes(min(thumb_sizes)) if thumb_sizes else '-',
              base.HumanizedBytes(max(thumb_sizes)) if thumb_sizes else '-',
              base.HumanizedBytes(int(statistics.mean(thumb_sizes))) if thumb_sizes else '-',
              base.HumanizedBytes(
                  int(statistics.stdev(thumb_sizes))) if len(thumb_sizes) > 2 else '-',
              (100.0 * all_thumb_size) / all_files_size))
    _PrintLine()
    _PrintLine('%d users' % len(self.users))
    all_dates = [max(f['date_straight'], f['date_blobs'])
                 for u in self.favorites.values() for f in u.values()]
    min_date = min(all_dates) if all_dates else 0
    max_date = max(all_dates) if all_dates else 0
    _PrintLine('%d favorite galleries (oldest: %s / newer: %s)' % (
        sum(len(f) for _, f in self.favorites.items()),
        base.STD_TIME_STRING(min_date) if min_date else 'pending',
        base.STD_TIME_STRING(max_date) if max_date else 'pending'))
    _PrintLine('%d unique images (%d total, %d exact duplicates)' % (
        len(self.blobs),
        sum(len(b['loc']) for _, b in self.blobs.items()),
        sum(len(b['loc']) - 1 for _, b in self.blobs.items())))
    unique_failed: set[int] = set()
    for failed in (
        fav['failed_images'] for user in self.favorites.values() for fav in user.values()):
      unique_failed.update(img for img, _, _, _ in failed)
    _PrintLine('%d unique failed images in all user albums' % len(unique_failed))
    _PrintLine('%d perceptual duplicates in %d groups' % (
        len(self.duplicates.index), len(self.duplicates.registry)))
    return all_lines

  def PrintUsersAndFavorites(self, actually_print=True) -> list[str]:
    """Print database users.

    Args:
      actually_print: (default True) If true will print() the lines; else won't

    Returns:
      list of strings to print as status
    """
    all_lines: list[str] = []

    def _PrintLine(line: str = ''):
      all_lines.append(line)
      if actually_print:
        print(line)

    _PrintLine('ID: USER_NAME')
    _PrintLine('    FILE STATS FOR USER')
    _PrintLine('    => ID: FAVORITE_NAME (IMAGE_COUNT / FAILED_COUNT / PAGE_COUNT / DATE DOWNLOAD)')
    _PrintLine('           FILE STATS FOR FAVORITES')
    for uid in sorted(self.users.keys()):
      _PrintLine()
      _PrintLine('%d: %r' % (uid, self.users[uid]['name']))
      file_sizes: list[int] = [
          self.blobs[self.image_ids_index[i]]['sz']
          for d, u in self.favorites.items() if d == uid
          for f in u.values()
          for i in f['images'] if i in self.image_ids_index]
      _PrintLine('    %s files size (%s min, %s max, %s mean with %s standard deviation)' % (
          base.HumanizedBytes(sum(file_sizes) if file_sizes else 0),
          base.HumanizedBytes(min(file_sizes)) if file_sizes else '-',
          base.HumanizedBytes(max(file_sizes)) if file_sizes else '-',
          base.HumanizedBytes(int(statistics.mean(file_sizes))) if file_sizes else '-',
          base.HumanizedBytes(int(statistics.stdev(file_sizes))) if len(file_sizes) > 2 else '-'))
      for fid in sorted(self.favorites.get(uid, {}).keys()):
        obj = self.favorites[uid][fid]
        file_sizes: list[int] = [
            self.blobs[self.image_ids_index[i]]['sz']
            for i in obj['images'] if i in self.image_ids_index]
        _PrintLine('    => %d: %r (%d / %d / %d / %s)' % (
            fid, obj['name'], len(obj['images']), len(obj['failed_images']), obj['pages'],
            base.STD_TIME_STRING(max(obj['date_straight'], obj['date_blobs']))
            if obj['date_straight'] or obj['date_blobs'] else 'pending'))
        if file_sizes:
          _PrintLine(
              '           %s files size (%s min, %s max, %s mean with %s standard deviation)' % (
                  base.HumanizedBytes(sum(file_sizes)),
                  base.HumanizedBytes(min(file_sizes)),
                  base.HumanizedBytes(max(file_sizes)),
                  base.HumanizedBytes(int(statistics.mean(file_sizes))),
                  base.HumanizedBytes(
                      int(statistics.stdev(file_sizes))) if len(file_sizes) > 2 else '-'))
    return all_lines

  def PrintTags(self, actually_print=True) -> list[str]:
    """Print database tags.

    Args:
      actually_print: (default True) If true will print() the lines; else won't

    Returns:
      list of strings to print as status
    """
    all_lines: list[str] = []

    def _PrintLine(line: str = ''):
      all_lines.append(line)
      if actually_print:
        print(line)

    if not self.tags:
      _PrintLine('NO TAGS CREATED')
      return all_lines
    _PrintLine('TAG_ID: TAG_NAME (NUMBER_OF_IMAGES_WITH_TAG / SIZE_OF_IMAGES_WITH_TAG)')
    _PrintLine()
    for tag_id, tag_name, depth, _ in self.TagsWalk():
      count: int = 0
      sz: int = 0
      for blob in self.blobs.values():
        if tag_id in blob['tags']:
          count += 1
          sz += blob['sz']
      _PrintLine('%s%d: %r (%d / %s)' % (
          '    ' * depth, tag_id, tag_name, count, base.HumanizedBytes(sz)))
    return all_lines

  def PrintBlobs(self, actually_print=True) -> list[str]:
    """Print database blobs metadata.

    Args:
      actually_print: (default True) If true will print() the lines; else won't

    Returns:
      list of strings to print as status
    """
    all_lines: list[str] = []

    def _PrintLine(line: str = ''):
      all_lines.append(line)
      if actually_print:
        print(line)

    _PrintLine('SHA256_HASH: ID1/\'NAME1\' or ID2/\'NAME2\' or ..., PIXELS '
               '(WIDTH, HEIGHT) [ANIMATED]')
    _PrintLine('    => {\'TAG1\', \'TAG2\', ...}')
    _PrintLine()
    for sha in sorted(self.blobs.keys()):
      blob = self.blobs[sha]
      _PrintLine('%s: %s, %s %r%s' % (
          sha, ' or '.join(self.LocationStr(loc)
                           for loc in sorted(blob['loc'], key=lambda x: (x[0], x[3], x[4]))),
          base.HumanizedDecimal(blob['width'] * blob['height']),
          (blob['width'], blob['height']),
          ' animated' if blob['animated'] else ''))
      if blob['tags']:
        _PrintLine('    => {%s}' % ', '.join(self.TagStr(tid) for tid in sorted(blob['tags'])))
    return all_lines

  def AddUserByID(self, user_id: int) -> str:
    """Add user by ID and find user name in the process.

    Args:
      user_id: The user ID

    Returns:
      actual user name

    Raises:
      Error: if conversion failed
    """
    if user_id in self.users:
      status = 'Known'
    else:
      status = 'New'
      url: str = _FAVORITES_URL(user_id, 0)  # use the favorites page
      logging.info('Fetching favorites page: %s', url)
      user_html = _FapHTMLRead(url)
      user_names: list[str] = _FIND_NAME_IN_FAVORITES.findall(user_html)
      if len(user_names) != 1:
        raise Error('Could not find user name for %d' % user_id)
      self.users[user_id] = {
          'name': html.unescape(user_names[0]), 'date_albums': 0, 'date_finished': 0}
    logging.info('%s user %s added', status, self.UserStr(user_id))
    return self.users[user_id]['name']

  def AddUserByName(self, user_name: str) -> tuple[int, str]:
    """Add user by handle. Find user ID in the process.

    Args:
      user_name: The given user name

    Returns:
      (int user ID, actual user name)

    Raises:
      Error: if conversion failed
    """
    # first try to find in DB
    for uid, user in self.users.items():
      if user['name'].lower() == user_name.lower():
        logging.info('Known user %s', self.UserStr(uid))
        return (uid, user['name'])
    # not found: we have to find in actual site
    url: str = _USER_PAGE_URL(user_name)
    logging.info('Fetching user page: %s', url)
    user_html = _FapHTMLRead(url)
    user_ids: list[str] = _FIND_USER_ID_RE.findall(user_html)
    if len(user_ids) != 1:
      raise Error('Could not find ID for user %r' % user_name)
    uid = int(user_ids[0])
    actual_name: list[str] = _FIND_ACTUAL_NAME.findall(user_html)
    if len(actual_name) != 1:
      raise Error('Could not find actual display name for user %r' % user_name)
    self.users[uid] = {
        'name': html.unescape(actual_name[0]), 'date_albums': 0, 'date_finished': 0}
    logging.info('New user %s added', self.UserStr(uid))
    return (uid, self.users[uid]['name'])

  def AddFolderByID(self, user_id: int, folder_id: int) -> str:
    """Add folder by ID and find folder name in the process.

    Args:
      user_id: User int ID
      folder_id: Folder int ID

    Returns:
      actual folder name

    Raises:
      Error: if conversion failed
    """
    if folder_id in self.favorites.get(user_id, {}):
      status = 'Known'
    else:
      status = 'New'
      url: str = _FOLDER_URL(user_id, folder_id, 0)  # use the folder page
      logging.info('Fetching favorites page: %s', url)
      folder_html = _FapHTMLRead(url)
      folder_names: list[str] = _FIND_NAME_IN_FOLDER.findall(folder_html)
      if len(folder_names) != 1:
        raise Error('Could not find folder name for %d/%d' % (user_id, folder_id))
      _CheckFolderIsForImages(user_id, folder_id)  # raises Error if not valid
      self.favorites.setdefault(user_id, {})[folder_id] = {
          'name': html.unescape(folder_names[0]), 'pages': 0,
          'date_straight': 0, 'date_blobs': 0, 'images': [], 'failed_images': set()}
    logging.info('%s folder %s added', status, self.AlbumStr(user_id, folder_id))
    return self.favorites[user_id][folder_id]['name']

  def AddFolderByName(self, user_id: int, favorites_name: str) -> tuple[int, str]:
    """Add picture folder by name. Find folder ID in the process.

    Args:
      user_id: The user's int ID
      favorites_name: The given picture folder name

    Returns:
      (int picture folder ID, actual folder name)

    Raises:
      Error: if conversion failed
    """
    # first try to find in DB
    if user_id in self.favorites:
      for fid, f_data in self.favorites[user_id].items():
        if f_data['name'].lower() == favorites_name.lower():
          logging.info('Known folder %s', self.AlbumStr(user_id, fid))
          return (fid, f_data['name'])
    # not found: we have to find in actual site
    page_num: int = 0
    while True:
      url: str = _FAVORITES_URL(user_id, page_num)
      logging.info('Fetching favorites page: %s', url)
      fav_html = _FapHTMLRead(url)
      favorites_page: list[tuple[str, str]] = _FIND_FOLDERS.findall(fav_html)
      if not favorites_page:
        raise Error('Could not find picture folder %r for user %d' % (favorites_name, user_id))
      for f_id, f_name in favorites_page:
        i_f_id, f_name = int(f_id), html.unescape(f_name)
        if f_name.lower() == favorites_name.lower():
          # found it!
          _CheckFolderIsForImages(user_id, i_f_id)  # raises Error if not valid
          self.favorites.setdefault(user_id, {})[i_f_id] = {
              'name': f_name, 'pages': 0, 'date_straight': 0, 'date_blobs': 0,
              'images': [], 'failed_images': set()}
          logging.info('New folder %s added', self.AlbumStr(user_id, i_f_id))
          return (i_f_id, f_name)
      page_num += 1

  def AddAllUserFolders(self, user_id: int, force_download: bool) -> set[int]:  # noqa: C901
    """Add all user's folders that are images galleries.

    Args:
      user_id: The user's int ID
      force_download: If True will download even if recently downloaded

    Returns:
      set of int folder IDs
    """
    try:
      # check for the timestamps: should we even do this work?
      if not self._CheckWorkHysteresis(
          force_download, self.users[user_id]['date_albums'],
          'Getting all image favorites for user %s' % self.UserStr(user_id)):
        return set(self.favorites.get(user_id, {}).keys())
    except KeyError:
      raise Error('This user was not added to DB yet: %d' % user_id)
    # get all pages of albums, extract the albums
    page_num: int = 0
    known_favorites: int = 0
    non_galleries: int = 0
    found_folder_ids: set[int] = set()
    self.favorites.setdefault(user_id, {})  # just to make sure user is in _favorites
    while True:
      url: str = _FAVORITES_URL(user_id, page_num)
      logging.info('Fetching favorites page: %s', url)
      fav_html = _FapHTMLRead(url)
      favorites_page: list[tuple[str, str]] = _FIND_FOLDERS.findall(fav_html)
      if not favorites_page:
        break  # no favorites found, so we passed the last page
      for f_id, f_name in favorites_page:
        i_f_id, f_name = int(f_id), html.unescape(f_name)
        # first check if we know it (for speed)
        if i_f_id in self.favorites[user_id]:
          # we already know of this gallery
          logging.info('Known picture folder %s', self.AlbumStr(user_id, i_f_id))
          found_folder_ids.add(i_f_id)
          known_favorites += 1
          continue
        # check if we can accept it as a images gallery
        try:
          _CheckFolderIsForImages(user_id, i_f_id)  # raises Error if not valid
        except Error:
          # this is a galleries favorite, so we can skip: we want images gallery!
          logging.info('Discarded galleries folder %r (%d/%d)', f_name, user_id, i_f_id)
          non_galleries += 1
          continue
        # we seem to have a valid new favorite here
        found_folder_ids.add(i_f_id)
        self.favorites[user_id][i_f_id] = {
            'name': f_name, 'pages': 0, 'date_straight': 0, 'date_blobs': 0,
            'images': [], 'failed_images': set()}
        logging.info('New picture folder %s added', self.AlbumStr(user_id, i_f_id))
      page_num += 1
    # mark the albums checking as done, log & return
    self.users[user_id]['date_albums'] = base.INT_TIME()
    logging.info('Found %d total favorite galleries in %d pages (%d were already known; '
                 'also, %d non-image galleries were skipped)',
                 len(found_folder_ids), page_num, known_favorites, non_galleries)
    return found_folder_ids

  def AddFolderPics(  # noqa: C901
      self, user_id: int, folder_id: int, force_download: bool) -> list[int]:
    """Read a folder and collect/compile all image IDs that are found, for all pages.

    This always goes through all favorite pages, as we want to always
    find new images, and it counts how many are new.

    Args:
      user_id: User int ID
      folder_id: Folder int ID
      force_download: If True will download even if recently downloaded

    Returns:
      list of all image ids
    """
    try:
      # check for the timestamps: should we even do this work?
      tm_download: int = max(self.favorites[user_id][folder_id]['date_straight'],
                             self.favorites[user_id][folder_id]['date_blobs'])
      if not self._CheckWorkHysteresis(
          force_download, tm_download,
          'Reading album %s pages & IDs' % self.AlbumStr(user_id, folder_id)):
        return self.favorites[user_id][folder_id]['images']
      img_list: list[int] = self.favorites[user_id][folder_id]['images']
      seen_pages: int = self.favorites[user_id][folder_id]['pages']
    except KeyError:
      raise Error('This user/folder was not added to DB yet: %d/%d' % (user_id, folder_id))
    # do the paging backtracking, if adequate; this is guaranteed to work because
    # the site only adds images to the *end* of the images favorites; on the other
    # hand there is the issue of the "disappearing" images, so we have to backtrack
    # to make sure we don't loose any...
    page_num: int = 0
    new_count: int = 0
    img_set: set[int] = set(img_list)
    if seen_pages >= _PAGE_BACKTRACKING_THRESHOLD:
      logging.warning('Backtracking from last seen page (%d) to save time', seen_pages)
      page_num = seen_pages - 1  # remember the site numbers pages starting on zero
      while page_num >= 0:
        new_ids = _ExtractFavoriteIDs(page_num, user_id, folder_id)
        if set(new_ids).intersection(img_set):
          # found last page that matters to backtracking (because it has images we've seen before)
          break
        page_num -= 1
    # get the pages of links, until they end
    while True:
      new_ids = _ExtractFavoriteIDs(page_num, user_id, folder_id)
      if not new_ids:
        # we should be able to stop (break) here, but the Imagefap site has this horrible bug
        # where we might have empty pages in the middle of the album and then have images again,
        # and because of this we should try a few more pages just to make sure, even if most times
        # it will be a complete waste of our time...
        new_ids = _ExtractFavoriteIDs(page_num + 1, user_id, folder_id)  # extra safety page 1
        if not new_ids:
          new_ids = _ExtractFavoriteIDs(page_num + 2, user_id, folder_id)  # extra safety page 1
          if not new_ids:
            break  # after 2 extra safety pages, we hope we can now safely give up...
          else:
            page_num += 2  # we found something (2nd extra page), remember to increment page counter
            logging.warn('Album %s had 2 EMPTY PAGES in the middle of the page list!',
                         self.AlbumStr(user_id, folder_id))
        else:
          page_num += 1  # we found something (1st extra page), remember to increment page counter
          logging.warn('Album %s had 1 EMPTY PAGES in the middle of the page list!',
                       self.AlbumStr(user_id, folder_id))
      # add the images to the end, preserve order, but skip the ones already there
      for i in new_ids:
        if i not in img_set:
          img_list.append(i)
          new_count += 1
      img_set = set(img_list)
      page_num += 1
    self.favorites[user_id][folder_id]['pages'] = page_num  # (pages start on zero)
    logging.info(
        'Found a total of %d image IDs in %d pages (%d are new in set, %d need downloading)',
        len(img_list), page_num, new_count,
        sum(1 for i in img_list if i not in self.image_ids_index))
    return img_list

  def _FindOrCreateBlobLocationEntry(self, user_id: int, folder_id: int, img_id: int) -> tuple[
      Optional[bytes], str, str, str, str]:
    """Find entry for user_id/folder_id/img_id or create one, if none is found.

    Args:
      user_id: User int ID
      folder_id: Folder int ID
      img_id: Imagefap int image ID

    Returns:
      (image_bytes, sha256_hexdigest, imagefap_full_res_url,
       file_name_sanitized, file_extension_sanitized)
      image_bytes can be None if the image's hash is known!

    Raises:
      Error404: with url and added image ID and name on a 404
    """
    # figure out if we have it in the index
    sha = self.image_ids_index.get(img_id, None)
    if sha is None:
      # we don't know about this specific img_id yet: get image's full resolution URL + name
      url_path, sanitized_image_name, extension = _ExtractFullImageURL(img_id)  # 404 bubble through
      # get actual binary data
      try:
        (image_bytes, sha, percept_hash, average_hash, diff_hash, wavelet_hash, cnn_hash,
         width, height, is_animated) = self._GetBinary(
            url_path, extension)
      except Error404 as e:
        e.image_id = img_id
        e.image_name = sanitized_image_name
        raise  # (let Error404 bubble through after adding the image ID and name...)
      # create DB entries and return
      self.image_ids_index[img_id] = sha
      sz = len(image_bytes)
      if sha in self.blobs:
        # in this case we haven't seen this img_id, but the actual binary (sha) was seen in
        # some other album, so we do some checks and add to the 'loc' entry
        if (self.blobs[sha]['sz'] != sz or self.blobs[sha]['percept'] != percept_hash or
            self.blobs[sha]['width'] != width or self.blobs[sha]['height'] != height or
            self.blobs[sha]['animated'] != is_animated):
          logging.error(  # this would be truly weird case, especially for the sz data!
              'Mismatch in %r: stored %d/%s/%s/%d/%d/%r versus new %d/%s/%s/%d/%d/%r',
              sha, self.blobs[sha]['sz'], self.blobs[sha]['percept'], self.blobs[sha]['ext'],
              self.blobs[sha]['width'], self.blobs[sha]['height'], self.blobs[sha]['animated'],
              sz, percept_hash, extension, width, height, is_animated)
        self.blobs[sha]['loc'].add(
            (img_id, url_path, sanitized_image_name, user_id, folder_id))
      else:
        # in this case this is a truly new image: never seen img_id or sha
        self.blobs[sha] = {
            'loc': {(img_id, url_path, sanitized_image_name, user_id, folder_id)},
            'tags': set(), 'sz': sz, 'sz_thumb': 0, 'ext': extension, 'percept': percept_hash,
            'average': average_hash, 'diff': diff_hash, 'wavelet': wavelet_hash, 'cnn': cnn_hash,
            'width': width, 'height': height, 'animated': is_animated}
      return (image_bytes, sha, url_path, sanitized_image_name, extension)
    # we have seen this img_id before, and can skip a lot of computation
    # first: could it be we saw it in this same user_id/folder_id?
    for iid, url, nm, uid, fid in self.blobs[sha]['loc']:
      if img_id == iid and user_id == uid and folder_id == fid:
        # this is an exact match (img_id/user_id/folder_id) and we won't download or search for URL
        return (None, sha, url, nm, self.blobs[sha]['ext'])
    # in this last case we know the img_id but it seems to be duplicated in another album,
    # so we have to get the img_id metadata (url, name) at least, and add to the database
    url_path, sanitized_image_name, extension = _ExtractFullImageURL(img_id)  # 404 bubble through
    self.blobs[sha]['loc'].add(
        (img_id, url_path, sanitized_image_name, user_id, folder_id))
    return (None, sha, url_path, sanitized_image_name, extension)

  def _CheckWorkHysteresis(self, force_download: bool, tm_last: int, task_message: str) -> bool:
    """Check if work should be done, or if task has recently been finished.

    Args:
      force_download: If True will download even if recently downloaded
      tm_last: Time last download was done
      task_message: Type of work message to log

    Returns:
      True if work should be done; False otherwise
    """
    tm_now = base.INT_TIME()
    if tm_last and (tm_last + FAVORITES_MIN_DOWNLOAD_WAIT) > tm_now:
      logging.warning(
          '%s recently done (%s, %s ago): %s!',
          task_message, base.STD_TIME_STRING(tm_last), base.HumanizedSeconds(tm_now - tm_last),
          'ignoring time limit and downloading again' if force_download else 'SKIP')
      if not force_download:
        return False
    logging.info(task_message)
    return True

  def DownloadFavorites(self, user_id: int, folder_id: int,
                        checkpoint_size: int, force_download: bool) -> int:
    """Actually get the images in a picture folder.

    Args:
      user_id: User ID
      folder_id: Folder ID
      checkpoint_size: Commit database to disk every `checkpoint_size` images actually downloaded;
          if zero will not checkpoint at all
      force_download: If True will download even if recently downloaded

    Returns:
      int size of all bytes downloaded
    """
    return self._DownloadAll(
        user_id, folder_id, checkpoint_size, force_download, self._db_dir, 'date_straight')

  def ReadFavoritesIntoBlobs(self, user_id: int, folder_id: int,
                             checkpoint_size: int, force_download: bool) -> int:
    """Actually get the images in a picture folder.

    Args:
      user_id: User ID
      folder_id: Folder ID
      checkpoint_size: Commit database to disk every `checkpoint_size` images actually downloaded;
          if zero will not checkpoint at all
      force_download: If True will download even if recently downloaded

    Returns:
      int size of all bytes downloaded
    """
    # create blobs directory, if needed
    if not self.blobs_dir_exists:
      logging.info('Creating blob directory %r', self._blobs_dir)
      os.mkdir(self._blobs_dir)
    # delegate the actual work
    return self._DownloadAll(
        user_id, folder_id, checkpoint_size, force_download, self._blobs_dir, 'date_blobs')

  def _DownloadAll(self, user_id: int, folder_id: int,  # noqa: C901
                   checkpoint_size: int, force_download: bool, output_dir: str,
                   date_key: Literal['date_blobs', 'date_straight']) -> int:
    """Actually get the images in a picture folder.

    Args:
      user_id: User ID
      folder_id: Folder ID
      checkpoint_size: Commit database to disk every `checkpoint_size` images actually downloaded;
          if zero will not checkpoint at all
      force_download: If True will download even if recently downloaded
      output_dir: Output directory to use
      date_key: Date key to use (either 'date_blobs' or 'date_straight')

    Returns:
      int size of all bytes downloaded
    """
    # check if work needs to be done
    try:
      tm_download: int = self.favorites[user_id][folder_id][date_key]
      if not self._CheckWorkHysteresis(
          force_download, tm_download,
          'Downloading album %s images' % self.AlbumStr(user_id, folder_id)):
        return 0
      logging.info('*NO* checkpoints used (work may be lost!)' if checkpoint_size == 0 else
                   'Checkpoint DB every %d downloads' % checkpoint_size)
    except KeyError:
      raise Error('This user/folder was not added to DB yet: %d/%d' % (user_id, folder_id))
    # download all full resolution images we don't yet have
    total_sz: int = 0
    thumb_sz: int = 0
    saved_count: int = 0
    known_count: int = 0
    exists_count: int = 0
    for img_id in list(self.favorites[user_id][folder_id]['images']):  # copy b/c we might change it
      # add image to database
      try:
        image_bytes, sha, url_path, sanitized_image_name, extension = (
            self._FindOrCreateBlobLocationEntry(user_id, folder_id, img_id))
      except Error404 as e:
        # we had a 404 error, but this already comes will all fields ready
        self.favorites[user_id][folder_id]['images'].remove(img_id)
        self.favorites[user_id][folder_id]['failed_images'].add(e.FailureTuple())
        logging.error('FAILED IMAGE: %s' % e)
        continue
      known_count += 1 if image_bytes is None else 0
      full_path = (os.path.join(output_dir, sanitized_image_name)
                   if date_key == 'date_straight' else self._BlobPath(sha))
      # check for output path existence so we don't clobber images that are already there
      if os.path.exists(full_path):
        logging.info('Image already exists at %r', full_path)
        exists_count += 1
        continue
      # if we still don't have the image data, check if we have the data in the DB
      if image_bytes is None and self.HasBlob(sha):
        image_bytes = self.GetBlob(sha)
      # save image and get data if we couldn't find it in DB yet
      try:
        total_sz += _SaveImage(full_path, self._GetBinary(
            url_path, extension)[0] if image_bytes is None else image_bytes)
      except Error404 as e:
        # we had a 404 error, and it needs extra fields
        e.image_id = img_id
        e.image_name = sanitized_image_name
        self.favorites[user_id][folder_id]['images'].remove(img_id)
        self.favorites[user_id][folder_id]['failed_images'].add(e.FailureTuple())
        logging.error('FAILED IMAGE: %s' % e)
        continue
      saved_count += 1
      # if we saved a blob, we should also generate a thumbnail
      if date_key == 'date_blobs':
        thumb_sz += self._MakeThumbnailForBlob(sha)
      # checkpoint database, if needed
      if checkpoint_size and not saved_count % checkpoint_size:
        self.Save()
    # all images were downloaded, the end
    self.favorites[user_id][folder_id][date_key] = base.INT_TIME()  # marks album as done
    print(
        'Saved %d images to disk (%s) and %s in thumbnails; also %d images were already in DB and '
        '%d images were already saved to destination' % (
            saved_count, base.HumanizedBytes(total_sz), base.HumanizedBytes(thumb_sz),
            known_count, exists_count))
    return total_sz

  def _GetBinary(
      self,
      url: str,
      image_extension: str) -> tuple[bytes, str, str, str, str, str, np.ndarray, int, int, bool]:
    """Get an image by URL and compute data that depends only on the binary representation.

    Args:
      url: Image URL path
      image_extension: Putative image extension

    Returns:
      (image_bytes, image_sha256_hexdigest,
       percept_hash, average_hash, diff_hash, wavelet_hash, cnn_hash,
       width, height, is_animated)

    Raises:
      Error: for invalid URLs or empty images
    """
    # get the full image binary
    logging.info('Fetching full-res image: %s', url)
    img_data = _FapBinRead(url)  # (let Error404 bubble through...)
    if not img_data:
      raise Error('Empty full-res URL: %s' % url)
    # do perceptual hashing
    with tempfile.NamedTemporaryFile(suffix='.' + image_extension) as temp_file:
      temp_file.write(img_data)
      temp_file.flush()
      with Image.open(temp_file.name) as img:
        width, height = img.width, img.height
        is_animated: bool = getattr(img, 'is_animated', False)
      percept, average, diff, wavelet, cnn = self.duplicates.Encode(temp_file.name)
    return (img_data, hashlib.sha256(img_data).hexdigest(),
            percept, average, diff, wavelet, cnn, width, height, is_animated)

  def _MakeThumbnailForBlob(self, sha: str) -> int:
    """Make equivalent thumbnail for `sha` entry. Will overwrite destination.

    Args:
      sha: the SHA256 key

    Returns:
      int size of saved file
    """
    # create thumbnails directory, if needed
    if not self.thumbs_dir_exists:
      logging.info('Creating thumbnails directory %r', self._thumbs_dir)
      os.mkdir(self._thumbs_dir)
    # open image and generate a thumbnail
    with Image.open(self._BlobPath(sha)) as img:
      output_path = self.ThumbnailPath(sha)
      # figure out the new size that will be used
      width, height = img.width, img.height
      if max((width, height)) <= _THUMBNAIL_MAX_DIMENSION:
        # the image is already smaller than the putative thumbnail, so we just copy it as thumbnail
        shutil.copyfile(self._BlobPath(sha), output_path)
        sz_thumb = os.path.getsize(output_path)
        self.blobs[sha]['sz_thumb'] = sz_thumb
        logging.info('Copied image as thumbnail for %r', sha)
        return sz_thumb
      if width > height:
        new_width, factor = _THUMBNAIL_MAX_DIMENSION, width / _THUMBNAIL_MAX_DIMENSION
        new_height = math.floor(height / factor)
      else:
        new_height, factor = _THUMBNAIL_MAX_DIMENSION, height / _THUMBNAIL_MAX_DIMENSION
        new_width = math.floor(width / factor)
      if self.blobs[sha]['animated'] and self.blobs[sha]['ext'].lower() == 'gif':
        # special process for animated images, specifically an animated `gif`

        def _thumbnails(img_frames: Iterator[Image.Image]) -> Iterator[Image.Image]:
          for frame in img_frames:
            thumbnail = frame.copy()
            thumbnail.thumbnail((new_width, new_height), Image.LANCZOS)
            yield thumbnail

        frames: Iterator[Image.Image] = _thumbnails(ImageSequence.Iterator(img))
        first_frame = next(frames)   # handle first frame separately: will be used to save
        first_frame.info = img.info  # copy sequence info into first frame
        first_frame.save(output_path, save_all=True, append_images=list(frames))
        logging.info('Saved animated thumbnail for %r', sha)
      else:
        # simpler process for regular (non-animated) images
        img.thumbnail((new_width, new_height), resample=Image.LANCZOS)
        img.save(output_path)
        logging.info('Saved thumbnail for %r', sha)
    # we get the size of the created file
    sz_thumb = os.path.getsize(output_path)
    self.blobs[sha]['sz_thumb'] = sz_thumb
    return sz_thumb

  def DeleteUserAndAlbums(self, user_id: int) -> tuple[int, int]:
    """Delete an user, together with favorites and orphaned blobs, thumbs, indexes and duplicates.

    Args:
      user_id: User ID

    Returns:
      (number of blobs deleted, number of duplicates deleted)

    Raises:
      Error: invalid user_id or folder_id
    """
    # check input
    if user_id not in self.users:
      raise Error('Invalid user %d' % user_id)
    # delete the favorite albums first
    img_count: int = 0
    duplicate_count: int = 0
    for folder_id in set(self.favorites.get(user_id, {}).keys()):
      img, duplicate = self.DeleteAlbum(user_id, folder_id)
      img_count += img
      duplicate_count += duplicate
    # finally delete the actual user entry and return the counts
    del self.favorites[user_id]
    del self.users[user_id]
    return (img_count, duplicate_count)

  def DeleteAlbum(self, user_id: int, folder_id: int) -> tuple[int, int]:  # noqa: C901
    """Delete an user favorites album, together with orphaned blobs, thumbs, indexes and duplicates.

    Args:
      user_id: User ID
      folder_id: Folder ID

    Returns:
      (number of blobs deleted, number of duplicates deleted)

    Raises:
      Error: invalid user_id or folder_id or image location entry not found
    """
    # check input
    if user_id not in self.users or user_id not in self.favorites:
      raise Error('Invalid user %d' % user_id)
    if folder_id not in self.favorites[user_id]:
      raise Error('Invalid folder %d for user %s' % (folder_id, self.UserStr(user_id)))
    # get the album and go through the images deleting as necessary
    img_count: int = 0
    duplicate_count: int = 0
    images: list[int] = self.favorites[user_id][folder_id]['images']
    for img_id in images:
      # get the blob
      sha = self.image_ids_index[img_id]
      # remove the location entry from the blob
      for loc_key in self.blobs[sha]['loc']:
        if loc_key[0] == img_id and loc_key[3] == user_id and loc_key[4] == folder_id:
          logging.info('Deleting image entry %s/%s', self.LocationStr(loc_key), sha)
          break  # found the entry, as expected
      else:
        raise Error('Invalid image %d in folder %s; inconsistency should not happen!' % (
            img_id, self.AlbumStr(user_id, folder_id)))
      self.blobs[sha]['loc'].remove(loc_key)
      # now we either still have locations for this blob, or it is orphaned
      if self.blobs[sha]['loc']:
        # we still have locations using this blob: the blob stays and we might remove index
        self._DeleteIndexIfOrphan(folder_id, img_id)
        continue
      # this blob is orphaned and must be purged; start by deleting the files on disk, if they exist
      try:
        os.remove(self._BlobPath(sha))
        logging.info('Deleted blob %r from disk', sha)
      except FileNotFoundError as e:
        logging.warning('Blob %r not found: %s', sha, e)
      try:
        os.remove(self.ThumbnailPath(sha))
        logging.info('Deleted thumbnail %r from disk', sha)
      except FileNotFoundError as e:
        logging.warning('Thumbnail %r not found: %s', sha, e)
      # now delete the blob entry
      del self.blobs[sha]
      img_count += 1
      # purge the duplicates and the indexes associated with this blob
      duplicate_count += int(self.duplicates.TrimDeletedBlob(sha))
      self._DeleteIndexesToBlob(sha)
    # finally delete the actual album entry and return the counts
    del self.favorites[user_id][folder_id]
    return (img_count, duplicate_count)

  def _DeleteIndexesToBlob(self, sha: str) -> None:
    """Delete all index entries pointing to (recently deleted) blob `sha`."""
    for img in {i for i, s in self.image_ids_index.items() if s == sha}:
      del self.image_ids_index[img]

  def _DeleteIndexIfOrphan(self, folder_id: int, imagefap_image_id: int) -> None:
    """Delete index entry for `imagefap_image_id` IFF no album uses the index."""
    if not any(
        imagefap_image_id in favorite_obj['images'] and fid != folder_id
        for user_obj in self.favorites.values()
        for fid, favorite_obj in user_obj.items()):
      del self.image_ids_index[imagefap_image_id]

  @property
  def _hashes_encodings_map(self) -> duplicates.HashEncodingMapType:
     """A dictionary containing mapping of filenames and corresponding perceptual hashes."""
     return {method: {sha: obj[method] for sha, obj in self.blobs.items()}  # type: ignore
             for method in duplicates.DUPLICATE_HASHES}

  def FindDuplicates(self) -> None:
    """Find (perceptual) duplicates.

    Returns:
      dict of {sha: set_of_other_sha_duplicates}
    """
    self.duplicates.FindDuplicates(self._hashes_encodings_map)


def _LimpingURLRead(url: str, min_wait: float = 1.0, max_wait: float = 2.0) -> bytes:
  """Read URL, but wait a semi-random time to protect site from overload.

  Args:
    url: The URL to get
    min_wait: (default 1.0) The minimum wait, in seconds
    max_wait: (default 2.0) The maximum wait, in seconds

  Returns:
    The bytes retrieved

  Raises:
    Error404: on HTTP 404 errors that exceed the retry limit
    Error: on all other errors that exceed the retry limit
  """
  # get a random wait
  if min_wait <= 0.0 or max_wait <= 0.0 or max_wait < min_wait:
    raise AttributeError('Invalid min/max wait times')
  tm = random.uniform(min_wait, max_wait)  # nosec
  n_retry: int = 0
  last_error: Optional[str] = None
  while n_retry <= _MAX_RETRY:
    # sleep to keep Imagefap happy
    logging.debug('Sleep %0.2fs...', tm)
    time.sleep(tm)
    try:
      # get the URL
      last_error = None
      return urllib.request.urlopen(url, timeout=_URL_TIMEOUT).read()  # nosec
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        http.client.RemoteDisconnected,
        socket.timeout) as e:
      # these errors sometimes happen and can be a case for retry
      n_retry += 1
      last_error = str(e)
      logging.error('%r error for URL %r, RETRY # %d', last_error, url, n_retry)
  # only way to reach here is exceeding retries
  if last_error is not None and 'http error 404' in last_error.lower():
    raise Error404(url)
  raise Error('Max retries reached on URL %r' % url)


def _FapHTMLRead(url: str) -> str:
  return _LimpingURLRead(url).decode('utf-8', errors='ignore')  # (let Error404 bubble through...)


def _FapBinRead(url: str) -> bytes:
  return _LimpingURLRead(url)  # (let Error404 bubble through...)


def _CheckFolderIsForImages(user_id: int, folder_id: int) -> None:
  """Check that a folder is an *image* folder, not a *galleries* folder.

  Args:
    user_id: User int ID
    folder_id: Folder int ID

  Raises:
    Error: if folder is not an image folder (i.e. it might be a galleries folder)
  """
  url: str = _FOLDER_URL(user_id, folder_id, 0)  # use the folder's 1st page
  logging.debug('Fetching favorites to check *not* a galleries folder: %s', url)
  folder_html = _FapHTMLRead(url)
  should_have: list[str] = _FIND_ONLY_IN_PICTURE_FOLDER.findall(folder_html)
  should_not_have: list[str] = _FIND_ONLY_IN_GALLERIES_FOLDER.findall(folder_html)
  if should_not_have or not should_have:
    raise Error('This is not a valid images folder! Maybe it is a galleries folder?')


def _NormalizeExtension(extension: str) -> str:
  """Normalize image file extensions."""
  extension = extension.lower()
  if extension == 'jpeg':
    extension = 'jpg'
  return extension


def _ExtractFavoriteIDs(page_num: int, user_id: int, folder_id: int) -> list[int]:
  """Get numerical IDs of all images in a picture folder by URL.

  Args:
    page_num: Page to request (starting on 0!)
    user_id: User ID
    folder_id: Folder ID

  Returns:
    list of integer image IDs; empty list on last (empty) page
  """
  url: str = _FOLDER_URL(user_id, folder_id, page_num)
  logging.info('Fetching favorites page: %s', url)
  fav_html = _FapHTMLRead(url)
  images: list[str] = _FAVORITE_IMAGE.findall(fav_html)
  image_ids = [int(id) for id in images]
  logging.info('Got %d image IDs', len(image_ids))
  return image_ids


def _ExtractFullImageURL(img_id: int) -> tuple[str, str, str]:
  """Get URL path of the full resolution image by image ID.

  Args:
    img_id: The image numerical ID

  Returns:
    (image_URL_path, sanitized_image_name, sanitized_extension)

  Raises:
    Error: for invalid URLs or full-res URL not found
  """
  # get page with full image, to find (raw) image URL
  url: str = IMG_URL(img_id)
  logging.info('Fetching image page: %s', url)
  try:
    img_html = _FapHTMLRead(url)
  except Error404 as e:
    e.image_id = img_id
    raise
  full_res_urls: list[str] = _FULL_IMAGE.findall(img_html)
  if not full_res_urls:
    raise Error('No full resolution image in %s' % url)
  # from the same source extract image file name
  img_name: list[str] = _IMAGE_NAME.findall(img_html)
  if not img_name:
    raise Error('No image name path in %s' % url)
  # sanitize image name before returning
  new_name: str = sanitize_filename.sanitize(html.unescape(img_name[0]))
  if new_name != img_name[0]:
    logging.warning('Filename sanitization necessary %r ==> %r', img_name[0], new_name)
  # figure out the file name, sanitize extension
  main_name, extension = new_name.rsplit('.', 1) if '.' in new_name else (new_name, 'jpg')
  sanitized_extension = _NormalizeExtension(extension)
  sanitized_image_name = '%s.%s' % (main_name, sanitized_extension)
  return (full_res_urls[0], sanitized_image_name, sanitized_extension)


def _SaveImage(full_path: str, bin_data: bytes) -> int:
  """Save bin_data, the image data, to full_path.

  Args:
    full_path: File path
    bin_data: Image binary data

  Returns:
    number of bytes actually saved
  """
  sz = len(bin_data)
  with open(full_path, 'wb') as f:
    f.write(bin_data)
  logging.info('Saved %s for image %r', base.HumanizedBytes(sz), full_path)
  return sz


def GetDatabaseTimestamp(db_path: str = DEFAULT_DB_DIRECTORY) -> int:
  """Get the (int) timestamp that the database file was last modified.

  Args:
    db_path: Directory path where to find the database file (default DEFAULT_DB_DIRECTORY)

  Returns:
    int timestamp (rounded up to minimize chance of collision)

  Raises:
    Error: if database file does not already exist
  """
  db_file = os.path.join(os.path.expanduser(db_path), _DEFAULT_DB_NAME)
  if not os.path.exists(db_file):
    raise Error('Database file not found: %r' % db_file)
  return math.ceil(os.path.getmtime(db_file))
