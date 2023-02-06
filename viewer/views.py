"""Create your views here."""

import functools
import logging
# import pdb
from typing import Any, Literal, Optional

from django import http
from django import shortcuts
from django import conf
from django.template import defaulttags

from baselib import base
import duplicates
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

  Must cache on this specific combination of variables:
    -> db_path ensures we are looking at the same DB
    -> db_file_timestamp ensures a reload (cache invalidation) if for some reason it has changed

  Args:
    db_path: Database directory path
    db_file_timestamp: Int timestamp for last database modification
        (meant to be provided by calling fapdata.GetDatabaseTimestamp())

  Returns:
    database object

  Raises:
    fapdata.Error: if database file does not exist or fails to load correctly
  """
  logging.info('Loading database in %r from timestamp %d', db_path, db_file_timestamp)
  db = fapdata.FapDatabase(db_path, create_if_needed=False)
  db.Load()
  return db


def _DBFactory() -> fapdata.FapDatabase:
  """Get a loaded database (convenience method)."""
  return _GetLoadedDatabase(
      conf.settings.IMAGEFAP_FAVORITES_DB_PATH,
      fapdata.GetDatabaseTimestamp(conf.settings.IMAGEFAP_FAVORITES_DB_PATH))


def ServeIndex(request: http.HttpRequest) -> http.HttpResponse:
  """Serve the `index` page."""
  db = _DBFactory()
  context = {
      'users': len(db.users),
      'tags': len(tuple(db.TagsWalk())),
      'duplicates': len(db.duplicates.index),
      'n_images': len(db.blobs),
      'database_stats': db.PrintStats(actually_print=False)
  }
  return shortcuts.render(request, 'viewer/index.html', context)


def ServeUsers(request: http.HttpRequest) -> http.HttpResponse:
  """Serve the `users` page."""
  db = _DBFactory()
  context = {
      'users': db.users,
  }
  return shortcuts.render(request, 'viewer/users.html', context)


def ServeFavorites(request: http.HttpRequest, user_id: int) -> http.HttpResponse:
  """Serve the `favorites` page of one `user_id`."""
  # check for errors in parameters
  db = _DBFactory()
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


def ServeFavorite(  # noqa: C901
    request: http.HttpRequest, user_id: int, folder_id: int) -> http.HttpResponse:
  """Serve the `favorite` (album) page for an `user_id` and a `folder_id`."""
  # check for errors in parameters
  db = _DBFactory()
  if user_id not in db.users or user_id not in db.favorites:
    raise http.Http404('Unknown user %d' % user_id)
  if folder_id not in db.favorites[user_id]:
    raise http.Http404('Unknown folder %d (in known user %d)' % (folder_id, user_id))
  # retrieve the `GET` data
  show_duplicates = bool(int(request.GET.get('dup', '0')))        # default: False
  show_portraits = bool(int(request.GET.get('portrait', '1')))    # default: True
  show_landscapes = bool(int(request.GET.get('landscape', '1')))  # default: True
  # get images in album
  favorite = db.favorites[user_id][folder_id]
  images: list[int] = favorite['images']  # type: ignore
  sorted_blobs = [(i, db.image_ids_index[i]) for i in images]  # "sorted" here means original order!
  # find images that have duplicates
  # TODO: also look at perceptual duplicates!
  duplicates: dict[str, list[int]] = {}
  for img, sha in sorted_blobs:
    hits: list[int] = [i for i, _, _, uid, fid in db.blobs[sha]['loc']  # type: ignore
                       if uid == user_id and fid == folder_id]
    if len(hits) > 1:
      # this image has >=2 instances in this same album
      duplicates[sha] = hits
  # apply filters
  if not show_duplicates:
    sorted_blobs = [(i, sha) for i, sha in sorted_blobs
                    if not (sha in duplicates and duplicates[sha][0] != i)]  # type: ignore
  if not show_portraits:
    sorted_blobs = [(i, sha) for i, sha in sorted_blobs
                    if not (db.blobs[sha]['height'] / db.blobs[sha]['width'] > 1.1)]  # type: ignore
  if not show_landscapes:
    sorted_blobs = [(i, sha) for i, sha in sorted_blobs
                    if not (db.blobs[sha]['width'] / db.blobs[sha]['height'] > 1.1)]  # type: ignore
  # stack the hashes in rows of _IMG_COLUMNS columns
  stacked_blobs = [sorted_blobs[i:(i + _IMG_COLUMNS)]
                   for i in range(0, len(sorted_blobs), _IMG_COLUMNS)]
  stacked_blobs[-1] += [(0, '') for i in range(_IMG_COLUMNS - len(stacked_blobs[-1]))]
  # format blob data to be included as auxiliary data
  blobs_data = {}
  for img, sha in sorted_blobs:
    blob = db.blobs[sha]
    # find the correct 'loc' entry (to get the name)
    for i, _, name, uid, fid in blob['loc']:  # type: ignore
      if i == img and uid == user_id and fid == folder_id:
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
        'thumb': '%s.%s' % (sha, blob['ext']),  # this is just the file name, to be served as
                                                # a static resource: see settings.py
        'is_duplicate': sha in duplicates,
    }
  # send to page
  context = {
      'user_id': user_id,
      'user_name': db.users[user_id],
      'folder_id': folder_id,
      'name': favorite['name'],
      'show_duplicates': show_duplicates,
      'dup_url': 'dup=%d' % int(show_duplicates),
      'show_portraits': show_portraits,
      'portrait_url': 'portrait=%d' % int(show_portraits),
      'show_landscapes': show_landscapes,
      'landscape_url': 'landscape=%d' % int(show_landscapes),
      'pages': favorite['pages'],  # TODO: pages count has got to have some bug! it is too low!!
      'date': base.STD_TIME_STRING(favorite['date_blobs']),
      'count': len(sorted_blobs),
      'stacked_blobs': stacked_blobs,
      'blobs_data': blobs_data,
  }
  return shortcuts.render(request, 'viewer/favorite.html', context)


def ServeTags(request: http.HttpRequest) -> http.HttpResponse:
  """Serve the `tags` page."""
  db = _DBFactory()
  # walk the tags and take them in
  tags = [(tid, db.PrintableTag(tid)) for tid, _, _, _ in db.TagsWalk()]
  context = {
      'tags': tags
  }
  return shortcuts.render(request, 'viewer/tags.html', context)


def ServeTag(request: http.HttpRequest, tag_id: int) -> http.HttpResponse:
  """Serve the `tag` page for one `tag_id`."""
  # check for errors in parameters
  db = _DBFactory()
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
  db = _DBFactory()
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
  db = _DBFactory()
  sorted_keys = sorted(db.duplicates.index.keys(), key=lambda x: x[0])
  context = {
      'duplicates': {
          k: {
              'size': len(k),
              'action': any(st == 'new' for _, st in db.duplicates.index[k].items()),
          }
          for k in sorted_keys
      },
  }
  return shortcuts.render(request, 'viewer/duplicates.html', context)


def ServeDuplicate(request: http.HttpRequest, digest: str) -> http.HttpResponse:
  """Serve the `duplicate` page, with a set of duplicates, by giving one of the SHA256 `digest`."""
  # check for errors in parameters
  db = _DBFactory()
  error_message: Optional[str] = None
  if digest not in db.blobs:
    raise http.Http404('Unknown blob %r' % digest)
  sorted_keys = sorted(db.duplicates.index.keys(), key=lambda x: x[0])
  for current_index, dup_keys in enumerate(sorted_keys):
    if digest in dup_keys:
      break
  else:
    raise http.Http404('Blob %r does not correspond to a duplicate set' % digest)
  dup_obj = db.duplicates.index[dup_keys]
  # get user selected choice, if any and update database
  if request.POST:
    for sha in dup_keys:
      # check that the selection is valid
      if sha not in request.POST:
        error_message = 'Expected key %r in POST data, but didn\'t find it!' % sha
        break
      selected_option: Literal['new', 'false', 'keep', 'skip'] = request.POST[sha]  # type: ignore
      if selected_option not in duplicates.DUPLICATE_OPTIONS:
        error_message = 'Key %r in POST data has invalid option %r!' % (sha, selected_option)
        break
      # set data in DB structure
      dup_obj[sha] = selected_option
    else:
      # everything went smoothly (no break action above), so save the data
      db.Save()
  # send to page
  context = {
      'digest': digest,
      'current_index': current_index,
      'previous_key': sorted_keys[current_index - 1] if current_index else None,
      'next_key': (sorted_keys[current_index + 1]
                   if current_index < (len(sorted_keys) - 1) else None),
      'dup_keys': dup_keys,
      'duplicates': {
          sha: {
              'action': dup_obj[sha],
              'loc': {
                  i: {
                      'file_name': nm,
                      'user_id': uid,
                      'user_name': db.users[uid],
                      'folder_id': fid,
                      'folder_name': db.favorites[uid][fid]['name'],
                  }
                  for i, _, nm, uid, fid in db.blobs[sha]['loc']  # type: ignore
              },
              'sz': base.HumanizedBytes(db.blobs[sha]['sz']),  # type: ignore
              'dimensions': '%dx%d (WxH)' % (db.blobs[sha]['width'], db.blobs[sha]['height']),
              'tags': ', '.join(sorted(
                  db.PrintableTag(t) for t in db.blobs[sha]['tags'])),  # type: ignore
              'thumb': '%s.%s' % (sha, db.blobs[sha]['ext']),  # this is just the file name, served
                                                               # as a static resource (settings.py)
              'percept': db.blobs[sha]['percept'],
          }
          for sha in dup_keys
      },
      'error_message': error_message,
  }
  # TODO: if saved, go to next
  return shortcuts.render(request, 'viewer/duplicate.html', context)
