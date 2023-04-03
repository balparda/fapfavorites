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
from fapfavorites import duplicates
from fapfavorites import fapdata


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
def lookup(value: dict, arg: Any) -> Any:  # pylint: disable=invalid-name
  """Lookup dictionary (so we can use it in the templates)."""
  return value[arg]


@defaulttags.register.filter(name='green_scale')
def green_scale(score: str) -> str:  # pylint: disable=invalid-name
  """Convert a float string score ('0.0' to '10.0') to a green scale '0' to '200'."""
  return str(int(float(score) * 20.0))


class SHA256HexDigest:
  """Django path converter for a SHA256 hexadecimal digest (exactly 64 chars of hexadecimal)."""

  regex = r'[0-9a-fA-F]{64}'  # 64 chars of lower or upper-case hexadecimal

  def to_python(self, value: str) -> str:  # pylint: disable=invalid-name
    """Convert from URL to (python) type."""
    return value.lower()

  def to_url(self, value: str) -> str:  # pylint: disable=invalid-name
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
  database = fapdata.FapDatabase(db_path, create_if_needed=False)
  if not database.Load():
    raise fapdata.Error('Database does not exist. First create one with `favorites.py`.')
  if not database.blobs_dir_exists or not database.thumbs_dir_exists:
    raise fapdata.Error('Database blobs and/or thumbs directories not found!')
  return database


def _DBFactory() -> fapdata.FapDatabase:
  """Get a loaded database (convenience method)."""
  return _GetLoadedDatabase(
      conf.settings.IMAGEFAP_FAVORITES_DB_PATH,
      fapdata.GetDatabaseTimestamp(conf.settings.IMAGEFAP_FAVORITES_DB_PATH))


def ServeIndex(request: http.HttpRequest) -> http.HttpResponse:
  """Serve the `index` page."""
  db = _DBFactory()  # pylint: disable=invalid-name
  context: dict[str, Any] = {
      'users': len(db.users),
      'tags': len(tuple(db.TagsWalk())),
      'duplicates': len(db.duplicates.registry),
      'dup_action': sum(1 for d in db.duplicates.registry.values()
                        if any(st == 'new' for st in d['verdicts'].values())),
      'n_images': len(db.blobs),
      'identical': sum(1 for b in db.blobs.values() if len(b['loc']) > 1),
      'id_action': sum(1 for b in db.blobs.values()
                       if len(b['loc']) > 1 and any(v[1] == 'new' for v in b['loc'].values())),
      'database_stats': db.PrintStats(actually_print=False),
  }
  return shortcuts.render(request, 'viewer/index.html', context)


def ServeUsers(request: http.HttpRequest) -> http.HttpResponse:
  """Serve the `users` page."""
  db = _DBFactory()  # pylint: disable=invalid-name
  warning_message: Optional[str] = None
  error_message: Optional[str] = None
  # get POST data
  delete_user_id = int(request.POST.get('delete_input', '0').strip())
  # do we have a favorites album to delete?
  if delete_user_id:
    # check user is known
    if delete_user_id not in db.users:
      error_message = f'Requested deletion of unknown user {delete_user_id}'
    else:
      delete_user_name = db.UserStr(delete_user_id)
      delete_count, duplicates_count = db.DeleteUserAndAlbums(delete_user_id)
      # compose message and remember to save DB
      warning_message = (
          f'User {delete_user_name} deleted, and with them {delete_count} blobs (images) deleted, '
          f'together with their thumbnails, plus {duplicates_count} duplicates groups abandoned')
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
        'date_audit': base.STD_TIME_STRING(user['date_audit']),
        'n_img': n_img,
        'n_failed': len(unique_failed),
        'n_animated': f'{n_animated} ({(100.0 * n_animated / n_img) if n_img else 0.0:0.1f}%)',
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
      'total_animated': (f'{total_animated} '
                         f'({(100.0 * total_animated / total_img) if total_img else 0.0:0.1f}%)'),
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
  db = _DBFactory()  # pylint: disable=invalid-name
  warning_message: Optional[str] = None
  error_message: Optional[str] = None
  if user_id not in db.users or user_id not in db.favorites:
    raise http.Http404(f'Unknown user {user_id}')
  user_favorites = db.favorites[user_id]
  # get POST data
  delete_album_id = int(request.POST.get('delete_input', '0').strip())
  # do we have a favorites album to delete?
  if delete_album_id:
    # check album is known
    if delete_album_id not in user_favorites:
      error_message = f'Requested deletion of unknown favorites album {delete_album_id}'
    else:
      delete_album_name = db.AlbumStr(user_id, delete_album_id)
      delete_count, duplicates_count = db.DeleteAlbum(user_id, delete_album_id)
      # compose message and remember to save DB
      warning_message = (
          f'Favorites album {delete_album_name} deleted, and with it {delete_count} blobs (images) '
          f'deleted, together with their thumbnails, plus {duplicates_count} duplicates '
          'groups abandoned')
      db.Save()
  # sort albums alphabetically and format data
  names = sorted(((fid, obj['name']) for fid, obj in user_favorites.items()), key=lambda x: x[1])
  favorites: dict[int, dict[str, Any]] = {}
  total_failed: int = 0
  total_disappeared: int = 0
  total_sz: int = 0
  total_thumbs_sz: int = 0
  total_animated: int = 0
  for fid, name in names:
    obj = db.favorites[user_id][fid]
    count_img = len(obj['images'])
    count_failed = len(obj['failed_images'])
    count_disappeared = sum(
        1 for i in obj['images']
        if i in db.image_ids_index if db.blobs[db.image_ids_index[i]]['gone'])
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
        'disappeared': (f'{count_disappeared} '
                        f'({(100.0 * count_disappeared / count_img) if count_img else 0.0:0.1f}%)'),
        'files_sz': base.HumanizedBytes(sum(file_sizes) if file_sizes else 0),
        'min_sz': base.HumanizedBytes(min(file_sizes)) if file_sizes else '-',
        'max_sz': base.HumanizedBytes(max(file_sizes)) if file_sizes else '-',
        'mean_sz': base.HumanizedBytes(int(statistics.mean(file_sizes))) if file_sizes else '-',
        'dev_sz': base.HumanizedBytes(
            int(statistics.stdev(file_sizes))) if len(file_sizes) > 2 else '-',
        'thumbs_sz': base.HumanizedBytes(sum(thumbs_sizes) if thumbs_sizes else 0),
        'n_animated': (f'{n_animated} '
                       f'({(100.0 * n_animated / count_img) if count_img else 0.0:0.1f}%)'),
    }
    total_failed += count_failed
    total_disappeared += count_disappeared
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
      'date_audit': base.STD_TIME_STRING(db.users[user_id]['date_audit']),
      'favorites': favorites,
      'album_count': len(names),
      'img_count': all_img_count,
      'failed_count': total_failed,
      'disappeared_count': (
          f'{total_disappeared} '
          f'({(100.0 * total_disappeared / all_img_count) if all_img_count else 0.0:0.1f}%)'),
      'page_count': sum(f['pages'] for f in favorites.values()),
      'total_sz': base.HumanizedBytes(total_sz) if total_sz else '-',
      'total_thumbs_sz': base.HumanizedBytes(total_thumbs_sz) if total_thumbs_sz else '-',
      'total_file_storage': base.HumanizedBytes(
          total_sz + total_thumbs_sz) if (total_sz + total_thumbs_sz) else '-',
      'total_animated': (
          f'{total_animated} '
          f'({(100.0 * total_animated / all_img_count) if all_img_count else 0.0:0.1f}%)'),
      'warning_message': warning_message,
      'error_message': error_message,
  }
  return shortcuts.render(request, 'viewer/favorites.html', context)


