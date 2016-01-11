import logging
from psycopg2.extensions import cursor as _cursor


class LoggingCursor(_cursor):
    def execute(self, sql, args=None):
        logger = logging.getLogger('sql_debug')
        logger.info(self.mogrify(sql, args).decode('utf-8'))

        try:
            _cursor.execute(self, sql, args)
        except Exception as exc:
            logger.error("%s: %s" % (exc.__class__.__name__, exc))
            raise