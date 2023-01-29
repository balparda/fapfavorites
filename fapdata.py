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
import logging
import os
import os.path
# import pdb
import random
import re
import statistics
import time
from typing import Literal, Union
import urllib.error
import urllib.request

import sanitize_filename

from baselib import base


__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


# useful globals
DEFAULT_DB_DIRECTORY = '~/Downloads/imagefap/'
DEFAULT_DB_NAME = 'imagefap.database'
DEFAULT_BLOB_DIR_NAME = 'blobs/'
CHECKPOINT_LENGTH = 10
_PAGE_BACKTRACKING_THRESHOLD = 5
_FAVORITES_MIN_DOWNLOAD_WAIT = 3 * (60 * 60 * 24)  # 3 days (in seconds)

# internal data utils
_DB_MAIN_KEYS = {
    'users',
    'favorites',
    'tags',
    'blobs',
    'image_ids_index',
}
_DB_KEY_TYPE = Literal['users', 'favorites', 'tags', 'blobs', 'image_ids_index']
_TAG_TYPE = dict[int, dict[Literal['name', 'tags'], Union[str, dict]]]

# the site page templates we need
_USER_PAGE_URL = lambda n: 'https://www.imagefap.com/profile/%s' % n
_FAVORITES_URL = (
    lambda u, p: 'https://www.imagefap.com/showfavorites.php?userid=%d&page=%d' % (u, p))
_FOLDER_URL = lambda u, f, p: '%s&folderid=%d' % (_FAVORITES_URL(u, p), f)  # cspell:disable-line
_IMG_URL = lambda id: 'https://www.imagefap.com/photo/%d/' % id

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


def LimpingURLRead(url: str, min_wait: float = 1.0, max_wait: float = 2.0) -> bytes:
  """Read URL, but wait a semi-random time to trip up site protections.

  Args:
    url: The URL to get
    min_wait: (default 1.0) The minimum wait, in seconds
    max_wait: (default 2.0) The maximum wait, in seconds

  Returns:
    The bytes retrieved

  Raises:
    Error: on error
  """
  if min_wait <= 0.0 or max_wait <= 0.0 or max_wait < min_wait:
    raise AttributeError('Invalid min/max wait times')
  tm = random.uniform(min_wait, max_wait)  # nosec
  try:
    url_data = urllib.request.urlopen(url).read()  # nosec
    logging.debug('Sleep %0.2fs...', tm)
    time.sleep(tm)
    return url_data
  except urllib.error.URLError as e:
    raise Error('Invalid URL: %s (%s)' % (url, e)) from e


def _CheckFolderIsForImages(user_id: int, folder_id: int) -> None:
  """Check that a folder is an *image* folder, not a *galleries* folder.

  Args:
    user_id: User int ID
    folder_id: Folder int ID

  Raises:
    Error: if folder is not an image folder (i.e. it might be a galleries folder)
  """
  url = _FOLDER_URL(user_id, folder_id, 0)  # use the folder's 1st page
  logging.debug('Fetching favorites to check *not* a galleries folder: %s', url)
  folder_html = LimpingURLRead(url).decode('utf-8', errors='ignore')
  should_have = _FIND_ONLY_IN_PICTURE_FOLDER.findall(folder_html)
  should_not_have = _FIND_ONLY_IN_GALLERIES_FOLDER.findall(folder_html)
  if should_not_have or not should_have:
    raise base.Error('This is not a valid images folder! Maybe it is a galleries folder?')


