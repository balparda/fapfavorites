"""Create your views here."""

from django import http
# from django.shortcuts import render


def index(request: http.HttpRequest) -> http.HttpResponse:
  """Index."""
  return http.HttpResponse("Hello, world. You're at the viewer index.")
