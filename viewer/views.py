"""Create your views here."""

import functools
import logging
# import pdb
import statistics
from typing import Any, Literal, Optional

from django import http
from django import shortcuts
from django import conf
from django.views.decorators import cache
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
      'dup_action': sum(1 for d in db.duplicates.index.values()
                        if any(st == 'new' for st in d.values())),
      'n_images': len(db.blobs),
      'database_stats': db.PrintStats(actually_print=False),
  }
  return shortcuts.render(request, 'viewer/index.html', context)


def ServeUsers(request: http.HttpRequest) -> http.HttpResponse:
  """Serve the `users` page."""
  db = _DBFactory()
  users, total_sz, total_img, total_animated, total_thumbs = {}, 0, 0, 0, 0
  for uid, name in db.users.items():
    file_sizes: list[int] = [
        db.blobs[db.image_ids_index[i]]['sz']
        for d, u in db.favorites.items() if d == uid
        for f in u.values()
        for i in f['images'] if i in db.image_ids_index]  # type: ignore
    thumbs_sizes: list[int] = [
        db.blobs[db.image_ids_index[i]]['sz_thumb']
        for d, u in db.favorites.items() if d == uid
        for f in u.values()
        for i in f['images'] if i in db.image_ids_index]  # type: ignore
    n_animated = sum(
        bool(db.blobs[db.image_ids_index[i]]['animated'])
        for d, u in db.favorites.items() if d == uid
        for f in u.values()
        for i in f['images'] if i in db.image_ids_index)  # type: ignore
    n_img = len(file_sizes)
    users[uid] = {
        'name': name,
        'n_img': n_img,
        'n_animated': '%d (%0.1f%%)' % (
            n_animated, (100.0 * n_animated / n_img) if n_img else 0.0),
        'files_sz': base.HumanizedBytes(sum(file_sizes) if file_sizes else 0),
        'thumbs_sz': base.HumanizedBytes(sum(thumbs_sizes) if thumbs_sizes else 0),
        'min_sz': base.HumanizedBytes(min(file_sizes)) if file_sizes else '-',
        'max_sz': base.HumanizedBytes(max(file_sizes)) if file_sizes else '-',
        'mean_sz': base.HumanizedBytes(int(statistics.mean(file_sizes))) if file_sizes else '-',
        'dev_sz': base.HumanizedBytes(
            int(statistics.stdev(file_sizes))) if len(file_sizes) > 2 else '-',
    }
    total_img += n_img
    total_animated += n_animated
    total_sz += sum(file_sizes) if file_sizes else 0
    total_thumbs += sum(thumbs_sizes) if file_sizes else 0
  context = {
      'users': users,
      'user_count': len(users),
      'total_img': total_img,
      'total_animated': '%d (%0.1f%%)' % (
          total_animated, (100.0 * total_animated / total_img) if total_img else 0.0),
      'total_sz': base.HumanizedBytes(total_sz) if total_sz else '-',
      'total_thumbs': base.HumanizedBytes(total_thumbs) if total_thumbs else '-',
      'total_file_storage': base.HumanizedBytes(
          total_sz + total_thumbs) if (total_sz + total_thumbs) else '-',
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
  favorites, total_sz, total_thumbs_sz, total_animated = {}, 0, 0, 0
  for fid, name in names:
    obj = db.favorites[user_id][fid]
    count_img = len(obj['images'])  # type: ignore
    file_sizes: list[int] = [
        db.blobs[db.image_ids_index[i]]['sz']
        for i in obj['images'] if i in db.image_ids_index]  # type: ignore
    thumbs_sizes: list[int] = [
        db.blobs[db.image_ids_index[i]]['sz_thumb']
        for i in obj['images'] if i in db.image_ids_index]  # type: ignore
    n_animated = sum(
        int(db.blobs[db.image_ids_index[i]]['animated'])    # type: ignore
        for i in obj['images'] if i in db.image_ids_index)  # type: ignore
    favorites[fid] = {
        'name': name,
        'pages': obj['pages'],
        'date': base.STD_TIME_STRING(obj['date_blobs']),
        'count': count_img,
        'files_sz': base.HumanizedBytes(sum(file_sizes) if file_sizes else 0),
        'min_sz': base.HumanizedBytes(min(file_sizes)) if file_sizes else '-',
        'max_sz': base.HumanizedBytes(max(file_sizes)) if file_sizes else '-',
        'mean_sz': base.HumanizedBytes(int(statistics.mean(file_sizes))) if file_sizes else '-',
        'dev_sz': base.HumanizedBytes(
            int(statistics.stdev(file_sizes))) if len(file_sizes) > 2 else '-',
        'thumbs_sz': base.HumanizedBytes(sum(thumbs_sizes) if thumbs_sizes else 0),
        'n_animated': '%d (%0.1f%%)' % (
            n_animated, (100.0 * n_animated / count_img) if count_img else 0.0),
    }
    total_sz += sum(file_sizes) if file_sizes else 0
    total_thumbs_sz += sum(thumbs_sizes) if thumbs_sizes else 0
    total_animated += n_animated
  # send to page
  all_img_count = sum(f['count'] for f in favorites.values())
  context = {
      'user_id': user_id,
      'user_name': db.users[user_id],
      'favorites': favorites,
      'album_count': len(names),
      'img_count': all_img_count,
      'page_count': sum(f['pages'] for f in favorites.values()),
      'total_sz': base.HumanizedBytes(total_sz) if total_sz else '-',
      'total_thumbs_sz': base.HumanizedBytes(total_thumbs_sz) if total_thumbs_sz else '-',
      'total_animated': '%d (%0.1f%%)' % (
          total_animated, (100.0 * total_animated / all_img_count) if all_img_count else 0.0),
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
  locked_for_tagging = bool(int(request.GET.get('lock', '0')))    # default: False
  # get images in album
  favorite = db.favorites[user_id][folder_id]
  images: list[int] = favorite['images']  # type: ignore
  sorted_blobs = [(i, db.image_ids_index[i]) for i in images]  # "sorted" here means original order!
  # find images that have duplicates
  duplicates: dict[str, list[int]] = {}
  percept_exclude: set[str] = set()
  for img, sha in sorted_blobs:
    # look for identical (sha256) collisions in the same album
    hits: list[int] = [i for i, _, _, uid, fid in db.blobs[sha]['loc']  # type: ignore
                       if uid == user_id and fid == folder_id]
    if len(hits) > 1:
      # this image has >=2 instances in this same album
      duplicates[sha] = hits
    # look in perceptual index if this image is marked as 'skip'
    for k, st in db.duplicates.index.items():
      if sha in k:
        if st[sha] == 'skip':
          percept_exclude.add(sha)
  # apply filters
  if not show_duplicates:
    sorted_blobs = [(i, sha) for i, sha in sorted_blobs
                    if not (sha in duplicates and duplicates[sha][0] != i)]  # type: ignore
    sorted_blobs = [(i, sha) for i, sha in sorted_blobs
                    if not (sha in percept_exclude)]  # type: ignore
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
        'is_percept': sha in percept_exclude,
        'imagefap': fapdata.IMG_URL(img),
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
      'locked_for_tagging': locked_for_tagging,
      'tagging_url': 'lock=%d' % int(locked_for_tagging),
      'pages': favorite['pages'],
      'date': base.STD_TIME_STRING(favorite['date_blobs']),
      'count': len(sorted_blobs),
      'stacked_blobs': stacked_blobs,
      'blobs_data': blobs_data,
  }
  return shortcuts.render(request, 'viewer/favorite.html', context)


def ServeTag(request: http.HttpRequest, tag_id: int) -> http.HttpResponse:  # noqa: C901
  """Serve the `tag` page for one `tag_id`."""
  # check for errors in parameters
  db = _DBFactory()
  warning_message: Optional[str] = None
  error_message: Optional[str] = None
  all_tags = [(tid, name, db.PrintableTag(tid)) for tid, name, _, _ in db.TagsWalk()]
  if tag_id:
    if tag_id not in {tid for tid, _, _ in all_tags}:
      raise http.Http404('Unknown tag %d' % tag_id)
    tag_hierarchy = db.GetTag(tag_id)
    page_depth = len(tag_hierarchy)
    tag_obj: fapdata.TAG_OBJ = db.GetTag(tag_id)[-1][-1]
  else:
    page_depth = 0
    tag_obj: fapdata.TAG_OBJ = {'name': 'root', 'tags': db.tags}  # "dummy" root tag (has real data)
  # get POST data
  new_tag = request.POST.get('named_child', '').strip()
  delete_tag = int(request.POST.get('delete_input', '0').strip())
  # do we have a new tag to create?
  if new_tag:
    # check if name does not clash with any already existing tag
    for _, n, p in all_tags:
      if new_tag.lower() == n.lower():
        error_message = 'Proposed tag name %r clashes with existing tag %r' % (new_tag, p)
        break
    else:
      # check for invalid chars
      if '/' in new_tag or '\\' in new_tag:
        error_message = 'Don\'t use "/" or "\\" in tag name (tried to create %r)' % (new_tag)
      else:
        # everything OK: add tag
        max_tag = max(i for i, _, _ in all_tags) if all_tags else 0
        tag_obj['tags'][max_tag + 1] = {'name': new_tag, 'tags': {}}  # type: ignore
        db.Save()
  # do we have a tag to delete?
  elif delete_tag:
    # check tag is known
    if delete_tag not in {tid for tid, _, _ in all_tags}:
      error_message = 'Requested deletion of unknown tag %d' % delete_tag
    else:
      delete_obj = db.GetTag(delete_tag)
      # check tag does not have children
      if delete_obj[-1][-1]['tags']:
        error_message = ('Requested deletion of tag %d/%r that is not empty '
                         '(delete children first)' % (delete_tag, delete_obj[-1][1]))
      else:
        # everything OK: do deletion
        if len(delete_obj) < 2:
          # in this case it is a child of root
          del db.tags[delete_tag]
        else:
          # in this case we have a non-root parent
          del delete_obj[-2][-1]['tags'][delete_tag]  # type: ignore
        # we must remove the tags from any images that have it too!
        count_tag_deletions = 0
        for blob in db.blobs.values():
          if delete_tag in blob['tags']:     # type: ignore
            blob['tags'].remove(delete_tag)  # type: ignore
            count_tag_deletions += 1
        # compose message and remember to save DB
        warning_message = 'Tag %d/%r deleted and association removed from %d blobs (images)' % (
            delete_tag, delete_obj[-1][1], count_tag_deletions)
        db.Save()
  # send to page
  context = {
      'tags': [(tid, name, db.PrintableTag(tid), page_depth + depth)
               for tid, name, depth, _ in db.TagsWalk(start_tag=tag_obj['tags'])],  # type: ignore
      'tag_id': tag_id,
      'page_depth': page_depth,
      'page_depth_up': (page_depth - 1) if page_depth else 0,
      'tag_name': db.PrintableTag(tag_id) if tag_id else None,
      'warning_message': warning_message,
      'error_message': error_message,
  }
  return shortcuts.render(request, 'viewer/tag.html', context)


# this page seems to be executing TWICE when called, and blobs' binary representations never ever
# change, so it is perfectly acceptable to cache the hell out of this particular page
@cache.cache_page(60 * 60)
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


def ServeDuplicates(request: http.HttpRequest) -> http.HttpResponse:
  """Serve the `duplicates` page."""
  db = _DBFactory()
  sorted_keys = sorted(db.duplicates.index.keys(), key=lambda x: x[0])
  context = {
      'duplicates': {
          k: {
              'size': len(k),
              'action': any(st == 'new' for st in db.duplicates.index[k].values()),
          }
          for k in sorted_keys
      },
      'dup_action': sum(1 for d in db.duplicates.index.values()
                        if any(st == 'new' for st in d.values())),
      'dup_count': len(sorted_keys),
      'img_count': sum(len(k) for k in sorted_keys),
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
                      'imagefap': fapdata.IMG_URL(i),
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
  return shortcuts.render(request, 'viewer/duplicate.html', context)
