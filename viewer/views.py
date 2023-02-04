"""Create your views here."""

import functools
import logging
import pdb
from typing import Any

from django import http
from django import shortcuts
from django.template import defaulttags

from baselib import base
import fapdata


_IMAGE_TYPES = {
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'gif': 'image/gif',
    'png': 'image/png',
    'tiff': 'image/tiff',
}

_IMG_COLUMNS = 4


@defaulttags.register.filter(name='lookup')
def lookup(value: dict, arg: Any) -> Any:
  """Lookup dictionary (so we can use it in the templates)."""
  return value[arg]


class SHA256HexDigest:
  """Django path converter for a SHA256 hexadecimal digest (exactly 64 chars of hexadecimal)."""

  regex = r'[0-9a-fA-F]{64}'  # 64 chars of lower or upper-case hexadecimal

  def to_python(self, value: str) -> str:
    """Convert from URL to (python) type."""
    return value.lower()

  def to_url(self, value: str) -> str:
    """Convert from (python) type to URL."""
    return value.lower()


@functools.cache
def _GetLoadedDatabase(db_path: str, db_file_timestamp: int) -> fapdata.FapDatabase:
  """Load database, cached. Called with database timestamp so it reloads if a Save() happened.

  Args:
    db_path: Database directory path
    db_file_timestamp: Int timestamp for last database modification
        (meant to be provided by calling fapdata.GetDatabaseTimestamp())

  Returns:
    database object

  Raises:
    fapdata.Error: if database file does not exist or fails to load correctly
  """
  # TODO: Find a way to communicate database path from main() module to here, so we can use
  #     paths other than the default DEFAULT_DB_DIRECTORY!!
  logging.info('Loading database in %r from timestamp %d', db_path, db_file_timestamp)
  db = fapdata.FapDatabase(db_path, create_if_needed=False)
  db.Load()
  return db


def ServeIndex(request: http.HttpRequest) -> http.HttpResponse:
  """Serve the `index` page."""
  db = _GetLoadedDatabase(fapdata.DEFAULT_DB_DIRECTORY, fapdata.GetDatabaseTimestamp())
  context = {
      'users': len(db.users),
      'tags': len(tuple(db.TagsWalk())),
      'duplicates': len(db.duplicates.index),
      'n_images': len(db.blobs),
  }
  return shortcuts.render(request, 'viewer/index.html', context)


def ServeUsers(request: http.HttpRequest) -> http.HttpResponse:
  """Serve the `users` page."""
  db = _GetLoadedDatabase(fapdata.DEFAULT_DB_DIRECTORY, fapdata.GetDatabaseTimestamp())
  context = {
      'users': db.users,
  }
  return shortcuts.render(request, 'viewer/users.html', context)


def ServeFavorites(request: http.HttpRequest, user_id: int) -> http.HttpResponse:
  """Serve the `favorites` page of one `user_id`."""
  # check for errors in parameters
  db = _GetLoadedDatabase(fapdata.DEFAULT_DB_DIRECTORY, fapdata.GetDatabaseTimestamp())
  if user_id not in db.users or user_id not in db.favorites:
    raise http.Http404('Unknown user %d' % user_id)
  user_favorites = db.favorites[user_id]
  # sort albums alphabetically and format data
  names = sorted(((fid, obj['name']) for fid, obj in user_favorites.items()), key=lambda x: x[1])
  favorites = {fid: {'name': name, 'pages': user_favorites[fid]['pages'],
                     'date': base.STD_TIME_STRING(user_favorites[fid]['date_blobs']),
                     'count': len(user_favorites[fid]['images'])}  # type: ignore
               for fid, name in names}
  # send to page
  context = {
      'user_id': user_id,
      'user_name': db.users[user_id],
      'favorites': favorites,
  }
  return shortcuts.render(request, 'viewer/favorites.html', context)