def _ServeImages(  # noqa: C901
    request: http.HttpRequest,
    db: fapdata.FapDatabase,  # pylint: disable=invalid-name
    image_list: list[tuple[int, str]],
    user_id: int,
    folder_id: int) -> dict[str, Any]:
  """Create context for page that serves a group of images and can set tags to them.

  The objective here is to be able to serve both the favorite.html & tag.html pages.
  Will *not* save the DB, for safety: will rely on caller to do so if 'warning_message'
  is not None.

  Args:
    request: HttpRequest object
    db: initialized fapdata.FapDatabase object
    image_list: ordered list of (img_id, sha), where img_id will be the album image ID for
        favorite pages and will be zero (0) for tag pages
    user_id: User ID if in album, or zero (0) if in tag
    folder_id: Folder ID if in album, or zero (0) if in tag

  Returns:
    context dict
  """
  # TODO: better filtering with tri-state for options: only/allow/filter, i.e., yes/don't-care/no
  # TODO: actually filter on identical verdicts
  warning_message: Optional[str] = None
  error_message: Optional[str] = None
  # do we have to save tags?
  selected_tag = int(request.POST.get('tag_select', '0'))
  clear_tag = int(request.POST.get('clear_tag', '0'))
  selected_images = {
      sha.strip().lower()
      for sha in request.POST.get('selected_blobs', '').split(',') if sha.strip()}
  if selected_tag and selected_images:
    # we have tags to apply; check tag validity
    try:
      tag_name = db.TagLineageStr(selected_tag)
    except fapdata.Error:
      error_message = f'Unknown tag {selected_tag} addition requested'
    else:
      # tag is OK; add the tags
      for sha in selected_images:
        # check if image is valid
        if sha not in db.blobs:
          error_message = f'Unknown image {sha!r} tagging requested'
          break
        # add tag to image
        db.blobs[sha]['tags'].add(selected_tag)
      else:
        # setting this message should trigger a DB Save() in the calling page
        warning_message = f'{len(selected_images)} images tagged with {tag_name}'
  if clear_tag and selected_images:
    # we have tags to delete; check tag validity
    try:
      tag_name = db.TagLineageStr(clear_tag)
      # get the tag plus all below it
      tag_child_ids = {i for i, _, _, _ in db.TagsWalk(
          start_tag=db.GetTag(clear_tag)[-1][-1]['tags'])}  # type: ignore
      tag_child_ids.add(clear_tag)
    except fapdata.Error:
      error_message = f'Unknown tag {clear_tag} removal requested'
    else:
      # tag is OK; remove the tags
      for sha in selected_images:
        # check if image is valid, has the tag, and the image is on image_list
        if sha not in db.blobs:
          error_message = f'Unknown image {sha!r} tag clearing requested'
          break
        if (0, sha) not in image_list:  # (0, foo) because for now this can only come from tag page
          error_message = f'Image {sha!r} expected in image list and not found'
          break
        tags_to_remove = tag_child_ids.intersection(db.blobs[sha]['tags'])
        if not tags_to_remove:
          error_message = f'Image {sha!r} does not have tag {tag_name} (or any of its children)'
          break
        # remove tag(s) from image and image from list so we don't serve it
        for tag_id in tags_to_remove:
          db.blobs[sha]['tags'].remove(tag_id)
        image_list.remove((0, sha))
      else:
        # setting this message should trigger a DB Save() in the calling page
        warning_message = f'{len(selected_images)} images had tag {tag_name} cleared'
  # retrieve the `GET` data
  show_duplicates = bool(int(request.GET.get('dup', '0')))        # default: False
  show_portraits = bool(int(request.GET.get('portrait', '1')))    # default: True
  show_landscapes = bool(int(request.GET.get('landscape', '1')))  # default: True
  locked_for_tagging = bool(int(request.GET.get('lock', '0')))    # default: False
  # find images that have duplicates
  exact_duplicates: dict[tuple[int, str], set[fapdata.LocationKeyType]] = {}
  album_duplicates: dict[tuple[int, str], set[fapdata.LocationKeyType]] = {}
  percept_verdicts: dict[tuple[int, str], duplicates.DuplicatesVerdictType] = {}
  percept_duplicates: dict[tuple[int, str], set[fapdata.LocationKeyType]] = {}
  dup_hints: dict[tuple[int, str], list[str]] = {}  # the hints (mouse-over text) for the duplicates
  for img, sha in image_list:
    # collect images with identical twins
    if len(db.blobs[sha]['loc']) > 1:
      exact_duplicates[(img, sha)] = set(db.blobs[sha]['loc'].keys())
      hits: set[fapdata.LocationKeyType] = {
          # reminder: user_id/folder_id can be 0 for tag page
          loc for loc in db.blobs[sha]['loc'].keys() if loc[0] == user_id and loc[1] == folder_id}
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
      # reminder: user_id/folder_id can be 0 for tag page
      is_current = loc == (user_id, folder_id, img)
      dup_hints.setdefault((img, sha), []).append(
          f'Exact: {db.LocationStr(loc, db.blobs[sha]["loc"][loc])}'
          f'{" <= THIS" if is_current else ""}')
    for loc in percept_duplicates.get((img, sha), set()):
      # reminder: user_id/folder_id can be 0 for tag page
      is_current = loc == (user_id, folder_id, img)
      dup_hints.setdefault((img, sha), []).append(
          f'Visual: {db.LocationStr(loc, db.blobs[db.image_ids_index[loc[2]]]["loc"][loc])}'
          f'{" <= THIS" if is_current else ""}')
    if (img, sha) in dup_hints and dup_hints[(img, sha)]:
      dup_hints[(img, sha)].sort()
  # apply filters
  if not show_duplicates:
    image_list = [(img, sha) for img, sha in image_list
                  if not ((img, sha) in album_duplicates and
                          img != min(n[0] for n in album_duplicates[(img, sha)]))]
    image_list = [(img, sha) for img, sha in image_list
                  if not ((img, sha) in percept_verdicts and
                          percept_verdicts[(img, sha)] == 'skip')]
  if not show_portraits:
    image_list = [(img, sha) for img, sha in image_list
                  if not db.blobs[sha]['height'] / db.blobs[sha]['width'] > 1.1]
  if not show_landscapes:
    image_list = [(img, sha) for img, sha in image_list
                  if not db.blobs[sha]['width'] / db.blobs[sha]['height'] > 1.1]
  # stack the hashes in rows of _IMG_COLUMNS columns
  stacked_blobs = [image_list[i:(i + _IMG_COLUMNS)]
                   for i in range(0, len(image_list), _IMG_COLUMNS)]
  if stacked_blobs:
    stacked_blobs[-1] += [(0, '') for i in range(_IMG_COLUMNS - len(stacked_blobs[-1]))]
  # do the same for disappeared images
  disappeared_list = [i for i in image_list if db.blobs[i[1]]['gone']]
  stacked_disappeared = [disappeared_list[i:(i + _IMG_COLUMNS)]
                         for i in range(0, len(disappeared_list), _IMG_COLUMNS)]
  if stacked_disappeared:
    stacked_disappeared[-1] += [(0, '') for i in range(_IMG_COLUMNS - len(stacked_disappeared[-1]))]
  # format blob data to be included as auxiliary data
  blobs_data: dict[str, dict[str, Any]] = {}
  for img, sha in image_list:
    blob = db.blobs[sha]
    # find the correct 'loc' entry (to get the name)
    loc = (user_id, folder_id, img)
    if loc not in blob['loc']:
      if not user_id and not folder_id and blob['loc']:
        # we are serving from the tag page, so we use the first available 'loc'
        loc = sorted(blob['loc'].keys())[0]
      else:
        # we might have raised an exception here, but this can happen in partially downloaded albums
        logging.error('Blob %r in %s did not have a matching `loc` entry!',
                      sha, db.AlbumStr(user_id, folder_id) if user_id and folder_id else '-')
        blobs_data[sha] = {}
        continue
    # fill in the other fields, make them readable
    blobs_data[sha] = {
        'name': blob['loc'][loc][0],
        'verdict': blob['loc'][loc][1],
        'sz': base.HumanizedBytes(blob['sz']),
        'dimensions': f'{blob["width"]}x{blob["height"]} (WxH)',
        'tags': ', '.join(sorted(db.TagLineageStr(t, add_id=False) for t in blob['tags'])),
        'has_duplicate': (img, sha) in exact_duplicates,
        'album_duplicate': (img, sha) in album_duplicates,
        'has_percept': (img, sha) in percept_verdicts,
        'imagefap': fapdata.IMG_URL(img),
        'duplicate_hints': (
            '\n'.join(dup_hints[(img, sha)])
            if (img, sha) in dup_hints and dup_hints[(img, sha)] else ''),
        'date': base.STD_TIME_STRING(blob['date']),
        'gone': [(i, base.STD_TIME_STRING(t[0]), t[1].name) for i, t in blob['gone'].items()],
    }
  # create context
  return {
      'show_duplicates': show_duplicates,
      'dup_url': f'dup={int(show_duplicates)}',
      'show_portraits': show_portraits,
      'portrait_url': f'portrait={int(show_portraits)}',
      'show_landscapes': show_landscapes,
      'landscape_url': f'landscape={int(show_landscapes)}',
      'locked_for_tagging': locked_for_tagging,
      'tagging_url': f'lock={int(locked_for_tagging)}',
      'count': len(image_list),
      'stacked_blobs': stacked_blobs,
      'count_disappeared': len(disappeared_list),
      'stacked_disappeared': stacked_disappeared,
      'blobs_data': blobs_data,
      'form_tags': [(tid, name, db.TagLineageStr(tid, add_id=False))
                    for tid, name, _, _ in db.TagsWalk()],
      'warning_message': warning_message,
      'error_message': error_message,
  }


