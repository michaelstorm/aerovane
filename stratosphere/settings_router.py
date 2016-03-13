from .util import get_thread_local


# from https://dzone.com/articles/django-switching-databases
class SettingsRouter(object):
    """
    A router to control all database operations on models in
    the website application. Can be over-ridden on demand with a
    decorator on a view or a particular function:

    @thread_local(DB_OVERRIDE='report')
    def social_network_reach(request):

    This is more DRY than having a .using() on every query. It also
    means you don't have to pass a using parameter all over the place.
    """

    def db_for_read(self, model, **hints):
        return get_thread_local('DB_OVERRIDE', 'default')

    def db_for_write(self, model, **hints):
        return get_thread_local('DB_OVERRIDE', 'default')

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_syncdb(self, db, model):
        return None