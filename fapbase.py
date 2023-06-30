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
"""Imagefap.com base methods and constants."""

import functools
import hashlib
import html
import http.client
import logging
import os
import os.path
# import pdb
import random
import re
import socket
import time
from typing import Optional
import urllib.error
import urllib.request

import sanitize_filename

from baselib import base


__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (2, 0)


# useful globals
_MAX_RETRY = 10         # int number of retries for URL get
_URL_TIMEOUT = 15.0     # URL timeout, in seconds
_PAGE_BACKTRACKING_THRESHOLD = 5

IMAGE_TYPES = {
    'bmp': 'image/bmp',
    'gif': 'image/gif',
    'jfif': 'image/jpeg',  # this is very much exactly a JPEG # cspell:disable-line
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'mpo': 'image/jpeg',   # Multi-Picture Object: a stereo image
    'png': 'image/png',
    'tiff': 'image/tiff',
}


# the site page templates we need
_USER_PAGE_URL = lambda n: f'https://www.imagefap.com/profile/{n}'
FAVORITES_URL = (
    lambda u, p: f'https://www.imagefap.com/showfavorites.php?userid={u}&page={p}')
FOLDER_URL = lambda u, f, p: f'{FAVORITES_URL(u, p)}&folderid={f}'  # cspell:disable-line
IMG_URL = lambda id: f'https://www.imagefap.com/photo/{id}/'

# the regular expressions we use to navigate the pages
_FIND_ONLY_IN_PICTURE_FOLDER = re.compile(r'<\/a><\/td><\/tr>\s+<\/table>\s+<table')
_FIND_ONLY_IN_GALLERIES_FOLDER = re.compile(
    r'<td\s+class=.blk_favorites_hdr.*<b>Gallery Name<\/span>')
_FIND_NAME_IN_FAVORITES = re.compile(
    r'<a\s+class=.blk_header.\s+href="\/profile\.php\?user=(.*)"\s+style="')
_FIND_USER_ID_RE = re.compile(  # cspell:disable-next-line
    r'<a\s+class=.blk_header.\s+href="\/showfavorites.php\?userid=([0-9]+)".*>')
FIND_NAME_IN_FOLDER = re.compile(
    r'<a\s+class=.blk_favorites.\s+href=".*none;">(.*)<\/a><\/td><\/tr>')
FIND_FOLDERS = re.compile(
    r'<td\s+class=.blk_favorites.><a\s+class=.blk_galleries.\s+href="'
    r'https:\/\/www.imagefap.com\/showfavorites.php\?userid=[0-9]+'  # cspell:disable-line
    r'&folderid=([0-9]+)".*>(.*)<\/a><\/td>')                        # cspell:disable-line
_FAVORITE_IMAGE = re.compile(r'<td\s+class=.blk_favorites.\s+id="img-([0-9]+)"\s+align=')
FULL_IMAGE = lambda img_id: re.compile(
    r'<a\shref=\"(https:\/\/.*\/images\/full\/.*\/' + str(img_id) + r'\..*)"\sframed=')
_IMAGE_NAME = re.compile(
    r'<meta\s+name="description"\s+content="View this hot (.*) porn pic uploaded by')


# internal types definitions
FailedTupleType = tuple[int, int, Optional[str], Optional[str]]


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
    return (f'Error404(ID: {0 if self.image_id is None else self.image_id}, '
            f'@{base.STD_TIME_STRING(self.timestamp)}, '
            f'{"-" if self.image_name is None else self.image_name!r}, '
            f'{"-" if self.url is None else self.url!r})')

  def FailureTuple(self, log: bool = False) -> FailedTupleType:
    """Get a failure tuple for this 404.

    Args:
      log: (Default False) If true will log the failed image to stderr
    """
    if log:
      logging.error('FAILED IMAGE: %s', self)
    return (
        0 if self.image_id is None else self.image_id,
        self.timestamp,
        self.image_name,
        self.url)


def ConvertUserName(user_name: str) -> int:
  """Convert imagefap user name to user ID.

  Args:
    user_name: User name

  Returns:
    imagefap user ID

  Raises:
    Error: invalid name or user not found
  """
  user_name = user_name.strip()
  if not user_name:
    raise Error('Empty user name')
  url: str = _USER_PAGE_URL(user_name)
  logging.info('Fetching user page: %s', url)
  user_html = FapHTMLRead(url)
  user_ids: list[str] = _FIND_USER_ID_RE.findall(user_html)
  if len(user_ids) != 1:
    raise Error(f'Could not find ID for user {user_name!r}')
  return int(user_ids[0])


