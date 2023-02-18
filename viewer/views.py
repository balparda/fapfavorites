"""Create your views here."""

import functools
import logging
# import pdb
import statistics
from typing import Any, Optional

from django import http
from django import shortcuts
from django import conf
from django.views.decorators import cache
from django.utils import safestring
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

_VERDICT_ABBREVIATION: dict[duplicates.DuplicatesVerdictType, str] = {
    'new': 'N',
    'false': 'F',
    'keep': 'K',
    'skip': 'S',
}


@defaulttags.register.filter(name='lookup')
def lookup(value: dict, arg: Any) -> Any:
  """Lookup dictionary (so we can use it in the templates)."""
  return value[arg]


@defaulttags.register.filter(name='green_scale')
def green_scale(score: str) -> str:
  """Convert a float string score ('0.0' to '10.0') to a green scale '0' to '200'."""
  return str(int(float(score) * 20.0))


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
  context: dict[str, Any] = {
      'users': len(db.users),
      'tags': len(tuple(db.TagsWalk())),
      'duplicates': len(db.duplicates.registry),
      'dup_action': sum(1 for d in db.duplicates.registry.values()
                        if any(st == 'new' for st in d['verdicts'].values())),
      'n_images': len(db.blobs),
      'database_stats': db.PrintStats(actually_print=False),
  }
  return shortcuts.render(request, 'viewer/index.html', context)