def ServeFavorite(
    request: http.HttpRequest, user_id: int, folder_id: int) -> http.HttpResponse:
  """Serve the `favorite` (album) page for an `user_id` and a `folder_id`."""
  # TODO: filter by tags
  # check for errors in parameters
  db = _DBFactory()  # pylint: disable=invalid-name
  if user_id not in db.users or user_id not in db.favorites:
    raise http.Http404(f'Unknown user {user_id}')
  if folder_id not in db.favorites[user_id]:
    raise http.Http404(f'Unknown folder {folder_id} (in known user {user_id})')
  # get images in album
  favorite = db.favorites[user_id][folder_id]
  images: list[int] = favorite['images']
  sorted_blobs = [(i, db.image_ids_index[i])  # "sorted" here means original order!
                  for i in images if i in db.image_ids_index]  # check existence: partial downloads
  # get the context for the images
  context = _ServeImages(request, db, sorted_blobs, user_id, folder_id)
  # save database, if needed: having a 'warning_message' means a successful operation somewhere
  if context['warning_message'] is not None:
    db.Save()
  # update with page-specific context and return
  context.update({
      'user_id': user_id,
      'user_name': db.users[user_id]['name'],
      'folder_id': folder_id,
      'name': favorite['name'],
      'pages': favorite['pages'],
      'date': base.STD_TIME_STRING(favorite['date_blobs']),
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
  })
  return shortcuts.render(request, 'viewer/favorite.html', context)


