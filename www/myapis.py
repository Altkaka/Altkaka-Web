import re
class APIError(Exception):

    def __init__(self, error, data='', message=''):
        super(APIError, self).__init__(message)
        self.error = error
        self.data = data
        self.message = message

class Page(object):

    def __init__(self, item_count, page_index=1, page_size=10):
        self.item_count = item_count
        self.page_size = page_size
        self.page_count = item_count // page_size + (1 if item_count % page_size > 0 else 0)
        if (item_count == 0) or (page_index > self.page_count):
            self.offset = 0
            self.limit = 0
            self.page_index = 1
        else:
            self.page_index = page_index
            self.offset = self.page_size * (page_index - 1)
            self.limit = self.page_size
        self.has_next = self.page_index < self.page_count
        self.has_previous = self.page_index > 1

    def __str__(self):
        return 'item_count: %s, page_count: %s, page_index: %s, page_size: %s, offset: %s, limit: %s' % (self.item_count, self.page_count, self.page_index, self.page_size, self.offset, self.limit)

    __repr__ = __str__

def get_page_index(page):

    if isinstance(page, Page):
        return page.page_index
    else:
        return int(page)

def str_to_where(kw, default = '?'):
    kw_len = len(kw)
    kw_key = list(kw.keys())
    str_where=''
    for i in range(kw_len):
        if i == 0:
            str_where = '`%s` = %s ' % (kw_key[i], default)
        else:
            str_where = str_where + 'and `%s` = %s ' % (kw_key[i], default)
    return str_where.strip()

def has_orders(kw):
    orders = ('order', 'orderby', 'order by')
    for order in orders:
        if order in kw.keys():
            return order
    return None

def has_limit(kw):
    limits = ('limit', 'limits')
    for limit in limits:
        if limit in kw.keys():
            return limit
    return None