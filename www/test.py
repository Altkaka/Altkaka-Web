# import time
# dic = {
#     '11':1,
#     '22':2,
#     '33':3,
#     '44':4,
# }
# print(list(dic.keys()))
# print(list(dic.values()))
# print(list(dic.items())[0][0])
# print(list(dic)[0])
# print(list(dic.keys()))

# def str_to_where(kw, default = '?'):
#     kw_len = len(kw)
#     kw_key = list(kw.keys())
#     str_where=''
#     for i in range(kw_len):
#         if i == 0:
#             str_where = '`%s` = %s ' % (kw_key[i], default)
#         else:
#             str_where = str_where + 'and `%s` = %s ' % (kw_key[i], default)
#     return str_where.strip()
#
# s1 = 'where %s' % (str_to_where(dic)), list(dic.values())
# print(str_to_where(dic, '.'))
# print(s1)

# print(time.time)
#
# import orm,asyncio
# from Model import *
# def test(loop):
#     yield from orm.create_pool(loop=loop, user='www-data', password='www-data', db='awesome')
#     u = User(name='Test', email='test@example.com', passwd='1234567890', image='about:blank')
#     yield from u.save()
#
# loop = asyncio.get_event_loop()
# loop.run_until_complete(test(loop))
# loop.close()

import base64
s = ''
sb = base64.b64decode(s)
print(sb.decode('utf-8'))