def ServeTag(request: http.HttpRequest, tag_id: int) -> http.HttpResponse:  # noqa: C901
  """Serve the `tag` page for one `tag_id`."""
  # TODO: tag exporter
  # check for errors in parameters
  db = _DBFactory()  # pylint: disable=invalid-name
  all_tags = [(tid, name, db.TagLineageStr(tid)) for tid, name, _, _ in db.TagsWalk()]
  tag_hierarchy: list[tuple[int, str, fapdata.TagObjType]] = []
  sorted_blobs: list[tuple[int, str]] = []
  page_depth: int = 0
  if tag_id:
    # some leaf tag node, check if we know this tag and get it
    if tag_id not in {tid for tid, _, _ in all_tags}:
      raise http.Http404(f'Unknown tag {tag_id}')
    tag_hierarchy = db.GetTag(tag_id)
    page_depth: int = len(tag_hierarchy)
    tag_obj: fapdata.TagObjType = db.GetTag(tag_id)[-1][-1]
    # get the images for this tag and all below it
    tag_child_ids = {i for i, _, _, _ in db.TagsWalk(start_tag=tag_obj['tags'])}  # type: ignore
    tag_child_ids.add(tag_id)
    indexed_dict: dict[tuple[int, int, int], str] = {}
    for tag_sha in {  # create intermediary set to de-dup
        sha for sha, blob in db.blobs.items() if tag_child_ids.intersection(blob['tags'])}:
      # search for user/album/id to use
      all_loc = sorted(db.blobs[tag_sha]['loc'].keys())
      for user_id, album_id, img in all_loc:
        if db.blobs[tag_sha]['loc'][(user_id, album_id, img)][1] == 'keep':
          # we found a 'keep' verdict in the locations, so we use the first one
          break
      else:
        # there is no 'keep' in the locations (probably all 'new'...) so we take the first one
        user_id, album_id, img = all_loc[0]
      # the key to indexed_dict will help sort by: user / album / image position
      indexed_dict[
          (user_id, album_id, db.favorites[user_id][album_id]['images'].index(img))] = tag_sha
    sorted_blobs = [(0, indexed_dict[k]) for k in sorted(indexed_dict.keys())]
  else:
    # root page, just build a mock object
    tag_obj: fapdata.TagObjType = {
        'name': 'root', 'tags': db.tags}  # "dummy" root tag (has real data) # type: ignore
  # fill in the images context
  context = _ServeImages(request, db, sorted_blobs, 0, 0)
  # get POST data
  new_tag = request.POST.get('named_child', '').strip()
  rename_tag = request.POST.get('rename_tag', '').strip()
  delete_tag = int(request.POST.get('delete_input', '0').strip())
  if ((new_tag or rename_tag or delete_tag) and
      (context['warning_message'] is not None or context['error_message'] is not None)):
    raise fapdata.Error('Multiple POST operations attempted at once!')
  # do the POST operation
  try:
    # do we have a new tag to create?
    if new_tag:
      new_tag_id = db.AddTag(tag_id, new_tag)
      context['warning_message'] = f'Tag {db.TagLineageStr(new_tag_id)} created'
    # should we rename this tag?
    elif rename_tag:
      old_name = db.TagLineageStr(tag_id)
      db.RenameTag(tag_id, rename_tag)
      context['warning_message'] = f'Tag {old_name} renamed to {db.TagLineageStr(tag_id)}'
    # do we have a tag to delete?
    elif delete_tag:
      delete_tag_name = db.TagLineageStr(delete_tag)
      deleted_hashes = db.DeleteTag(delete_tag)
      context['warning_message'] = (
          f'Tag {delete_tag_name} deleted and association removed '
          f'from {len(deleted_hashes)} blobs (images)')
  except fapdata.Error as err:
    context['error_message'] = str(err)
  # save database, if needed: having a 'warning_message' means a successful operation somewhere
  if context['warning_message'] is not None:
    db.Save()
  # update with page-specific context and return
  context.update({
      'tags': [(tid, name, db.TagLineageStr(tid, add_id=False), page_depth + depth)
               for tid, name, depth, _ in db.TagsWalk(start_tag=tag_obj['tags'])],  # type: ignore
      'tag_id': tag_id,
      'page_depth': page_depth,
      'page_depth_up': tag_hierarchy[-2][0] if tag_id and page_depth > 1 else 0,
      'tag_name': db.TagLineageStr(tag_id) if tag_id else None,                # could be renamed?
      'tag_simple_name': db.TagStr(tag_id, add_id=False) if tag_id else None,  # could be renamed?
  })
  return shortcuts.render(request, 'viewer/tag.html', context)