def GetUserDisplayName(user_id: int) -> str:
  """Convert imagefap user name to user ID.

  Args:
    user_id: User ID

  Returns:
    imagefap actual display name

  Raises:
    Error: invalid ID or display name not found
  """
  if not user_id:
    raise Error('Empty user ID')
  url: str = FAVORITES_URL(user_id, 0)  # use the favorites page
  logging.info('Fetching favorites page: %s', url)
  user_html = FapHTMLRead(url)
  user_names: list[str] = _FIND_NAME_IN_FAVORITES.findall(user_html)
  if len(user_names) != 1:
    raise Error(f'Could not find user name for {user_id}')
  return html.unescape(user_names[0])


def ConvertFavoritesName(user_id: int, favorites_name: str) -> tuple[int, str]:
  """Convert imagefap favorites album name to album ID.

  Args:
    user_id: User ID
    favorites_name: Favorites album name

  Returns:
    (imagefap favorites album ID, actual favorites album name)

  Raises:
    Error: empty inputs, picture folder not found, or is not a picture folder
  """
  favorites_name = favorites_name.strip()
  if not user_id or not favorites_name:
    raise Error('Empty user ID or favorites name')
  page_num: int = 0
  while True:
    url: str = FAVORITES_URL(user_id, page_num)
    logging.info('Fetching favorites page: %s', url)
    fav_html = FapHTMLRead(url)
    favorites_page: list[tuple[str, str]] = FIND_FOLDERS.findall(fav_html)
    if not favorites_page:
      raise Error(f'Could not find picture folder {favorites_name!r} for user {user_id}')
    for f_id, f_name in favorites_page:
      i_f_id, f_name = int(f_id), html.unescape(f_name)
      if f_name.lower() == favorites_name.lower():
        # found it!
        CheckFolderIsForImages(user_id, i_f_id)  # raises Error if not valid
        return (i_f_id, f_name)
    page_num += 1


def GetFolderPics(
    user_id: int,
    folder_id: int,
    img_list_hint: Optional[list[int]] = None,
    seen_pages_hint: int = 0) -> tuple[list[int], int, int]:
  """Read a folder and collect/compile all image IDs that are found, for all pages.

  This always goes through all favorite pages, as we want to always
  find new images, and it counts how many are new.

  Args:
    user_id: User int ID
    folder_id: Folder int ID
    img_list_hint: (default None) Optional. If given will suppose the image list given has already
        been seen in this album. Useful for continuing work.
    seen_pages_hint: (default 0) Optional. If given will suppose this is the number of the last page
        seen in this album. Useful for continuing work.

  Returns:
    (list of all image ids, number of last seen page, new images count)
  """
  # do the paging backtracking, if adequate; this is guaranteed to work because
  # the site only adds images to the *end* of the images favorites; on the other
  # hand there is the issue of the "disappearing" images, so we have to backtrack
  # to make sure we don't loose any...
  page_num: int = 0
  new_count: int = 0
  img_list = [] if img_list_hint is None else img_list_hint
  seen_pages = seen_pages_hint
  img_set: set[int] = set(img_list)
  if seen_pages >= _PAGE_BACKTRACKING_THRESHOLD:
    logging.warning('Backtracking from last seen page (%d) to save time', seen_pages)
    page_num = seen_pages - 1  # remember the site numbers pages starting on zero
    while page_num >= 0:
      new_ids = ExtractFavoriteIDs(page_num, user_id, folder_id)
      if set(new_ids).intersection(img_set):
        # found last page that matters to backtracking (because it has images we've seen before)
        break
      page_num -= 1
  # get the pages of links, until they end
  while True:
    new_ids = ExtractFavoriteIDs(page_num, user_id, folder_id)
    if not new_ids:
      # we should be able to stop (break) here, but the Imagefap site has this horrible bug
      # where we might have empty pages in the middle of the album and then have images again,
      # and because of this we should try a few more pages just to make sure, even if most times
      # it will be a complete waste of our time...
      new_ids = ExtractFavoriteIDs(page_num + 1, user_id, folder_id)  # extra safety page 1
      if not new_ids:
        new_ids = ExtractFavoriteIDs(page_num + 2, user_id, folder_id)  # extra safety page 2
        if not new_ids:
          break  # after 2 extra safety pages, we hope we can now safely give up...
        page_num += 2  # we found something (2nd extra page), remember to increment page counter
        logging.warning('Album %d/%d had 2 EMPTY PAGES in the middle of the page list!',
                        user_id, folder_id)
      else:
        page_num += 1  # we found something (1st extra page), remember to increment page counter
        logging.warning('Album %d/%d had 1 EMPTY PAGES in the middle of the page list!',
                        user_id, folder_id)
    # add the images to the end, preserve order, but skip the ones already there
    for img_id in new_ids:
      if img_id not in img_set:
        img_list.append(img_id)
        new_count += 1
    img_set = set(img_list)
    page_num += 1
  # finished, return results
  return (img_list, page_num, new_count)