class FapDatabase():
  """Imagefap.com database."""

  def __init__(self, path):
    """Construct a clean database.

    Args:
      path: The file path to load/save DB from

    Raises:
      AttributeError: on empty path
    """
    # start with a clean DB; see README.md for format
    if not path:
      raise AttributeError('Database path cannot be empty')
    self._path: str = path
    self._db: dict[_DB_KEY_TYPE, dict] = {}
    for k in _DB_MAIN_KEYS:  # creates the main expected key entries
      self._db[k] = {}  # type: ignore

  @property
  def _users(self) -> dict[int, str]:
    return self._db['users']

  @property
  def _favorites(self) -> dict[int, dict[int, dict[Literal['name', 'pages', 'date', 'images'],
                                                   Union[str, int, list[int]]]]]:
    return self._db['favorites']

  @property
  def _tags(self) -> _TAG_TYPE:
    return self._db['tags']

  @property
  def _blobs(self) -> dict[str, dict[Literal['loc', 'tags', 'sz', 'ext'],
                                     Union[int, str,
                                           set[Union[int, tuple[int, str, str, int, int]]]]]]:
    return self._db['blobs']

  @property
  def _image_ids_index(self) -> dict[int, str]:
    return self._db['image_ids_index']

  def Load(self) -> None:
    """Load DB from file.

    Raises:
      Error: if found DB does not check out
    """
    if os.path.exists(self._path):
      self._db = base.BinDeSerialize(file_path=self._path)
      # just a quick dirty check that we got what we expected
      if any(k not in self._db for k in _DB_MAIN_KEYS):
        raise Error('Loaded DB is invalid!')
      logging.info('Loaded DB from %r', self._path)
    else:
      logging.warning('No DB found in %r', self._path)

  def Save(self) -> None:
    """Save DB to file."""
    base.BinSerialize(self._db, self._path)
    logging.info('Saved DB to %r', self._path)

  def GetTag(self, tag_id: int) -> list[tuple[int, str]]:  # noqa: C901
    """Search recursively for specific tag object, returning parents too, if any.

    Args:
      tag_id: The wanted tag ID

    Returns:
      list of (id, name), starting with the parents and ending with the wanted tag;
      this means that GetTag(id)[-1] is always the wanted tag

    Raises:
      Error: not found or invalid
    """
    hierarchy = []

    def _get_recursive(obj: _TAG_TYPE) -> bool:
      if tag_id in obj:
        try:
          hierarchy.append((tag_id, obj[tag_id]['name']))  # found!
        except KeyError:
          raise base.Error('Found tag %d is empty (has no \'name\')!' % tag_id)
        return True
      for i, o in obj .items():
        if o.get('tags', {}):
          if _get_recursive(o['tags']):  # type: ignore
            try:
              hierarchy.append((i, o['name']))  # this is a parent to a found tag
            except KeyError:
              raise base.Error('Parent tag %d (of %d) is empty (has no \'name\')!' % (i, tag_id))
            return True
      return False

    if not _get_recursive(self._tags):
      raise base.Error('Tag ID %d was not found' % tag_id)
    hierarchy.reverse()
    return hierarchy

  def PrintStats(self) -> None:
    """Print database stats."""
    file_sizes: list[int] = [s['sz'] for s in self._blobs.values()]  # type: ignore
    all_files_size = sum(file_sizes)
    db_size = os.path.getsize(self._path)
    print('Database is located in %r, and is %s (%0.5f%% of total images size)' % (
        self._path, base.HumanizedLength(db_size),
        100.0 * db_size / (all_files_size if all_files_size else 1)))
    print(
        '%s total unique image files size (%s min, %s max, %s mean with %s standard deviation)' % (
            base.HumanizedLength(all_files_size),
            base.HumanizedLength(min(file_sizes)),
            base.HumanizedLength(max(file_sizes)),
            base.HumanizedLength(int(statistics.mean(file_sizes))),
            base.HumanizedLength(int(statistics.stdev(file_sizes)))))
    print()
    print('%d users' % len(self._users))
    all_dates = [f['date'] for u in self._favorites.values() for f in u.values()]
    min_date, max_date = min(all_dates), max(all_dates)
    print('%d favorite galleries (oldest: %s / newer: %s)' % (
        sum(len(f) for _, f in self._favorites.items()),
        base.STD_TIME_STRING(min_date) if min_date else 'pending',
        base.STD_TIME_STRING(max_date) if max_date else 'pending'))
    print('%d unique images (%d total, %d duplicates)' % (
        len(self._blobs),
        sum(len(b['loc']) for _, b in self._blobs.items()),       # type: ignore
        sum(len(b['loc']) - 1 for _, b in self._blobs.items())))  # type: ignore

  def PrintUsersAndFavorites(self) -> None:
    """Print database users."""
    print('ID: USER_NAME')
    print('    FILE STATS FOR USER')
    print('    => ID: FAVORITE_NAME (IMAGE_COUNT / PAGE_COUNT / DATE DOWNLOAD)')
    print('           FILE STATS FOR FAVORITES')
    for i in sorted(self._users.keys()):
      u = self._users[i]
      print()
      print('%d: %r' % (i, u))
      file_sizes: list[int] = [
          self._blobs[
              self._image_ids_index[i]]['sz'] for u in self._favorites.values()
              for f in u.values() for i in f['images']]   # type: ignore # noqa: C901,E131
      print('    %s files size (%s min, %s max, %s mean with %s standard deviation)' % (
          base.HumanizedLength(sum(file_sizes)),
          base.HumanizedLength(min(file_sizes)),
          base.HumanizedLength(max(file_sizes)),
          base.HumanizedLength(int(statistics.mean(file_sizes))),
          base.HumanizedLength(int(statistics.stdev(file_sizes)))))
      for j in sorted(self._favorites.get(i, {}).keys()):
        f = self._favorites[i][j]
        file_sizes: list[int] = [
            self._blobs[self._image_ids_index[i]]['sz'] for i in f['images']]  # type: ignore
        print('    => %d: %r (%d / %d / %s)' % (
            j, f['name'], len(f['images']), f['pages'],  # type: ignore
            base.STD_TIME_STRING(f['date']) if f['date'] else 'pending'))
        print('           %s files size (%s min, %s max, %s mean with %s standard deviation)' % (
            base.HumanizedLength(sum(file_sizes)),
            base.HumanizedLength(min(file_sizes)),
            base.HumanizedLength(max(file_sizes)),
            base.HumanizedLength(int(statistics.mean(file_sizes))),
            base.HumanizedLength(int(statistics.stdev(file_sizes)))))

  def PrintTags(self) -> None:
    """Print database tags."""
    # TODO: finish tag printing
    # raise NotImplementedError()

  def PrintBlobs(self) -> None:
    """Print database blobs metadata."""
    print('SHA256_HASH: ID1/\'NAME1\' or ID2/\'NAME2\' or ...')
    print('    => {\'TAG1\', \'TAG2\', ...}')
    print()
    for h in sorted(self._blobs.keys()):
      b = self._blobs[h]
      print('%s: %s' % (h, ' or '.join(
          '%d/%r' % (i, n) for i, _, n, _, _ in b['loc'])))  # type: ignore
      if b['tags']:
        # TODO: translate tag names instead of IDs!
        print('    => {%s}' % ', '.join(repr(i) for i in b['tags']))  # type: ignore

  def AddUserByID(self, user_id: int) -> str:
    """Add user by ID and find user name in the process.

    Args:
      user_id: The user ID

    Returns:
      actual user name

    Raises:
      Error: if conversion failed
    """
    if user_id in self._users:
      status = 'Known'
    else:
      status = 'New'
      url = _FAVORITES_URL(user_id, 0)  # use the favorites page
      logging.info('Fetching favorites page: %s', url)
      user_html = LimpingURLRead(url).decode('utf-8', errors='ignore')
      user_names = _FIND_NAME_IN_FAVORITES.findall(user_html)
      if len(user_names) != 1:
        raise Error('Could not find user name for %d' % user_id)
      self._users[user_id] = html.unescape(user_names[0])
    logging.info('%s user ID %d = %r', status, user_id, self._users[user_id])
    return self._users[user_id]

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
    for uid, unm in self._users.items():
      if unm.lower() == user_name.lower():
        logging.info('Known user %r = ID %d', unm, uid)
        return (uid, unm)
    # not found: we have to find in actual site
    url = _USER_PAGE_URL(user_name)
    logging.info('Fetching user page: %s', url)
    user_html = LimpingURLRead(url).decode('utf-8', errors='ignore')
    user_ids = _FIND_USER_ID_RE.findall(user_html)
    if len(user_ids) != 1:
      raise Error('Could not find ID for user %r' % user_name)
    uid = int(user_ids[0])
    actual_name = _FIND_ACTUAL_NAME.findall(user_html)
    if len(actual_name) != 1:
      raise Error('Could not find actual display name for user %r' % user_name)
    self._users[uid] = html.unescape(actual_name[0])
    logging.info('New user %r = ID %d', self._users[uid], uid)
    return (uid, self._users[uid])

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
    if folder_id in self._favorites.get(user_id, {}):
      status = 'Known'
    else:
      status = 'New'
      url = _FOLDER_URL(user_id, folder_id, 0)  # use the folder page
      logging.info('Fetching favorites page: %s', url)
      folder_html = LimpingURLRead(url).decode('utf-8', errors='ignore')
      folder_names = _FIND_NAME_IN_FOLDER.findall(folder_html)
      if len(folder_names) != 1:
        raise Error('Could not find folder name for %d/%d' % (user_id, folder_id))
      _CheckFolderIsForImages(user_id, folder_id)  # raises Error if not valid
      self._favorites.setdefault(user_id, {})[folder_id] = {
          'name': html.unescape(folder_names[0]), 'pages': 0, 'date': 0, 'images': []}
    logging.info('%s folder ID %d/%d = %r',
                 status, user_id, folder_id, self._favorites[user_id][folder_id]['name'])
    return self._favorites[user_id][folder_id]['name']  # type: ignore

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
    if user_id in self._favorites:
      for fid, f_data in self._favorites[user_id].items():
        if f_data['name'].lower() == favorites_name.lower():  # type: ignore
          logging.info('Known picture folder %r = ID %d', f_data['name'], fid)
          return (fid, f_data['name'])  # type: ignore
    # not found: we have to find in actual site
    page_num = 0
    while True:
      url = _FAVORITES_URL(user_id, page_num)
      logging.info('Fetching favorites page: %s', url)
      fav_html = LimpingURLRead(url).decode('utf-8', errors='ignore')
      favorites_page: list[tuple[str, str]] = _FIND_FOLDERS.findall(fav_html)
      if not favorites_page:
        raise Error('Could not find picture folder %r for user %d' % (favorites_name, user_id))
      for f_id, f_name in favorites_page:
        i_f_id, f_name = int(f_id), html.unescape(f_name)
        if f_name.lower() == favorites_name.lower():
          # found it!
          _CheckFolderIsForImages(user_id, i_f_id)  # raises Error if not valid
          self._favorites.setdefault(user_id, {})[i_f_id] = {
              'name': f_name, 'pages': 0, 'date': 0, 'images': []}
          logging.info('New picture folder %r = ID %d', f_name, i_f_id)
          return (i_f_id, f_name)
      page_num += 1

  def AddAllUserFolders(self, user_id: int) -> set[int]:
    """Add all user's folders that are images galleries.

    Args:
      user_id: The user's int ID

    Returns:
      set of int folder IDs
    """
    page_num, found_folder_ids, known_favorites, non_galleries = 0, set(), 0, 0
    self._favorites.setdefault(user_id, {})  # just to make sure user is in _favorites
    while True:
      url = _FAVORITES_URL(user_id, page_num)
      logging.info('Fetching favorites page: %s', url)
      fav_html = LimpingURLRead(url).decode('utf-8', errors='ignore')
      favorites_page: list[tuple[str, str]] = _FIND_FOLDERS.findall(fav_html)
      if not favorites_page:
        break  # no favorites found, so we passed the last page
      for f_id, f_name in favorites_page:
        i_f_id, f_name = int(f_id), html.unescape(f_name)
        # first check if we know it (for speed)
        if i_f_id in self._favorites[user_id]:
          # we already know of this gallery
          logging.info('Known picture folder %r (ID %d)', f_name, i_f_id)
          found_folder_ids.add(i_f_id)
          known_favorites += 1
          continue
        # check if we can accept it as a images gallery
        try:
          _CheckFolderIsForImages(user_id, i_f_id)  # raises Error if not valid
        except base.Error:
          # this is a galleries favorite, so we can skip: we want images gallery!
          logging.info('Discarded galleries folder %r (ID %d)', f_name, i_f_id)
          non_galleries += 1
          continue
        # we seem to have a valid new favorite here
        found_folder_ids.add(i_f_id)
        self._favorites[user_id][i_f_id] = {'name': f_name, 'pages': 0, 'date': 0, 'images': []}
        logging.info('New picture folder %r (ID %d)', f_name, i_f_id)
      page_num += 1
    logging.info('Found %d total favorite galleries in %d pages (%d were already known; '
                 'also, %d non-image galleries were skipped)',
                 len(found_folder_ids), page_num, known_favorites, non_galleries)
    return found_folder_ids

  def AddFolderPics(self, user_id: int, folder_id: int) -> list[int]:  # noqa: C901
    """Read a folder and collect/compile all image IDs that are found, for all pages.

    This always goes through all favorite pages, as we want to always
    find new images, and it counts how many are new.

    Args:
      user_id: User int ID
      folder_id: Folder int ID

    Returns:
      list of all image ids
    """
    try:
      tm: int = self._favorites[user_id][folder_id]['date']  # type: ignore
      if tm and (tm + _FAVORITES_MIN_DOWNLOAD_WAIT) > base.INT_TIME():
        logging.warning(
            'Picture folder %r/%r (%d/%d) downloaded recently (%s): SKIP',
            self._users[user_id], self._favorites[user_id][folder_id]['name'], user_id, folder_id,
            base.STD_TIME_STRING(tm))
        return self._favorites[user_id][folder_id]['images']  # type: ignore
      logging.info(
          'Getting all picture folder pages and IDs for %r/%r (%d/%d)',
          self._users[user_id], self._favorites[user_id][folder_id]['name'], user_id, folder_id)
      img_list: list[int] = self._favorites[user_id][folder_id]['images']  # type: ignore
      seen_pages: int = self._favorites[user_id][folder_id]['pages']       # type: ignore
    except KeyError:
      raise base.Error('This user/folder was not added to DB yet: %d/%d' % (user_id, folder_id))

    def _ExtractFavoriteIDs(page_num: int) -> list[int]:
      """Get numerical IDs of all images in a picture folder by URL.

      Args:
        page_num: Page to request (starting on 0!)

      Returns:
        list of integer image IDs; empty list on last (empty) page
      """
      url = _FOLDER_URL(user_id, folder_id, page_num)
      logging.info('Fetching favorites page: %s', url)
      fav_html = LimpingURLRead(url).decode('utf-8', errors='ignore')
      ids = [int(id) for id in _FAVORITE_IMAGE.findall(fav_html)]
      logging.info('Got %d image IDs', len(ids))
      return ids

    # do the paging backtracking, if adequate; this is guaranteed to work because
    # the site only adds images to the *end* of the images favorites; on the other
    # hand there is the issue of the "disappearing" images, so we have to backtrack
    # to make sure we don't loose any...
    page_num, new_count, img_set = 0, 0, set(img_list)
    if seen_pages >= _PAGE_BACKTRACKING_THRESHOLD:
      logging.warning('Backtracking from last seen page (%d) to save time', seen_pages)
      page_num = seen_pages - 1  # remember the site numbers pages starting on zero
      while page_num >= 0:
        new_ids = _ExtractFavoriteIDs(page_num)
        if set(new_ids).intersection(img_set):
          # found last page that matters to us because it has images we've seen before
          break
        page_num -= 1
    # get the pages of links, until they end
    while True:
      new_ids = _ExtractFavoriteIDs(page_num)
      if not new_ids:
        break
      # add the images to the end, preserve order, but skip the ones already there
      for i in new_ids:
        if i not in img_set:
          img_list.append(i)
          new_count += 1
      img_set = set(img_list)
      page_num += 1
    self._favorites[user_id][folder_id]['pages'] = page_num  # (pages start on zero)
    logging.info(
        'Found a total of %d image IDs in %d pages (%d are new in set, %d need downloading)',
        len(img_list), page_num, new_count,
        sum(1 for i in img_list if i not in self._image_ids_index))
    return img_list

  def DownloadFavorites(self, user_id: int, folder_id: int,  # noqa: C901
                        output_path: str, checkpoint_size: int = 0,
                        save_as_blob: bool = False) -> int:
    """Actually get the images in a picture folder.

    Args:
      user_id: User ID
      folder_id: Folder ID
      output_path: Output path
      checkpoint_size: (default 0) Commit database to disk every `checkpoint_size`
          images actually downloaded; if zero will not checkpoint at all
      save_as_blob: (default False) Save images with sha256 names (not original names)

    Returns:
      int size of all bytes downloaded
    """
    try:
      tm: int = self._favorites[user_id][folder_id]['date']  # type: ignore
      if tm and (tm + _FAVORITES_MIN_DOWNLOAD_WAIT) > base.INT_TIME():
        logging.warning(
            'Picture folder %r/%r (%d/%d) downloaded recently (%s): SKIP',
            self._users[user_id], self._favorites[user_id][folder_id]['name'], user_id, folder_id,
            base.STD_TIME_STRING(tm))
        return 0
      logging.info(
          'Downloading all images in folder %r/%r (%d/%d)',
          self._users[user_id], self._favorites[user_id][folder_id]['name'], user_id, folder_id)
      if checkpoint_size:
        logging.info('Will checkpoint DB every %d downloaded images', checkpoint_size)
      else:
        logging.warning('Will NOT checkpoint DB - work may be lost')
      img_list: list[int] = self._favorites[user_id][folder_id]['images']  # type: ignore
    except KeyError:
      raise base.Error('This user/folder was not added to DB yet: %d/%d' % (user_id, folder_id))

    def _ExtractFullImageURL(img_id: int) -> tuple[str, str]:
      """Get URL path of the full resolution image by image ID.

      Args:
        img_id: The image numerical ID

      Returns:
        (image URL path, image name path)

      Raises:
        Error: for invalid URLs or full-res URL not found
      """
      url = _IMG_URL(img_id)
      logging.info('Fetching image page: %s', url)
      img_html = LimpingURLRead(url).decode('utf-8', errors='ignore')
      full_res_urls = _FULL_IMAGE.findall(img_html)
      if not full_res_urls:
        raise Error('No full resolution image in %s' % url)
      img_name = _IMAGE_NAME.findall(img_html)
      if not img_name:
        raise Error('No image name path in %s' % url)
      return (full_res_urls[0], img_name[0])

    def _NormalizeExtension(extension: str) -> str:
      """Normalize image file extensions."""
      extension = extension.lower()
      if extension == 'jpeg':
        extension = 'jpg'
      return extension

    def _SaveImage(url: str, name: str, dir_path: str) -> tuple[str, int, str, str]:
      """Get an image by URL and save to directory. Will sanitize the file name if needed.

      Args:
        url: Image URL path
        name: Image (un-sanitized) name
        dir_path: Local disk directory path

      Returns:
        (the image sha256 hexdigest, the retrieved image bytes length, sanitized name, extension)

      Raises:
        Error: for invalid URLs or empty images
      """
      logging.info('Fetching full-res image: %s', url)
      img = LimpingURLRead(url)
      if not img:
        raise Error('Empty full-res URL: %s' % url)
      sz = len(img)
      new_name = sanitize_filename.sanitize(name)
      if new_name != name:
        logging.warning('Filename sanitization necessary %r ==> %r', name, new_name)
      sha = hashlib.sha256(img).hexdigest()
      main_name, extension = new_name.rsplit('.', 1) if '.' in new_name else (new_name, 'jpg')
      extension = _NormalizeExtension(extension)
      actual_name = '%s.%s' % (sha if save_as_blob else main_name, extension)
      full_path = os.path.join(dir_path, actual_name)
      with open(full_path, 'wb') as f:
        f.write(img)
      logging.info('Got %s for image %s (%s)',
                   base.HumanizedLength(sz), full_path, actual_name if save_as_blob else sha)
      return (sha, sz, actual_name, extension)

    # download all full resolution images we don't yet have
    total_sz, saved_count, known_count, dup_count = 0, 0, 0, 0
    for img_id in img_list:
      # figure out if we have it
      sha = self._image_ids_index.get(img_id, None)
      if sha is not None:
        found = False
        for i, _, n, uid, fid in self._blobs[sha]['loc']:  # type: ignore
          if user_id == uid and folder_id == fid:
            # this is an exact match and can be safely skipped
            found = True
            logging.info('Image %d/%r is already in DB from this album', i, n)
            break
        if found:
          known_count += 1
          continue
      # get the image's full resolution URL
      url_path, full_name = _ExtractFullImageURL(img_id)
      if sha is None:
        # we never saw this image, so we create a full entry
        sha, sz, new_name, ext = _SaveImage(url_path, full_name, output_path)
        self._blobs.setdefault(
            sha, {'loc': set(), 'tags': set(), 'sz': sz, 'ext': ext})['loc'].add(  # type: ignore
                (img_id, url_path, new_name, user_id, folder_id))
        self._image_ids_index[img_id] = sha
        total_sz += sz
        saved_count += 1
        if checkpoint_size and not saved_count % checkpoint_size:
          self.Save()
      else:
        # we have this image in a blob, so we only update the blob indexing
        logging.info('Image %d/%r does not need downloading', img_id, full_name)
        self._blobs[sha]['loc'].add(  # type: ignore
            (img_id, url_path, full_name, user_id, folder_id))
        self._image_ids_index[img_id] = sha
        dup_count += 1
    # all images were downloaded, the end
    self._favorites[user_id][folder_id]['date'] = base.INT_TIME()  # this marks album as done
    print(
        'Saved %d images to disk (%s); also %d images were already in DB and '
        '%d images were duplicates from other albums' % (
            saved_count, base.HumanizedLength(total_sz), known_count, dup_count))
    return total_sz