def _AbbreviatedKey(dup_key: duplicates.DuplicatesKeyType) -> safestring.SafeText:
  """Return an abbreviated HTML representation for the key, each key will show 8 hex bytes."""
  if len(dup_key) == 1:
    return safestring.mark_safe(f'{dup_key[0][:16]}&hellip;')  # cspell:disable-line # nosec
  return safestring.mark_safe(  # nosec
      f'({", ".join(f"{sha[:16]}&hellip;" for sha in dup_key)})')  # cspell:disable-line


def ServeDuplicates(request: http.HttpRequest) -> http.HttpResponse:  # noqa: C901
  """Serve the `duplicates` page."""
  db = _DBFactory()  # pylint: disable=invalid-name
  warning_message: Optional[str] = None
  error_message: Optional[str] = None
  # get POST data (not the parameters POST data: these ones we do below, if needed)
  re_run = request.POST.get('re_run', '').strip()
  delete_pending = request.POST.get('delete_pending', '').strip()
  delete_all = request.POST.get('delete_all', '').strip()
  parameters_form = bool(request.POST.get('parameters_form_used', '').strip())
  # do the POST operation
  try:
    # should we re-run the duplicate find operation?
    if re_run:
      warning_message = (
          f'Duplicate operation run, and found {db.FindDuplicates()} new duplicate images')
    # should we clean the duplicates?
    elif delete_pending:
      n_dup, n_img = db.DeletePendingDuplicates()
      warning_message = f'Deleted {n_dup} duplicate groups containing {n_img} duplicate images'
    # should we completely delete all duplicates?
    elif delete_all:
      n_dup, n_img = db.DeleteAllDuplicates()
      warning_message = f'Deleted {n_dup} duplicate groups containing {n_img} duplicate images'
    # should we update the configs?
    elif parameters_form:
      # get everybody
      regular_config_post: duplicates._SensitivitiesType = {
          'percept': (int(request.POST.get('regular_percept', '').strip())
                      if request.POST.get('enabled_regular_percept', '').strip() else -1),
          'diff': (int(request.POST.get('regular_diff', '').strip())
                   if request.POST.get('enabled_regular_diff', '').strip() else -1),
          'average': (int(request.POST.get('regular_average', '').strip())
                      if request.POST.get('enabled_regular_average', '').strip() else -1),
          'wavelet': (int(request.POST.get('regular_wavelet', '').strip())
                      if request.POST.get('enabled_regular_wavelet', '').strip() else -1),
          'cnn': (float(request.POST.get('regular_cnn', '').strip())
                  if request.POST.get('enabled_regular_cnn', '').strip() else -1.0),
      }
      animated_config_post: duplicates._SensitivitiesType = {
          'percept': (int(request.POST.get('animated_percept', '').strip())
                      if request.POST.get('enabled_animated_percept', '').strip() else -1),
          'diff': (int(request.POST.get('animated_diff', '').strip())
                   if request.POST.get('enabled_animated_diff', '').strip() else -1),
          'average': (int(request.POST.get('animated_average', '').strip())
                      if request.POST.get('enabled_animated_average', '').strip() else -1),
          'wavelet': (int(request.POST.get('animated_wavelet', '').strip())
                      if request.POST.get('enabled_animated_wavelet', '').strip() else -1),
          'cnn': (float(request.POST.get('animated_cnn', '').strip())
                  if request.POST.get('enabled_animated_cnn', '').strip() else -1.0),
      }
      # check basic validity
      for method in duplicates.DUPLICATE_HASHES:
        if method == 'cnn':
          if regular_config_post['cnn'] != -1.0:
            if regular_config_post['cnn'] < 0.9 or regular_config_post['cnn'] >= 1.0:
              raise fapdata.Error(
                  f'\'CNN\' method regular value out of bounds: {regular_config_post["cnn"]}')
          if animated_config_post['cnn'] != -1.0:
            if (animated_config_post['cnn'] < 0.9 or animated_config_post['cnn'] >= 1.0 or
                animated_config_post['cnn'] < regular_config_post['cnn']):
              raise fapdata.Error(
                  f'\'CNN\' method regular value out of bounds: {animated_config_post["cnn"]}')
        else:
          if regular_config_post[method] != -1:
            if regular_config_post[method] < 0 or regular_config_post[method] > 15:
              raise fapdata.Error(
                  f'{method.upper()!r} method regular value out of bounds: '
                  f'{regular_config_post[method]}')
          if animated_config_post[method] != -1:
            if (animated_config_post[method] < 0 or animated_config_post[method] > 15 or
                animated_config_post[method] > regular_config_post[method]):
              raise fapdata.Error(
                  f'{method.upper()!r} method regular value out of bounds: '
                  f'{animated_config_post[method]}')
      # everything looks good, so just assign
      db.configs['duplicates_sensitivity_regular'] = regular_config_post
      db.configs['duplicates_sensitivity_animated'] = animated_config_post
      warning_message = 'Updated duplicate search parameters'
  except (fapdata.Error, ValueError) as err:
    error_message = str(err)
  # save database, if needed: having a 'warning_message' means a successful operation somewhere
  if warning_message is not None:
    db.Save()
  # build stats
  sorted_identical = sorted(sha for sha, blob in db.blobs.items() if len(blob['loc']) > 1)
  id_total = sum(len(blob['loc']) for blob in db.blobs.values() if len(blob['loc']) > 1)
  id_new_count = sum(
      1 for blob in db.blobs.values() if len(blob['loc']) > 1
      for st in blob['loc'].values() if st[1] == 'new')
  id_keep_count = sum(
      1 for blob in db.blobs.values() if len(blob['loc']) > 1
      for st in blob['loc'].values() if st[1] == 'keep')
  id_skip_count = sum(
      1 for blob in db.blobs.values() if len(blob['loc']) > 1
      for st in blob['loc'].values() if st[1] == 'skip')
  sorted_keys = sorted(db.duplicates.registry.keys())
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
  # send to page
  context: dict[str, Any] = {
      'identical': {
          sha: {
              'name': _AbbreviatedKey((sha,)),
              'size': len(db.blobs[sha]['loc']),
              'action': any(st[1] == 'new' for st in db.blobs[sha]['loc'].values()),
              'verdicts': ' / '.join(
                  _VERDICT_ABBREVIATION[
                      db.blobs[sha]['loc'][k][1]] for k in sorted(db.blobs[sha]['loc'].keys())),
          }
          for sha in sorted_identical
      },
      'id_action': sum(1 for b in db.blobs.values()
                       if len(b['loc']) > 1 and any(st[1] == 'new' for st in b['loc'].values())),
      'id_count': len(sorted_identical),
      'id_new_count': (f'{id_new_count} ({(100.0 * id_new_count) / id_total:0.1f}%)'
                       if id_total else '-'),
      'id_keep_count': (f'{id_keep_count} ({(100.0 * id_keep_count) / id_total:0.1f}%)'
                        if id_total else '-'),
      'id_skip_count': (f'{id_skip_count} ({(100.0 * id_skip_count) / id_total:0.1f}%)'
                        if id_total else '-'),
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
      'new_count': f'{new_count} ({(100.0 * new_count) / img_count:0.1f}%)' if img_count else '-',
      'false_count': (f'{false_count} ({(100.0 * false_count) / img_count:0.1f}%)'
                      if img_count else '-'),
      'keep_count': (f'{keep_count} ({(100.0 * keep_count) / img_count:0.1f}%)'
                     if img_count else '-'),
      'skip_count': (f'{skip_count} ({(100.0 * skip_count) / img_count:0.1f}%)'
                     if img_count else '-'),
      'configs': {
          'duplicates_sensitivity_regular': db.configs['duplicates_sensitivity_regular'],
          'duplicates_sensitivity_animated': db.configs['duplicates_sensitivity_animated'],
      },
      'warning_message': warning_message,
      'error_message': error_message,
  }
  return shortcuts.render(request, 'viewer/duplicates.html', context)


