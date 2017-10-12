import logging; logging.basicConfig(level = logging.INFO)
import asyncio
import aiomysql
from myapis import APIError
from myapis import *


async def create_pool(loop, **kw):
    logging.info('create database connection pool...')
    global __pool
    __pool = await aiomysql.create_pool(
        host = kw.get('host','localhost'),
        port = kw.get('port',3306),
        user = kw['user'],
        password = kw['password'],
        db = kw['db'],
        charset = kw.get('charset', 'utf8'),
        autocommit = kw.get('autocommit', True),
        maxsize = kw.get('maxsize', 10),
        minsize = kw.get('minsize', 1),
        loop = loop
    )

async def select(sql, args, size=None):
    logging.info('select : SQL: %s', sql)
    logging.info('select : args: %s', args)
    global __pool
    async with __pool.get() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql.replace('?', '%s'), args or ())
            if size:
                rs = await cur.fetchmany(size)
            else:
                rs = await cur.fetchall()
        logging.info('row returned: %s' % len(rs))
        return rs

async def execute(sql, args, autocommit = True):
    # logging.info('execute:SQL:',sql, 'args:',args)
    # global __pool
    # with (yield from __pool) as conn:
    #     try:
    #         cur = yield from conn.cursor()
    #         yield from cur.execute(sql.replace('?', '%s'), args)
    #         affected = cur.rowcount
    #         yield from cur.close()
    #     except BaseException as e:
    #         raise
    #         logging.ERROR(e.__context__)
    #     return affected
    logging.info('execute : SQL: %s', sql)
    logging.info('execute : args: %s', args)
    global __pool
    async with __pool.get() as conn:
        if not autocommit:
            await conn.begin()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql.replace('?', '%s'), args)
                affected = cur.rowcount
                await cur.close()
            if not autocommit:
                await conn.commit()
                logging.info('commit success!')
        except BaseException as e:
            if not autocommit:
                await conn.rollback()
            raise
        finally:
            conn.close()
        return affected
    logging.info('rows returned: %s ' % affected)

def create_args_string(len):
    return '?'+',?'*(len-1)