def GetBinary(url: str) -> tuple[bytes, str]:
  """Get an image by URL and compute SHA for binary data.

  Args:
    url: Image URL path

  Returns:
    (image_bytes, image_sha256_hexdigest)

  Raises:
    Error: for invalid URLs or empty images
  """
  # get the full image binary
  logging.info('Fetching full-res image: %s', url)
  img_data = LimpingURLRead(url)  # (let Error404 bubble through...)
  if not img_data:
    raise Error(f'Empty full-res URL: {url}')
  return (img_data, hashlib.sha256(img_data).hexdigest())


def DownloadFavorites(user_id: int, folder_id: int, output_path: str) -> None:
  """Actually get the images in a picture folder.

  Args:
    user_id: User ID
    folder_id: Folder ID
    output_path: Path to output images to (may be created if non-existent)

  Raises:
    Error: on empty inputs
  """
  if not user_id or not folder_id or not output_path.strip():
    raise Error('Empty inputs: you must provide user, folder, and output directory')
  # create thumbnails directory, if needed
  output_path = os.path.expanduser(output_path.strip())
  if not os.path.exists(output_path):
    logging.info('Creating output directory %r', output_path)
    os.mkdir(output_path)
  # download all full resolution images we don't yet have
  total_sz: int = 0
  saved_count: int = 0
  failed_count: int = 0
  skipped_count: int = 0
  img_ids, pages_count, _ = GetFolderPics(user_id, folder_id)
  logging.info('Got %d images in %d pages from album', len(img_ids), pages_count)
  for img_id in img_ids:
    sanitized_image_name: Optional[str] = None
    try:
      # get image's full resolution URL + name
      url_path, sanitized_image_name, _ = ExtractFullImageURL(img_id)
      image_path = os.path.join(output_path, sanitized_image_name)
      # check if we already have this image
      if os.path.exists(image_path):
        skipped_count += 1
        logging.warning('Image %r already exists at destination: SKIP', image_path)
        continue
      # get the binary data so we can compute the SHA for this image
      image_bytes, _ = GetBinary(url_path)
    except Error404 as err:
      err.image_id = img_id
      err.image_name = sanitized_image_name
      logging.error('Image failure: %s', err)
      failed_count += 1
      continue
    # write image to the final disk destination
    SaveNoClash(output_path, sanitized_image_name, image_bytes)
    total_sz += len(image_bytes)
    saved_count += 1
  # all images were downloaded, the end
  print(f'Saved {saved_count} images to disk ({base.HumanizedBytes(total_sz)}), '
        f'skipped {skipped_count} name collisions, and had {failed_count} image failures')


def LimpingURLRead(url: str, min_wait: float = 1.0, max_wait: float = 2.0) -> bytes:
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
  n_retry: int = 0
  last_error: Optional[str] = None
  while n_retry <= _MAX_RETRY:
    # sleep to keep Imagefap happy
    time.sleep(random.uniform(min_wait, max_wait))  # nosec
    try:
      # get the URL
      last_error = None
      return urllib.request.urlopen(url, timeout=_URL_TIMEOUT).read()  # nosec
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        urllib.error.ContentTooShortError,
        http.client.HTTPException,  # this is the parent for all HTTP exceptions
        socket.timeout) as err:
      # these errors sometimes happen and can be a case for retry
      n_retry += 1
      last_error = str(err)
      logging.error('%r error for URL %r, RETRY # %d', last_error, url, n_retry)
  # only way to reach here is exceeding retries
  if last_error is not None and 'http error 404' in last_error.lower():
    raise Error404(url)
  raise Error(f'Max retries reached on URL {url!r}')


def FapHTMLRead(url: str) -> str:
  """Plain wrapper for LimpingURLRead(), but it decodes page content as UTF-8 before returning."""
  return LimpingURLRead(url).decode('utf-8', errors='ignore')  # (let Error404 bubble through...)


def CheckFolderIsForImages(user_id: int, folder_id: int) -> None:
  """Check that a folder is an *image* folder, not a *galleries* folder.

  Args:
    user_id: User int ID
    folder_id: Folder int ID

  Raises:
    Error: if folder is not an image folder (i.e. it might be a galleries folder)
  """
  url: str = FOLDER_URL(user_id, folder_id, 0)  # use the folder's 1st page
  logging.debug('Fetching favorites to check *not* a galleries folder: %s', url)
  folder_html = FapHTMLRead(url)
  should_have: list[str] = _FIND_ONLY_IN_PICTURE_FOLDER.findall(folder_html)
  should_not_have: list[str] = _FIND_ONLY_IN_GALLERIES_FOLDER.findall(folder_html)
  if should_not_have or not should_have:
    raise Error('This is not a valid images folder! Maybe it is a galleries folder?')