def ServeDuplicate(request: http.HttpRequest, digest: str) -> http.HttpResponse:  # noqa: C901
  """Serve the `duplicate` page, with a set of duplicates, by giving one of the SHA256 `digest`."""
  # check for errors in parameters
  db = _DBFactory()  # pylint: disable=invalid-name
  error_message: Optional[str] = None
  warning_message: Optional[str] = None
  if digest not in db.blobs:
    raise http.Http404(f'Unknown blob {digest!r}')
  sorted_keys = sorted(db.duplicates.registry.keys())
  sorted_identical = sorted(sha for sha, blob in db.blobs.items() if len(blob['loc']) > 1)
  dup_obj: Optional[duplicates.DuplicateObjType] = None
  if digest in db.duplicates.index:
    # this is a perceptual set, so get the object and its index in sorted_keys, also
    # being a perceptual set page "wins" over being an identical set page
    dup_key: duplicates.DuplicatesKeyType = db.duplicates.index[digest]
    dup_obj = db.duplicates.registry[dup_key]
    current_index = sorted_keys.index(dup_key)
    current_identical: int = -1
  else:
    # not a perceptual set, so maybe it is a direct hash collision
    if len(db.blobs[digest]['loc']) <= 1:
      raise http.Http404(
          f'Blob {digest!r} does not correspond to a duplicate set or hash collision')
    # it is a hash collision, so use digest as `dup_key`, and flag `current_index` with -1 value
    dup_key: duplicates.DuplicatesKeyType = (digest,)
    current_index: int = -1
    current_identical = sorted_identical.index(digest)
  # get user selected choice, if any and update database
  if request.POST:
    loc_key = lambda k: f'{k[0]}_{k[1]}_{k[2]}'  # this is the way the page does 'loc' keys
    # first of all, we have to reject an all-'skip' entry for the perceptual level
    if (any(sha in request.POST for sha in dup_key) and
        not any(request.POST.get(sha, 'skip').lower() != 'skip' for sha in dup_key)):
      error_message = f'POST data for perceptual selections are all "skip": {request.POST!r}'
    for sha in dup_key:
      # check that the selection is superficially valid
      if (sha not in request.POST and         # we either need a perceptual duplicate or ...
          (len(db.blobs[sha]['loc']) <= 1 or  # ... we need an identical duplicate for this sha
           loc_key(list(db.blobs[sha]['loc'].keys())[0]) not in request.POST)):
        error_message = f'Expected key {sha!r} in POST data, but didn\'t find it!'
        break
      # start with the perceptual side
      if sha in request.POST:
        # in this case we have a perceptual duplicate selection to register
        selected_option: duplicates.DuplicatesVerdictType = (  # type: ignore
            request.POST[sha].lower())
        if dup_obj is None or selected_option not in duplicates.DUPLICATE_OPTIONS:
          error_message = f'Key {sha!r} in POST data has invalid option {selected_option!r}!'
          break
        # perceptual selection seems OK: set data in DB structure
        dup_obj['verdicts'][sha] = selected_option
      else:
        # we don't have the perceptive option: pretend it is a 'keep' so the identical level works
        selected_option = 'keep'
      # now we check to see if we have an identical duplicate selection for this sha
      if len(db.blobs[sha]['loc']) > 1:
        # we should have identical duplicate selections for all 'loc'
        identical_options = {k: request.POST.get(loc_key(k), 'missing').lower()
                             for k in db.blobs[sha]['loc'].keys()}
        if any(v not in duplicates.IDENTICAL_OPTIONS for v in identical_options.values()):
          error_message = (f'Key {sha!r} in POST data has missing or invalid identical '
                           f'duplicate selections: {identical_options!r}')
          break
        # we must now check the consistency of the options with the higher (perceptual) level
        if selected_option == 'skip':
          # all the options here should also be 'skip' or we have a consistency problem
          if any(v != 'skip' for v in identical_options.values()):
            warning_message = (f'Key {sha!r} in POST data is marked "skip" so we corrected all '
                               f'child identical selections to "skip" (was {identical_options!r})')
            identical_options = {k: 'skip' for k in db.blobs[sha]['loc'].keys()}
        else:
          # higher (perceptual) level is new/false/keep so we can have anything except all-'skip'
          if not any(v != 'skip' for v in identical_options.values()):
            error_message = (f'Key {sha!r} in POST data is {selected_option!r} but all child '
                             f'identical selections are "skip": {identical_options!r}')
            break
        # if we got here, identical duplicate selections seem OK: set data in DB
        for loc, opt in identical_options.items():
          db.blobs[sha]['loc'][loc] = (db.blobs[sha]['loc'][loc][0], opt)  # type: ignore
    else:
      # everything went smoothly (no break action above), so save the data (but check for error)
      if error_message is None:
        db.Save()
  # send to page

  def _NormalizeHashScore(method: duplicates.DuplicatesHashType, value: int) -> float:
    """Return score as a 0.0 to 10.0 range."""
    max_value: int = db.configs['duplicates_sensitivity_regular'][method]  # type: ignore
    return (max_value - value) * (10.0 / max_value)

  def _NormalizeCosineScore(method: duplicates.DuplicatesHashType, value: float) -> float:
    """Return score as a 0.0 to 10.0 range."""
    min_value: float = db.configs['duplicates_sensitivity_regular'][method]
    return (value - min_value) * (10.0 / (1.0 - min_value))

  context: dict[str, Any] = {
      'digest': digest,
      'dup_key': _AbbreviatedKey(dup_key),
      'has_any_identical': any(len(db.blobs[sha]['loc']) > 1 for sha in dup_key),
      'current_index': current_index,  # can be -1 if this is an identical set page
      'previous_key': sorted_keys[current_index - 1] if current_index > 0 else None,
      'next_key': (sorted_keys[current_index + 1]
                   if -1 < current_index < (len(sorted_keys) - 1) else None),
      'current_identical': current_identical,  # can be -1 if this is a perceptual set page
      'previous_identical': (sorted_identical[current_identical - 1]
                             if current_identical > 0 else None),
      'next_identical': (sorted_identical[current_identical + 1]
                         if -1 < current_identical < (len(sorted_identical) - 1) else None),
      'duplicates': {
          sha: {
              'action': dup_obj['verdicts'][sha] if dup_obj else '',
              'has_identical': len(db.blobs[sha]['loc']) > 1,
              'loc': [
                  {
                      'fap_id': img,
                      'file_name': db.blobs[sha]['loc'][(uid, fid, img)][0],
                      'verdict': db.blobs[sha]['loc'][(uid, fid, img)][1],
                      'user_id': uid,
                      'user_name': db.users[uid]['name'],
                      'folder_id': fid,
                      'folder_name': db.favorites[uid][fid]['name'],
                      'imagefap': fapdata.IMG_URL(img),
                  }
                  for uid, fid, img in sorted(db.blobs[sha]['loc'].keys())
              ],
              'sz': base.HumanizedBytes(db.blobs[sha]['sz']),
              'dimensions': f'{db.blobs[sha]["width"]}x{db.blobs[sha]["height"]} (WxH)',
              'tags': ', '.join(sorted(db.TagLineageStr(t) for t in db.blobs[sha]['tags'])),
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
                          f'{dup_obj["sources"][method][dup_key]:0.3f}' if method == 'cnn' else
                          str(dup_obj['sources'][method][dup_key])),
                      'normalized_value': (
                          f'{_NormalizeCosineScore(method, dup_obj["sources"][method][dup_key]):0.1f}'  # pylint: disable=line-too-long # noqa: E501
                          if method == 'cnn' else
                          f'{_NormalizeHashScore(method, dup_obj["sources"][method][dup_key]):0.1f}'),  # type:ignore # pylint: disable=line-too-long # noqa: E501
                      'sha1': dup_key[0],
                      'sha2': dup_key[1],
                  } for dup_key in sorted(dup_obj['sources'][method].keys())
              ]
          } for method in sorted(dup_obj['sources'].keys())
      ] if dup_obj else [],
      'warning_message': warning_message,
      'error_message': error_message,
  }
  return shortcuts.render(request, 'viewer/duplicate.html', context)


