"""
The manager class for the CMS models
"""
from django.core.urlresolvers import reverse
from django.http import Http404
from mptt.managers import TreeManager
from polymorphic import PolymorphicManager
from polymorphic.query import PolymorphicQuerySet
from fluent_pages.utils.db import DecoratingQuerySet


class UrlNodeQuerySet(PolymorphicQuerySet, DecoratingQuerySet):
    pass


class UrlNodeManager(TreeManager, PolymorphicManager):
    """
    Extra methods attached to ``UrlNode.objects`` and ``Page.objects``.
    """

    def __init__(self, *args, **kwargs):
        PolymorphicManager.__init__(self, UrlNodeQuerySet, *args, **kwargs)


    def get_for_path_or_404(self, path):
        """
        Return the UrlNode for the given path.

        Raises a Http404 error when the object is not found.
        """
        if path.startswith(reverse('admin:index')[1:]):
            raise Http404("No admin page found at '/{0}'\n(raised by fluent_pages catch-all).".format(path))

        try:
            return self.get_for_path(path)
        except self.model.DoesNotExist as e:
            raise Http404(e)


    def get_for_path(self, path):
        """
        Return the UrlNode for the given path.

        Raises UrlNode.DoesNotExist when the item is not found.
        """
        # Normalize slashes
        path = '/{0}'.format(path)

        try:
            return self.published().get(_cached_url=path)
        except self.model.DoesNotExist:
            raise self.model.DoesNotExist("No published {0} found for the path '{1}'".format(self.model.__name__, path))


    def best_match_for_path(self, path):
        """
        Return the UrlNode that is the closest parent to the given path.

        UrlNode.objects.best_match_for_path('/photos/album/2008/09') might return the page with url '/photos/album/'.
        """
        # from FeinCMS:
        paths = ['/']
        if path:
            tokens = path.split('/')
            paths += ['/%s/' % '/'.join(tokens[:i]) for i in range(1, len(tokens)+1)]

        try:
            return self.published() \
                       .filter(_cached_url__in=paths) \
                       .extra(select={'_url_length': 'LENGTH(_cached_url)'}) \
                       .order_by('-_url_length')[0]
        except IndexError:
            raise self.model.DoesNotExist("No published {0} found for the path '{1}'".format(self.model.__name__, path))


    def published(self):
        """
        Return only published pages
        """
        from fluent_pages.models import UrlNode   # the import can't be globally, that gives a circular dependency
        return self.get_query_set().filter(status=UrlNode.PUBLISHED)


    def in_navigation(self):
        """
        Return only pages in the navigation.
        """
        return self.published().filter(in_navigation=True)


    def toplevel_navigation(self, current_page=None):
        """
        Return all toplevel items.

        When current_page is passed, the object values such as 'is_current' will be set. 
        """
        items = self.in_navigation().filter(parent__isnull=True).non_polymorphic()
        if current_page:
            items = _mark_current(items, current_page)
        return items


# Implemented as method, to avoid overwriting the QuerySet once again.
def _mark_current(qs, current_page):
    """
    Mark the given page as "is_current" in the resulting set.
    """
    current_id = current_page.id

    def add_prop(obj):
        obj.is_current = (obj.id == current_id)

    return qs.decorate(add_prop)