def GetDirectoryName(dir_path: str) -> str:
  """Get the directory name for a directory path."""
  dir_path = dir_path.strip()
  if dir_path.endswith('/'):
    dir_path = dir_path[:-1]
  return dir_path.rsplit('/', maxsplit=1)[-1]  # cspell:disable-line


def NormalizeFileName(file_name: str) -> str:
  """Normalize image file name."""
  new_name: str = sanitize_filename.sanitize(html.unescape(file_name.strip()).replace('/', '-'))
  if new_name != file_name:
    logging.warning('Filename sanitization necessary %r ==> %r', file_name, new_name)
  return new_name


def NormalizeExtension(extension: str) -> str:
  """Normalize image file extensions."""
  extension = extension.strip().lower()
  if extension == 'jpeg':
    extension = 'jpg'
  return extension


@functools.cache
def ExtractFavoriteIDs(page_num: int, user_id: int, folder_id: int) -> list[int]:
  """Get numerical IDs of all images in a picture folder by URL.

  Args:
    page_num: Page to request (starting on 0!)
    user_id: User ID
    folder_id: Folder ID

  Returns:
    list of integer image IDs; empty list on last (empty) page
  """
  url: str = FOLDER_URL(user_id, folder_id, page_num)
  logging.info('Fetching favorites page: %s', url)
  fav_html = FapHTMLRead(url)
  images: list[str] = _FAVORITE_IMAGE.findall(fav_html)
  image_ids = [int(id) for id in images]
  logging.info('Got %d image IDs', len(image_ids))
  return image_ids


def ExtractFullImageURL(img_id: int) -> tuple[str, str, str]:
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
    img_html = FapHTMLRead(url)
  except Error404 as err:
    err.image_id = img_id
    raise
  full_res_urls: list[str] = FULL_IMAGE(img_id).findall(img_html)
  if len(full_res_urls) != 1:
    raise Error(f'Invalid full resolution page in {url!r}')
  # from the same source extract image file name
  img_name: list[str] = _IMAGE_NAME.findall(img_html)
  if not img_name:
    raise Error(f'No image name path in {url!r}')
  # sanitize image name, figure out the file name, sanitize extension
  new_name = NormalizeFileName(img_name[0])
  main_name, extension = new_name.rsplit('.', 1) if '.' in new_name else (new_name, 'jpg')
  sanitized_extension = NormalizeExtension(extension)
  sanitized_image_name = f'{main_name}.{sanitized_extension}'
  return (full_res_urls[0], sanitized_image_name, sanitized_extension)


def SaveNoClash(dir_path: str, file_name: str, file_data: bytes) -> Optional[str]:
  """Save data to disk, but skip if identical file exists or rename if another one exists in path.

  If no file exists in destination, saves the file_data to the desired path (dir_path + file_name).

  If an identical file exists in the desired path, does nothing and returns None. Checks by SHA256.

  If a non-identical file exists in the desired path, this will rename and then save file_data.
  The implemented name clash avoidance (by renaming the file) is *almost* fool-proof: it may have
  a 1-in-a-million birthday collision. The file will be renamed to f'{sha[:10]}-{file_name}',
  so the added blurb is a 2**40 namespace (10 hex digits), which means a 2**20 birthday collision,
  which is more or less 1-in-a-million.

  Args:
    dir_path: Directory to save to
    file_name: File name to try to save to
    file_data: Bytes to save to file

  Returns:
    The actual file_name saved to if the file was saved, None otherwise (i.e. if identical file
    already existed in this path)
  """
  original_file_name = file_name
  file_path = os.path.join(dir_path, file_name)
  # check if the file exists
  if os.path.exists(file_path):
    # it exists... but is it the same, or a name clash?
    old_sha = hashlib.sha256(file_data).hexdigest()
    with open(file_path, 'rb') as file_obj:
      existing_sha = hashlib.sha256(file_obj.read()).hexdigest()
    if old_sha == existing_sha:
      # it is exactly the same, so we can safely skip
      logging.info('Already exists: %s (SKIP)', file_path)
      return None
    # name clash, so do an almost-fool-proof rename (1-in-a-million birthday collision)
    file_name = f'{old_sha[:10]}-{file_name}'  # 2**40 namespace -> 2**20 birthday collision
    file_path = os.path.join(dir_path, file_name)
    logging.warning('File clash rename: %r -> %r', original_file_name, file_name)
  # we have a trustworthy file path, so save the file
  with open(file_path, 'wb') as file_obj:
    file_obj.write(file_data)
  logging.info('Saved %s in: %s', base.HumanizedBytes(len(file_data)), file_path)
  return file_name