def ServeFavorite(request: http.HttpRequest, user_id: int, folder_id: int) -> http.HttpResponse:
  """Serve the `favorite` (album) page for an `user_id` and a `folder_id`."""
  # check for errors in parameters
  db = _GetLoadedDatabase(fapdata.DEFAULT_DB_DIRECTORY, fapdata.GetDatabaseTimestamp())
  if user_id not in db.users or user_id not in db.favorites:
    raise http.Http404('Unknown user %d' % user_id)
  if folder_id not in db.favorites[user_id]:
    raise http.Http404('Unknown folder %d (in known user %d)' % (folder_id, user_id))
  # get images in album
  favorite = db.favorites[user_id][folder_id]
  images: list[int] = favorite['images']  # type: ignore
  sorted_blobs = [db.image_ids_index[i] for i in images]  # "sorted" here means original order!
  # stack the hashes in rows of _IMG_COLUMNS columns
  stacked_blobs = [sorted_blobs[i:(i + _IMG_COLUMNS)]
                   for i in range(0, len(sorted_blobs), _IMG_COLUMNS)]
  stacked_blobs[-1] += ['' for i in range(_IMG_COLUMNS - len(stacked_blobs[-1]))]
  # format blob data to be included as auxiliary data
  blobs_data = {}
  for sha in sorted_blobs:
    blob = db.blobs[sha]
    # find the correct 'loc' entry (to get the name)
    for _, _, name, uid, fid in blob['loc']:  # type: ignore
      if uid == user_id and fid == folder_id:
        break
    else:
      raise fapdata.Error(
          'Blob %r in %d/%d did not have a matching `loc` entry!' % (sha, user_id, folder_id))
    # fill in the other fields, make them readable
    blobs_data[sha] = {
        'name': name,
        'sz': base.HumanizedBytes(blob['sz']),  # type: ignore
        'dimensions': '%dx%d (WxH)' % (blob['width'], blob['height']),
        'tags': ', '.join(sorted(db.PrintableTag(t) for t in blob['tags'])),  # type: ignore
    }
  # send to page
  context = {
      'user_id': user_id,
      'user_name': db.users[user_id],
      'folder_id': folder_id,
      'name': favorite['name'],
      'pages': favorite['pages'],  # TODO: pages count has got to have some bug! it is too low!!
      'date': base.STD_TIME_STRING(favorite['date_blobs']),
      'count': len(images),
      'stacked_blobs': stacked_blobs,
      'blobs_data': blobs_data,
  }
  return shortcuts.render(request, 'viewer/favorite.html', context)


def ServeTags(request: http.HttpRequest) -> http.HttpResponse:
  """Serve the `tags` page."""
  db = _GetLoadedDatabase(fapdata.DEFAULT_DB_DIRECTORY, fapdata.GetDatabaseTimestamp())
  # walk the tags and take them in
  tags = [(tid, db.PrintableTag(tid)) for tid, _, _, _ in db.TagsWalk()]
  context = {
      'tags': tags
  }
  return shortcuts.render(request, 'viewer/tags.html', context)


def ServeTag(request: http.HttpRequest, tag_id: int) -> http.HttpResponse:
  """Serve the `tag` page for one `tag_id`."""
  # check for errors in parameters
  db = _GetLoadedDatabase(fapdata.DEFAULT_DB_DIRECTORY, fapdata.GetDatabaseTimestamp())
  if tag_id not in db.tags:
    raise http.Http404('Unknown tag %d' % tag_id)
  # send to page
  context = {
      'tag_id': tag_id,
      'name': db.PrintableTag(tag_id),
  }
  return shortcuts.render(request, 'viewer/tag.html', context)


def ServeBlob(request: http.HttpRequest, digest: str) -> http.HttpResponse:
  """Serve the `blob` page, one image, given one SHA256 `digest`."""
  # check for errors in parameters
  db = _GetLoadedDatabase(fapdata.DEFAULT_DB_DIRECTORY, fapdata.GetDatabaseTimestamp())
  if not digest or digest not in db.blobs:
    raise http.Http404('Unknown blob %r' % digest)
  if not db.HasBlob(digest):
    raise http.Http404('Known blob %r could not be found on disk' % digest)
  # get blob and check for content type (extension)
  blob = db.blobs[digest]
  ext = blob['ext'].lower()  # type: ignore
  if ext not in _IMAGE_TYPES:
    raise http.Http404('Blob %r image type (file extension) %r not one of %r' % (
        digest, ext, sorted(_IMAGE_TYPES.keys())))
  # send to page
  return http.HttpResponse(content=db.GetBlob(digest), content_type=_IMAGE_TYPES[ext])
  # TODO: investigate why this seems to be executing TWICE when called


def ServeDuplicates(request: http.HttpRequest) -> http.HttpResponse:
  """Serve the `duplicates` page."""
  db = _GetLoadedDatabase(fapdata.DEFAULT_DB_DIRECTORY, fapdata.GetDatabaseTimestamp())
  context = {
      # TODO: fill context with actual data
  }
  return shortcuts.render(request, 'viewer/duplicates.html', context)


def ServeDuplicate(request: http.HttpRequest, digest: str) -> http.HttpResponse:
  """Serve the `duplicate` page, with a set of duplicates, by giving one of the SHA256 `digest`."""
  # check for errors in parameters
  db = _GetLoadedDatabase(fapdata.DEFAULT_DB_DIRECTORY, fapdata.GetDatabaseTimestamp())
  # send to page
  context = {
      'digest': digest,
      # TODO: fill context with actual data
  }
  return shortcuts.render(request, 'viewer/duplicate.html', context)