# this page seems to be executing TWICE when called, and blobs' binary representations never ever
# change, so it is perfectly acceptable to cache the hell out of this particular page
@cache.cache_page(60 * 60)
def ServeBlob(unused_request: http.HttpRequest, digest: str) -> http.HttpResponse:
  """Serve the `blob` page, one blob image, given one SHA256 `digest`."""
  # check for errors in parameters
  db = _DBFactory()  # pylint: disable=invalid-name
  if not digest or digest not in db.blobs:
    raise http.Http404(f'Unknown blob {digest!r}')
  if not db.HasBlob(digest):
    raise http.Http404(f'Known blob {digest!r} could not be found on disk')
  # get blob and check for content type (extension)
  blob = db.blobs[digest]
  ext = blob['ext'].lower()
  if ext not in _IMAGE_TYPES:
    raise http.Http404(
        f'Blob {digest!r} image type (file extension) {ext!r} not '
        f'one of {sorted(_IMAGE_TYPES.keys())!r}')
  # send to page
  return http.HttpResponse(content=db.GetBlob(digest), content_type=_IMAGE_TYPES[ext])


# similar to blobs, but smaller...
@cache.cache_page(60 * 60)
def ServeThumb(unused_request: http.HttpRequest, digest: str) -> http.HttpResponse:
  """Serve the `thumb` page, one thumbnail image, given one SHA256 `digest`."""
  # check for errors in parameters
  db = _DBFactory()  # pylint: disable=invalid-name
  if not digest or digest not in db.blobs:
    raise http.Http404(f'Unknown thumb {digest!r}')
  if not db.HasThumbnail(digest):
    raise http.Http404(f'Known thumb {digest!r} could not be found on disk')
  # get thumbnail's blob and check for content type (extension)
  blob = db.blobs[digest]
  ext = blob['ext'].lower()
  if ext not in _IMAGE_TYPES:
    raise http.Http404(
        f'Thumb {digest!r} image type (file extension) {ext!r} not '
        f'one of {sorted(_IMAGE_TYPES.keys())!r}')
  # send to page
  return http.HttpResponse(content=db.GetThumbnail(digest), content_type=_IMAGE_TYPES[ext])