def ServeUsers(request: http.HttpRequest) -> http.HttpResponse:
  """Serve the `users` page."""
  db = _DBFactory()
  warning_message: Optional[str] = None
  error_message: Optional[str] = None
  # get POST data
  delete_user_id = int(request.POST.get('delete_input', '0').strip())
  # do we have a favorites album to delete?
  if delete_user_id:
    # check user is known
    if delete_user_id not in db.users:
      error_message = 'Requested deletion of unknown user %d' % delete_user_id
    else:
      delete_count, duplicates_count = db.DeleteUserAndAlbums(delete_user_id)
      # compose message and remember to save DB
      warning_message = (
          'User %s deleted, and with them %d blobs (images) deleted, '
          'together with their thumbnails, plus %d duplicates groups abandoned' % (
              db.UserStr(delete_user_id), delete_count, duplicates_count))
      db.Save()
  # make user sums and data
  users: dict[int, dict[str, Any]] = {}
  total_sz: int = 0
  total_img: int = 0
  total_animated: int = 0
  total_thumbs: int = 0
  total_failed: int = 0
  for uid, user in db.users.items():
    file_sizes: list[int] = [
        db.blobs[db.image_ids_index[i]]['sz']
        for f in db.favorites.get(uid, {}).values()
        for i in f['images'] if i in db.image_ids_index]
    thumbs_sizes: list[int] = [
        db.blobs[db.image_ids_index[i]]['sz_thumb']
        for f in db.favorites.get(uid, {}).values()
        for i in f['images'] if i in db.image_ids_index]
    n_animated = sum(
        bool(db.blobs[db.image_ids_index[i]]['animated'])
        for f in db.favorites.get(uid, {}).values()
        for i in f['images'] if i in db.image_ids_index)
    unique_failed: set[int] = set()
    for failed in (f['failed_images'] for f in db.favorites.get(uid, {}).values()):
      unique_failed.update(img for img, _, _, _ in failed)
    n_img = len(file_sizes)
    users[uid] = {
        'name': user['name'],
        'date_albums': base.STD_TIME_STRING(user['date_albums']),
        'date_finished': base.STD_TIME_STRING(user['date_finished']),
        'n_img': n_img,
        'n_failed': len(unique_failed),
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
    total_failed += len(unique_failed)
    total_animated += n_animated
    total_sz += sum(file_sizes) if file_sizes else 0
    total_thumbs += sum(thumbs_sizes) if file_sizes else 0
  # send to page
  context: dict[str, Any] = {
      'users': users,
      'user_count': len(users),
      'total_img': total_img,
      'total_failed': total_failed,
      'total_animated': '%d (%0.1f%%)' % (
          total_animated, (100.0 * total_animated / total_img) if total_img else 0.0),
      'total_sz': base.HumanizedBytes(total_sz) if total_sz else '-',
      'total_thumbs': base.HumanizedBytes(total_thumbs) if total_thumbs else '-',
      'total_file_storage': base.HumanizedBytes(
          total_sz + total_thumbs) if (total_sz + total_thumbs) else '-',
      'warning_message': warning_message,
      'error_message': error_message,
  }
  return shortcuts.render(request, 'viewer/users.html', context)


def ServeFavorites(request: http.HttpRequest, user_id: int) -> http.HttpResponse:
  """Serve the `favorites` page of one `user_id`."""
  # check for errors in parameters
  db = _DBFactory()
  warning_message: Optional[str] = None
  error_message: Optional[str] = None
  if user_id not in db.users or user_id not in db.favorites:
    raise http.Http404('Unknown user %d' % user_id)
  user_favorites = db.favorites[user_id]
  # get POST data
  delete_album_id = int(request.POST.get('delete_input', '0').strip())
  # do we have a favorites album to delete?
  if delete_album_id:
    # check album is known
    if delete_album_id not in user_favorites:
      error_message = 'Requested deletion of unknown favorites album %d' % delete_album_id
    else:
      delete_count, duplicates_count = db.DeleteAlbum(user_id, delete_album_id)
      # compose message and remember to save DB
      warning_message = (
          'Favorites album %s deleted, and with it %d blobs (images) deleted, '
          'together with their thumbnails, plus %d duplicates groups abandoned' % (
              db.AlbumStr(user_id, delete_album_id), delete_count, duplicates_count))
      db.Save()
  # sort albums alphabetically and format data
  names = sorted(((fid, obj['name']) for fid, obj in user_favorites.items()), key=lambda x: x[1])
  favorites: dict[int, dict[str, Any]] = {}
  total_failed: int = 0
  total_sz: int = 0
  total_thumbs_sz: int = 0
  total_animated: int = 0
  for fid, name in names:
    obj = db.favorites[user_id][fid]
    count_img = len(obj['images'])
    count_failed = len(obj['failed_images'])
    file_sizes: list[int] = [
        db.blobs[db.image_ids_index[i]]['sz']
        for i in obj['images'] if i in db.image_ids_index]
    thumbs_sizes: list[int] = [
        db.blobs[db.image_ids_index[i]]['sz_thumb']
        for i in obj['images'] if i in db.image_ids_index]
    n_animated = sum(
        int(db.blobs[db.image_ids_index[i]]['animated'])
        for i in obj['images'] if i in db.image_ids_index)
    favorites[fid] = {
        'name': name,
        'pages': obj['pages'],
        'date': base.STD_TIME_STRING(obj['date_blobs']),
        'count': count_img,
        'failed': count_failed,
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
    total_failed += count_failed
    total_sz += sum(file_sizes) if file_sizes else 0
    total_thumbs_sz += sum(thumbs_sizes) if thumbs_sizes else 0
    total_animated += n_animated
  # send to page
  all_img_count = sum(f['count'] for f in favorites.values())
  context: dict[str, Any] = {
      'user_id': user_id,
      'user_name': db.users[user_id]['name'],
      'date_albums': base.STD_TIME_STRING(db.users[user_id]['date_albums']),
      'date_finished': base.STD_TIME_STRING(db.users[user_id]['date_finished']),
      'favorites': favorites,
      'album_count': len(names),
      'img_count': all_img_count,
      'failed_count': total_failed,
      'page_count': sum(f['pages'] for f in favorites.values()),
      'total_sz': base.HumanizedBytes(total_sz) if total_sz else '-',
      'total_thumbs_sz': base.HumanizedBytes(total_thumbs_sz) if total_thumbs_sz else '-',
      'total_file_storage': base.HumanizedBytes(
          total_sz + total_thumbs_sz) if (total_sz + total_thumbs_sz) else '-',
      'total_animated': '%d (%0.1f%%)' % (
          total_animated, (100.0 * total_animated / all_img_count) if all_img_count else 0.0),
      'warning_message': warning_message,
      'error_message': error_message,
  }
  return shortcuts.render(request, 'viewer/favorites.html', context)


def ServeFavorite(  # noqa: C901
    request: http.HttpRequest, user_id: int, folder_id: int) -> http.HttpResponse:
  """Serve the `favorite` (album) page for an `user_id` and a `folder_id`."""
  # check for errors in parameters
  db = _DBFactory()
  warning_message: Optional[str] = None
  error_message: Optional[str] = None
  if user_id not in db.users or user_id not in db.favorites:
    raise http.Http404('Unknown user %d' % user_id)
  if folder_id not in db.favorites[user_id]:
    raise http.Http404('Unknown folder %d (in known user %d)' % (folder_id, user_id))
  # do we have to save tags?
  selected_tag = int(request.POST.get('tag_select', '0'))
  selected_images = {
      sha.strip().lower()
      for sha in request.POST.get('selected_blobs', '').split(',') if sha.strip()}
  if selected_tag and selected_images:
    # we have tags to apply; check tag validity
    try:
      tag_name = db.TagLineageStr(selected_tag)
    except fapdata.Error:
      error_message = 'Unknown tag %d requested' % selected_tag
    else:
      # tag is OK; add the tags
      tag_count: int = 0
      for sha in selected_images:
        # check if image is valid
        if sha not in db.blobs:
          error_message = 'Unknown image %r requested' % sha
          break
        # add tag to image
        db.blobs[sha]['tags'].add(selected_tag)
        tag_count += 1
      else:
        warning_message = '%d images tagged with %s' % (tag_count, tag_name)
        db.Save()
  # retrieve the `GET` data
  show_duplicates = bool(int(request.GET.get('dup', '0')))        # default: False
  show_portraits = bool(int(request.GET.get('portrait', '1')))    # default: True
  show_landscapes = bool(int(request.GET.get('landscape', '1')))  # default: True
  locked_for_tagging = bool(int(request.GET.get('lock', '0')))    # default: False
  # get images in album
  favorite = db.favorites[user_id][folder_id]
  images: list[int] = favorite['images']
  sorted_blobs = [(i, db.image_ids_index[i])  # "sorted" here means original order!
                  for i in images if i in db.image_ids_index]  # check existence: partial downloads
  # find images that have duplicates
  exact_duplicates: dict[tuple[int, str], set[fapdata.LocationTupleType]] = {}
  album_duplicates: dict[tuple[int, str], set[fapdata.LocationTupleType]] = {}
  percept_verdicts: dict[tuple[int, str], duplicates.DuplicatesVerdictType] = {}
  percept_duplicates: dict[tuple[int, str], set[fapdata.LocationTupleType]] = {}
  dup_hints: dict[tuple[int, str], list[str]] = {}  # the hints (mouse-over text) for the duplicates
  for img, sha in sorted_blobs:
    # collect images with identical twins
    if len(db.blobs[sha]['loc']) > 1:
      exact_duplicates[(img, sha)] = db.blobs[sha]['loc']
      hits: set[fapdata.LocationTupleType] = {
          loc for loc in db.blobs[sha]['loc'] if loc[3] == user_id and loc[4] == folder_id}
      if len(hits) > 1:
        # this image has twins in this same album
        album_duplicates[(img, sha)] = hits
    # look in perceptual index if this image is marked as 'new'/'keep'/'skip' (!='false')
    if sha in db.duplicates.index:
      dup_keys = db.duplicates.index[sha]
      verdict = db.duplicates.registry[dup_keys]['verdicts'][sha]
      if verdict != 'false':
        percept_verdicts[(img, sha)] = verdict
        # also collect the locations where we can find the perceptual duplicates
        for dup_key in (
            k for k in dup_keys if db.duplicates.registry[dup_keys]['verdicts'][k] != 'false'):
          percept_duplicates.setdefault((img, sha), set()).update(db.blobs[dup_key]['loc'])
    # make the hints
    for loc in exact_duplicates.get((img, sha), set()):
      is_current = loc[0] == img and loc[3] == user_id and loc[4] == folder_id
      dup_hints.setdefault((img, sha), []).append(
          'Exact: %s%s' % (db.LocationStr(loc), ' <= THIS' if is_current else ''))
    for loc in percept_duplicates.get((img, sha), set()):
      is_current = loc[0] == img and loc[3] == user_id and loc[4] == folder_id
      dup_hints.setdefault((img, sha), []).append(
          'Visual: %s%s' % (db.LocationStr(loc), ' <= THIS' if is_current else ''))
    if (img, sha) in dup_hints and dup_hints[(img, sha)]:
      dup_hints[(img, sha)].sort()
  # apply filters
  if not show_duplicates:
    sorted_blobs = [(img, sha) for img, sha in sorted_blobs
                    if not ((img, sha) in album_duplicates and
                            img != min(n[0] for n in album_duplicates[(img, sha)]))]
    sorted_blobs = [(img, sha) for img, sha in sorted_blobs
                    if not ((img, sha) in percept_verdicts and
                            percept_verdicts[(img, sha)] == 'skip')]
  if not show_portraits:
    sorted_blobs = [(img, sha) for img, sha in sorted_blobs
                    if not (db.blobs[sha]['height'] / db.blobs[sha]['width'] > 1.1)]
  if not show_landscapes:
    sorted_blobs = [(img, sha) for img, sha in sorted_blobs
                    if not (db.blobs[sha]['width'] / db.blobs[sha]['height'] > 1.1)]
  # stack the hashes in rows of _IMG_COLUMNS columns
  stacked_blobs = [sorted_blobs[i:(i + _IMG_COLUMNS)]
                   for i in range(0, len(sorted_blobs), _IMG_COLUMNS)]
  if stacked_blobs:
    stacked_blobs[-1] += [(0, '') for i in range(_IMG_COLUMNS - len(stacked_blobs[-1]))]
  # format blob data to be included as auxiliary data
  blobs_data: dict[str, dict[str, Any]] = {}
  for img, sha in sorted_blobs:
    blob = db.blobs[sha]
    # find the correct 'loc' entry (to get the name)
    for i, _, name, uid, fid in blob['loc']:
      if i == img and uid == user_id and fid == folder_id:
        break
    else:
      logging.error('Blob %r in %s did not have a matching `loc` entry!',
                    sha, db.AlbumStr(user_id, folder_id))
      continue  # might raise an exception here, but this can happen in partially downloaded albums
    # fill in the other fields, make them readable
    blobs_data[sha] = {
        'name': name,
        'sz': base.HumanizedBytes(blob['sz']),
        'dimensions': '%dx%d (WxH)' % (blob['width'], blob['height']),
        'tags': ', '.join(sorted(db.TagLineageStr(t, add_id=False) for t in blob['tags'])),
        'thumb': '%s.%s' % (sha, blob['ext']),  # this is just the file name, to be served as
                                                # a static resource: see settings.py
        'has_duplicate': (img, sha) in exact_duplicates,
        'album_duplicate': (img, sha) in album_duplicates,
        'has_percept': (img, sha) in percept_verdicts,
        'imagefap': fapdata.IMG_URL(img),
        'duplicate_hints': (
            '\n'.join(dup_hints[(img, sha)])
            if (img, sha) in dup_hints and dup_hints[(img, sha)] else ''),
    }
  # send to page
  context: dict[str, Any] = {
      'user_id': user_id,
      'user_name': db.users[user_id]['name'],
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
      'tags': [(tid, name, db.TagLineageStr(tid)) for tid, name, _, _ in db.TagsWalk()],
      'failed_count': len(favorite['failed_images']),
      'failed_data': [
          {
              'id': img,
              'img_page': fapdata.IMG_URL(img),
              'time': base.STD_TIME_STRING(tm),
              'name': '-' if nm is None else nm,
              'url': url,
          } for img, tm, nm, url in sorted(favorite['failed_images'])
      ] if favorite['failed_images'] else None,
      'warning_message': warning_message,
      'error_message': error_message,
  }
  return shortcuts.render(request, 'viewer/favorite.html', context)


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
  ext = blob['ext'].lower()
  if ext not in _IMAGE_TYPES:
    raise http.Http404('Blob %r image type (file extension) %r not one of %r' % (
        digest, ext, sorted(_IMAGE_TYPES.keys())))
  # send to page
  return http.HttpResponse(content=db.GetBlob(digest), content_type=_IMAGE_TYPES[ext])


def ServeTag(request: http.HttpRequest, tag_id: int) -> http.HttpResponse:  # noqa: C901
  """Serve the `tag` page for one `tag_id`."""
  # check for errors in parameters
  db = _DBFactory()
  warning_message: Optional[str] = None
  error_message: Optional[str] = None
  all_tags = [(tid, name, db.TagLineageStr(tid)) for tid, name, _, _ in db.TagsWalk()]
  if tag_id:
    if tag_id not in {tid for tid, _, _ in all_tags}:
      raise http.Http404('Unknown tag %d' % tag_id)
    tag_hierarchy = db.GetTag(tag_id)
    page_depth: int = len(tag_hierarchy)
    tag_obj: fapdata.TagObjType = db.GetTag(tag_id)[-1][-1]
  else:
    page_depth: int = 0
    tag_obj: fapdata.TagObjType = {
        'name': 'root', 'tags': db.tags}  # "dummy" root tag (has real data) # type: ignore
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
        tag_obj['tags'][max_tag + 1] = {'name': new_tag, 'tags': {}}
        # message and save DB
        warning_message = 'Tag %d/%s created' % (max_tag + 1, new_tag)
        db.Save()
  # do we have a tag to delete?
  elif delete_tag:
    # check tag is known
    if delete_tag not in {tid for tid, _, _ in all_tags}:
      error_message = 'Requested deletion of unknown tag %d' % delete_tag
    else:
      delete_obj = db.GetTag(delete_tag)
      delete_name = db.TagLineageStr(delete_tag)
      # check tag does not have children
      if delete_obj[-1][-1]['tags']:
        error_message = ('Requested deletion of tag %s that is not empty '
                         '(delete children first)' % delete_name)
      else:
        # everything OK: do deletion
        if len(delete_obj) < 2:
          # in this case it is a child of root
          del db.tags[delete_tag]
        else:
          # in this case we have a non-root parent
          del delete_obj[-2][-1]['tags'][delete_tag]
        # we must remove the tags from any images that have it too!
        count_tag_deletions: int = 0
        for blob in db.blobs.values():
          if delete_tag in blob['tags']:
            blob['tags'].remove(delete_tag)
            count_tag_deletions += 1
        # compose message and remember to save DB
        warning_message = 'Tag %s deleted and association removed from %d blobs (images)' % (
            delete_name, count_tag_deletions)
        db.Save()
  # send to page
  context: dict[str, Any] = {
      'tags': [(tid, name, db.TagLineageStr(tid, add_id=False), page_depth + depth)
               for tid, name, depth, _ in db.TagsWalk(start_tag=tag_obj['tags'])],  # type: ignore
      'tag_id': tag_id,
      'page_depth': page_depth,
      'page_depth_up': (page_depth - 1) if page_depth else 0,
      'tag_name': db.TagLineageStr(tag_id) if tag_id else None,
      'warning_message': warning_message,
      'error_message': error_message,
  }
  return shortcuts.render(request, 'viewer/tag.html', context)


def _AbbreviatedKey(dup_key: duplicates.DuplicatesKeyType) -> safestring.SafeText:
  """Return an abbreviated HTML representation for the key, each key will show 8 hex bytes."""
  if len(dup_key) == 1:
    return safestring.mark_safe('%s&hellip;' % dup_key[0][:16])  # cspell:disable-line # nosec
  else:
    return safestring.mark_safe(  # nosec
        '(%s)' % ', '.join('%s&hellip;' % sha[:16] for sha in dup_key))  # cspell:disable-line


def ServeDuplicates(request: http.HttpRequest) -> http.HttpResponse:
  """Serve the `duplicates` page."""
  db = _DBFactory()
  sorted_keys = sorted(db.duplicates.registry.keys())
  # send to page
  img_count = sum(len(dup_key) for dup_key in sorted_keys)
  new_count = sum(
      1 for dup_obj in db.duplicates.registry.values()
      for st in dup_obj['verdicts'].values() if st == 'new')
  false_count = sum(
      1 for dup_obj in db.duplicates.registry.values()
      for st in dup_obj['verdicts'].values() if st == 'false')
  keep_count = sum(
      1 for dup_obj in db.duplicates.registry.values()
      for st in dup_obj['verdicts'].values() if st == 'keep')
  skip_count = sum(
      1 for dup_obj in db.duplicates.registry.values()
      for st in dup_obj['verdicts'].values() if st == 'skip')
  context: dict[str, Any] = {
      'duplicates': {
          dup_key: {
              'name': _AbbreviatedKey(dup_key),
              'size': len(dup_key),
              'action': any(
                  st == 'new' for st in db.duplicates.registry[dup_key]['verdicts'].values()),
              'verdicts': ' / '.join(
                  _VERDICT_ABBREVIATION[
                      db.duplicates.registry[dup_key]['verdicts'][sha]] for sha in dup_key),
          }
          for dup_key in sorted_keys
      },
      'dup_action': sum(1 for dup_obj in db.duplicates.registry.values()
                        if any(st == 'new' for st in dup_obj['verdicts'].values())),
      'dup_count': len(sorted_keys),
      'img_count': img_count,
      'new_count': '%d (%0.1f%%)' % (
          new_count, (100.0 * new_count) / img_count) if img_count else '-',
      'false_count': '%d (%0.1f%%)' % (
          false_count, (100.0 * false_count) / img_count) if img_count else '-',
      'keep_count': '%d (%0.1f%%)' % (
          keep_count, (100.0 * keep_count) / img_count) if img_count else '-',
      'skip_count': '%d (%0.1f%%)' % (
          skip_count, (100.0 * skip_count) / img_count) if img_count else '-',
  }
  return shortcuts.render(request, 'viewer/duplicates.html', context)


def _NormalizeHashScore(method: duplicates.DuplicatesHashType, value: int) -> float:
  """Return score as a 0.0 to 10.0 range."""
  max_value: int = duplicates.METHOD_SENSITIVITY[method]  # type: ignore
  return (max_value - value) * (10.0 / max_value)


def _NormalizeCosineScore(method: duplicates.DuplicatesHashType, value: float) -> float:
  """Return score as a 0.0 to 10.0 range."""
  min_value: float = duplicates.METHOD_SENSITIVITY[method]
  return (value - min_value) * (10.0 / (1.0 - min_value))


def ServeDuplicate(request: http.HttpRequest, digest: str) -> http.HttpResponse:
  """Serve the `duplicate` page, with a set of duplicates, by giving one of the SHA256 `digest`."""
  # check for errors in parameters
  db = _DBFactory()
  error_message: Optional[str] = None
  if digest not in db.blobs:
    raise http.Http404('Unknown blob %r' % digest)
  sorted_keys = sorted(db.duplicates.registry.keys())
  dup_obj: Optional[duplicates.DuplicateObjType] = None
  if digest in db.duplicates.index:
    # this is a perceptual set, so get the object and its index in sorted_keys
    dup_key: duplicates.DuplicatesKeyType = db.duplicates.index[digest]
    dup_obj = db.duplicates.registry[dup_key]
    current_index = sorted_keys.index(dup_key)
  else:
    # not a perceptual set, so maybe it is a direct hash collision
    if len(db.blobs[digest]['loc']) <= 1:
      raise http.Http404(
          'Blob %r does not correspond to a duplicate set or hash collision' % digest)
    # it is a hash collision, so use digest as `dup_key`, and flag `current_index` with -1 value
    dup_key: duplicates.DuplicatesKeyType = (digest,)
    current_index: int = -1
  # get user selected choice, if any and update database
  if request.POST:
    if not dup_obj:
      raise http.Http404('Trying to POST data on hash collision %r (not perceptual dup)' % digest)
    for sha in dup_key:
      # check that the selection is valid
      if sha not in request.POST:
        error_message = 'Expected key %r in POST data, but didn\'t find it!' % sha
        break
      selected_option: duplicates.DuplicatesVerdictType = request.POST[sha]  # type: ignore
      if selected_option not in duplicates.DUPLICATE_OPTIONS:
        error_message = 'Key %r in POST data has invalid option %r!' % (sha, selected_option)
        break
      # set data in DB structure
      dup_obj['verdicts'][sha] = selected_option
    else:
      # everything went smoothly (no break action above), so save the data
      db.Save()
  # send to page
  context: dict[str, Any] = {
      'digest': digest,
      'dup_key': _AbbreviatedKey(dup_key),
      'current_index': current_index,  # can be -1 if indexing is disabled! (hard hash collision)
      'previous_key': sorted_keys[current_index - 1] if current_index > 0 else None,
      'next_key': (sorted_keys[current_index + 1]
                   if -1 < current_index < (len(sorted_keys) - 1) else None),
      'duplicates': {
          sha: {
              'action': dup_obj['verdicts'][sha] if dup_obj else '',
              'loc': [
                  {
                      'fap_id': i,
                      'file_name': nm,
                      'user_id': uid,
                      'user_name': db.users[uid]['name'],
                      'folder_id': fid,
                      'folder_name': db.favorites[uid][fid]['name'],
                      'imagefap': fapdata.IMG_URL(i),
                  }
                  for i, _, nm, uid, fid in sorted(
                      (loc for loc in db.blobs[sha]['loc']), key=lambda x: (x[0], x[3], x[4]))
              ],
              'sz': base.HumanizedBytes(db.blobs[sha]['sz']),
              'dimensions': '%dx%d (WxH)' % (db.blobs[sha]['width'], db.blobs[sha]['height']),
              'tags': ', '.join(sorted(db.TagLineageStr(t) for t in db.blobs[sha]['tags'])),
              'thumb': '%s.%s' % (sha, db.blobs[sha]['ext']),  # this is just the file name, served
                                                               # as a static resource (settings.py)
              'percept': db.blobs[sha]['percept'],
              'average': db.blobs[sha]['average'],
              'diff': db.blobs[sha]['diff'],
              'wavelet': db.blobs[sha]['wavelet'],
          }
          for sha in dup_key
      },
      'sources': [
          {
              'name': method.upper(),
              'scores': [
                  {
                      'key1': _AbbreviatedKey((dup_key[0],)),
                      'key2': _AbbreviatedKey((dup_key[1],)),
                      'value': (
                          '%0.3f' % dup_obj['sources'][method][dup_key] if method == 'cnn' else
                          '%d' % dup_obj['sources'][method][dup_key]),
                      'normalized_value': (
                          '%0.1f' % _NormalizeCosineScore(
                              method, dup_obj['sources'][method][dup_key])
                          if method == 'cnn' else
                          '%0.1f' % _NormalizeHashScore(
                              method, dup_obj['sources'][method][dup_key])),  # type:ignore
                      'sha1': dup_key[0],
                      'sha2': dup_key[1],
                      'thumb1': '%s.%s' % (dup_key[0], db.blobs[dup_key[0]]['ext']),
                      'thumb2': '%s.%s' % (dup_key[1], db.blobs[dup_key[1]]['ext']),
                  } for dup_key in sorted(dup_obj['sources'][method].keys())
              ]
          } for method in sorted(dup_obj['sources'].keys())
      ] if dup_obj else [],
      'error_message': error_message,
  }
  return shortcuts.render(request, 'viewer/duplicate.html', context)