class ModelMetaclass(type):

    def __new__(cls, name, bases, attrs):
        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)
        tableName = attrs.get('__table__', None) or name
        logging.info('found model: %s (table: %s)' % (name, tableName))
        mappings = dict()
        fields = []
        primaryKey = None
        for k, v in attrs.items():
            if isinstance(v, Field):
                logging.info('found mapping: %s ==> %s' % (k, v))
                mappings[k] = v
                if v.primary_key:
                    if primaryKey:
                        raise APIError('Duplicate primary key for field: %s' % k)
                    primaryKey = k
                else:
                    fields.append(k)
        if not primaryKey:
            raise APIError('Primary key not found.')
        for k in mappings.keys():
            attrs.pop(k)
        escaped_fields = list(map(lambda f: '`%s`' % f, fields))
        attrs['__mappings__'] = mappings
        attrs['__table__'] = tableName
        attrs['__primary_key__'] = primaryKey
        attrs['__fields__'] = fields
        # 下列sql语句中的反引号是为了防止字段名称出现保留字报错而预留的，一般在进行mysql的sql语句撰写时，字段名称使用双引号防止报错
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ','.join(escaped_fields), tableName)
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ','.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields)+1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ','.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s` = ?' % (tableName, primaryKey)
        return type.__new__(cls, name, bases, attrs)

class Model(dict, metaclass=ModelMetaclass):

    def __init__(self, **kw):
        super(Model, self).__init__(**kw)

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s' " % key)

    def __setattr__(self, key, value):
        self[key] = value

    def getValue(self, key):
        return getattr(self, key, None)

    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s:%s' % (key, str(value)))
                setattr(self, key, value)
        return value

    @classmethod
    #根据主键查找记录
    async def find(cls, pk):
        rs = await select('%s where `%s` = ?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        logging.info('find rs:%s',rs[0])
        return  cls(**rs[0])

    async def save(self):
        args = list(map(self.getValueOrDefault, self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        rows = await execute(self.__insert__, args)
        if rows != 1:
            logging.warning('faild to insert record: affected rows: %s' % rows)

    @classmethod
    #findAll() - 根据WHERE条件查找
    async def findAll(cls, **kw):
        order_flag = False
        order_values = ''
        limit_flag = False
        limit_values = ()
        logging.info('find-all beigin')
        logging.info('find-all: %s-%d', kw, len(kw))
        if has_orders(kw):
            order_flag = True
            order_values = kw[has_orders(kw)]
            kw.pop(has_orders(kw))
        if has_limit(kw):
            limit_flag = True
            limit_values = kw[has_limit(kw)]
            kw.pop(has_limit(kw))
            values = list(kw.values())
            values.append(limit_values[0])
            values.append(limit_values[1])
        if len(kw)==0:
            if order_flag and limit_flag:
                rs = await select('%s order by %s limit ? , ?' % (cls.__select__, order_values), values)
            elif order_flag and not limit_flag:
                rs = await select('%s order by %s' % (cls.__select__, order_values), list(kw.values()))
            elif not order_flag and limit_flag:
                rs = await select('%s limit ? , ?' % cls.__select__,values)
            else:
                rs = await select('%s ' % cls.__select__ , args=None)
        else:
            if order_flag and limit_flag:
                rs = await select('%s where %s order by %s limit ? , ?' % (cls.__select__, str_to_where(kw), order_values), values)
            elif order_flag and not limit_flag:
                rs = await select('%s where %s order by %s' % (cls.__select__, str_to_where(kw), order_values), list(kw.values()))
            elif not order_flag and limit_flag:
                rs = await select('%s where %s limit ? , ?' % (cls.__select__, str_to_where(kw)),values)
            else:
                rs = await select('%s where %s' % (cls.__select__, str_to_where(kw)), list(kw.values()))
        if len(rs) == 0:
            return None
        logging.info('find-all end results: %s',rs)
        return [cls(**r) for r in rs]

    @classmethod
    #findNumber() - 根据WHERE条件查找，但返回的是整数，适用于select count(*)类型的SQL
    async def findNumber(cls, **kw):
        if len(kw)==0:
            logging.info('%s' % cls.__select__)
            rs = await select('select count(*) from %s' % cls.__table__, args=None)
        else:
            rs = await select('select count(*) from %s where %s' % (cls.__table__, str_to_where(kw)), list(kw.values()))
        logging.info('findnumber:%s', rs[0]['count(*)'])
        if len(rs) == 0:
            return None
        return rs[0]['count(*)']

    #根据主键插入
    async def update(self):

        args = list(map(self.getValueOrDefault, self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        rows = await execute(self.__update__, args)
        return rows

    #根据主键删除
    async def remove(self):

        args=[]
        args.append(self.getValueOrDefault(self.__primary_key__))
        rows = await execute(self.__delete__, args)
        return rows



class Field(object):

    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)

class StringField(Field):

    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
        super().__init__(name, ddl, primary_key, default)

class TinyIntField(Field):

    def __init__(self, name=None, primary_key=False, default = None, ddl='tinyint'):
        super().__init__(name, ddl, primary_key, default)

class SmallIntField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='smallint'):
        super().__init__(name, ddl, primary_key, default)


class MediumIntField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='mediumint'):
        super().__init__(name, ddl, primary_key, default)

class IntField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='int'):
        super().__init__(name, ddl, primary_key, default)

class BigIntField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='bigint'):
        super().__init__(name, ddl, primary_key, default)

class FloatField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='float'):
        super().__init__(name, ddl, primary_key, default)

class DoubleField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='double'):
        super().__init__(name, ddl, primary_key, default)

class DecimalField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='decimal(19,2)'):
        super().__init__(name, ddl, primary_key, default)

class CharStringField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='char(100)'):
        super().__init__(name, ddl, primary_key, default)

class TinyBlobField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='tinyblob'):
        super().__init__(name, ddl, primary_key, default)

class TinyTextField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='tinytext'):
        super().__init__(name, ddl, primary_key, default)

class BlobField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='blob'):
        super().__init__(name, ddl, primary_key, default)

class TextField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='text'):
        super().__init__(name, ddl, primary_key, default)

class MediumBlobField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='mediumblob'):
        super().__init__(name, ddl, primary_key, default)

class MediumTextField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='mediumtext'):
        super().__init__(name, ddl, primary_key, default)

class LongBlobField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='longblob'):
        super().__init__(name, ddl, primary_key, default)

class longTextField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='longtext'):
        super().__init__(name, ddl, primary_key, default)

class VarBinaryField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='varbinary(100)'):
        super().__init__(name, ddl, primary_key, default)

class BinaryField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='binary(100)'):
        super().__init__(name, ddl, primary_key, default)

class DateField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='date'):
        super().__init__(name, ddl, primary_key, default)

class TimeField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='time'):
        super().__init__(name, ddl, primary_key, default)

class YearField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='year'):
        super().__init__(name, ddl, primary_key, default)

class DateTimeField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='datetime'):
        super().__init__(name, ddl, primary_key, default)

class TimeStampField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='timestamp'):
        super().__init__(name, ddl, primary_key, default)

class BooleanField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='boolean'):
        super().__init__(name, ddl, primary_key, default)