"""Create your views here."""

import functools
import logging
# import pdb

from django import http
from django import shortcuts

import fapdata


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
      # TODO: fill context with actual data
  }
  return shortcuts.render(request, 'viewer/index.html', context)


def ServeUsers(request: http.HttpRequest) -> http.HttpResponse:
  """Serve the `users` page."""
  db = _GetLoadedDatabase(fapdata.DEFAULT_DB_DIRECTORY, fapdata.GetDatabaseTimestamp())
  context = {
      'users': db.users,
  }
  return shortcuts.render(request, 'viewer/users.html', context)


def ServeUser(request: http.HttpRequest, user_id: int) -> http.HttpResponse:
  """Serve the `user` page."""
  db = _GetLoadedDatabase(fapdata.DEFAULT_DB_DIRECTORY, fapdata.GetDatabaseTimestamp())
  context = {
      'user_id': user_id,
      # TODO: fill context with actual data
  }
  return shortcuts.render(request, 'viewer/user.html', context)


def ServeFavorites(request: http.HttpRequest, user_id: int) -> http.HttpResponse:
  """Serve the `favorites` page of one `user_id`."""
  db = _GetLoadedDatabase(fapdata.DEFAULT_DB_DIRECTORY, fapdata.GetDatabaseTimestamp())
  context = {
      'user_id': user_id,
      # TODO: fill context with actual data
  }
  return shortcuts.render(request, 'viewer/favorites.html', context)


def ServeFavorite(request: http.HttpRequest, user_id: int, folder_id: int) -> http.HttpResponse:
  """Serve the `favorite` (album) page for an `user_id` and a `folder_id`."""
  db = _GetLoadedDatabase(fapdata.DEFAULT_DB_DIRECTORY, fapdata.GetDatabaseTimestamp())
  context = {
      'user_id': user_id,
      'folder_id': folder_id,
      # TODO: fill context with actual data
  }
  return shortcuts.render(request, 'viewer/favorite.html', context)


def ServeTags(request: http.HttpRequest) -> http.HttpResponse:
  """Serve the `tags` page."""
  db = _GetLoadedDatabase(fapdata.DEFAULT_DB_DIRECTORY, fapdata.GetDatabaseTimestamp())
  context = {
      # TODO: fill context with actual data
  }
  return shortcuts.render(request, 'viewer/tags.html', context)


def ServeTag(request: http.HttpRequest, tag_id: int) -> http.HttpResponse:
  """Serve the `tag` page for one `tag_id`."""
  db = _GetLoadedDatabase(fapdata.DEFAULT_DB_DIRECTORY, fapdata.GetDatabaseTimestamp())
  context = {
      'tag_id': tag_id,
      # TODO: fill context with actual data
  }
  return shortcuts.render(request, 'viewer/tag.html', context)


def ServeBlob(request: http.HttpRequest, digest: str) -> http.HttpResponse:
  """Serve the `blob` page, one image, given one SHA256 `digest`."""
  db = _GetLoadedDatabase(fapdata.DEFAULT_DB_DIRECTORY, fapdata.GetDatabaseTimestamp())
  raise http.Http404('not implemented yet!')


def ServeDuplicates(request: http.HttpRequest) -> http.HttpResponse:
  """Serve the `duplicates` page."""
  db = _GetLoadedDatabase(fapdata.DEFAULT_DB_DIRECTORY, fapdata.GetDatabaseTimestamp())
  context = {
      # TODO: fill context with actual data
  }
  return shortcuts.render(request, 'viewer/duplicates.html', context)


def ServeDuplicate(request: http.HttpRequest, digest: str) -> http.HttpResponse:
  """Serve the `duplicate` page, with a set of duplicates, by giving one of the SHA256 `digest`."""
  db = _GetLoadedDatabase(fapdata.DEFAULT_DB_DIRECTORY, fapdata.GetDatabaseTimestamp())
  context = {
      'digest': digest,
      # TODO: fill context with actual data
  }
  return shortcuts.render(request, 'viewer/duplicate.html', context)
