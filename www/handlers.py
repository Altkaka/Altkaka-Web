import time,re,hashlib,json
from myweb import get,post
from models import *
import logging ; logging.basicConfig(level = logging.INFO)
from aiohttp import web
from myapis import *

_RE_EAMIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')
COOKIE_NAME = 'AwEsOmE'
_COOKIE_KEY = 'Altkaka'

def user2cookie(user, max_age):
    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)

def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise APIError('用户无权限')

@get('/')
async def index(request):
    if (request.__user__ is None):
        return web.HTTPFound('/signin')
    if (request.__user__ is not None and request.__user__.admin):
        return web.HTTPFound('/manage/blogs')
    blogs = await Blog.findAll(id=request.__user__.id,orderby = 'created_at desc')
    if blogs == None:
        blogs = {}
    return{
        '__template__': 'blogs.html',
        'blogs': blogs
    }

@get('/register')
async def register(request):
    return{
        '__template__':'register.html',
    }

@get('/signin')
async def signin(request):
    return{
        '__template__':'authenticate.html',
    }

@get('/signout')
async def signout(request):
    r = web.HTTPFound('/')
    # 将max_age设为0，则表示删除了cookie
    r.set_cookie(COOKIE_NAME, '', max_age=0, httponly=True)
    logging.info('user signed out')
    return r

@get('/blog/{id}')
async def get_blog_by_blogid(id):
    blog = await Blog.find(id)
    blog.content = blog.content.split('\n')
    return{
        '__template__': 'blog_byid.html',
        'blog': blog
    }

@get('/manage/blogs')
async def manage_blogs(*, page='1'):
    return{
        '__template__':'manage_blogs.html',
        'page_index': get_page_index(page)
    }

@get('/manage/blogs/create')
async def manage_create_blog(request):
    return {
        '__template__':'manage_blog_edit.html'
    }

@get('/manage/blogs/edit')
async def edit_blog_by_blogid(*,id):
    logging.info('edit begin!')
    blog = await Blog.find(id)
    if blog == None:
        raise ('Blog doesnot exit')
    return {
        '__template__':'edit_blog_by_blogid.html',
        'blog': blog,
        'id': blog.id,
        'action':'/api/blogs/edit/'
    }

# @get('/manage/blogs/edit/{id}')
# async def edit_blog_by_blogid(*,id):
#     logging.info('edit begin!')
#     blog = await Blog.find(id)
#     if blog == None:
#         raise ('Blog doesnot exit')
#     return {
#         '__template__':'edit_blog_by_blogid.html',
#         'blog': blog,
#         'id': blog.id,
#         'action':'/api/blogs/edit/'
#     }

@get('/api/users')
async def api_get_users(*, page='1'):
    page_index = get_page_index(page)
    num = await User.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, users=())
    users = await User.findAll(orderby='created_at desc', limit=(p.offset, p.limit))
    for u in users:
        u.passwd = '******'
    return dict(page=p, users=users)

# @get('/api/users')
# async def api_get_users(*,page_size=200,page_num='1'):
#     # 分页查询
#     num = await User.findNumber()
#     if num == 0:
#         return dict(users=())
#     users = await User.findAll()
#     for u in users:
#         u.passwd = '******'
#     return dict(users=users)

@get('/api/blogs')
async def api_get_blogs(*,page='1'):
    page_index = get_page_index(page)
    num = await Blog.findNumber()
    p = Page(num, page_index)
    if num==0:
        return dict(page=p, blogs=())
    blogs = await Blog.findAll(orderby = 'created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, blogs=blogs)

@get('/api/blogs/{id}')
async def get_oneblog_by_blogid(id):
    blog = await Blog.find(id)
    return dict(blog = blog)

# @get('/api/blogs')
# async def api_get_blogs(*,page='1'):
#     page_index = get_page_index(page)
#     num = await Blog.findNumber()
#     p = Page(num, page_index)
#     if num==0:
#         return dict(page=p, blogs=())
#     blogs = await Blog.findAll()
#     return dict(page=p, blogs=blogs)

@post('/api/users')
async def api_register_user(*, email, name, passwd):
    if not name or not name.strip():
        raise APIError('name')
    if not email or not _RE_EAMIL.match(email):
        raise APIError('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIError('passwd')
    users = await User.findAll(email=email)
    if users != None:
        raise APIError('regisiter:failed', 'email', 'Email is already in use.')
    uid = next_id()
    sha1_passwd = '%s:%s' % (uid, passwd)
    user = User(id=uid,name=name.strip(),email=email.strip(),passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), image = 'http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    await user.save()
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

@post('/api/authenticate')
async def authenticate(*, email, passwd):
    if not email:
        # raise APIError('email', 'Invalid email.')
        raise APIError('Invalid email.')
    if not passwd:
        # raise APIError('passwd', 'Invalid password.')
        raise APIError('Invalid password.')
    users = await User.findAll(email=email)
    if users == None:
        # raise APIError('email', 'Email not exist.')
        raise APIError('Email not exist.')
    user = users[0]
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(passwd.encode('utf-8'))
    if user.passwd != sha1.hexdigest():
        print(user.passwd+':'+sha1.hexdigest())
        # raise APIError('passwd', 'Invalid password.')
        raise APIError('Invalid password.')
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

@post('/manage/blogs/create')
async def api_create_blog(request, *, name, summary, content):
    check_admin(request)
    if not name or not name.strip():
        raise APIError('name cannot be empty')
    if not summary or not summary.strip():
        raise APIError('summary cannot be empty')
    if not content or not content.strip():
        raise APIError('content cannot be empty')
    blog = Blog(user_id = request.__user__.id, user_name = request.__user__.name, user_image = request.__user__.image, name=name.strip(), summary=summary.strip(), content=content.strip())
    await blog.save()
    return blog

@post('/api/blogs/edit/{id}')
async def api_edit_blog(request, *, id, name, summary, content):
    if not name or not name.strip():
        raise APIError('name cannot be empty')
    if not summary or not summary.strip():
        raise APIError('summary cannot be empty')
    if not content or not content.strip():
        raise APIError('content cannot be empty')
    blog = await Blog.find(id)
    if blog == None:
        raise APIError('Blog doesnot exist')
    blog.name = name
    blog.summary = summary
    blog.content = content
    await blog.update()
    return blog

# @post('/api/blogs')
# async def api_create_blog(request, *, name, summary, content):
#     check_admin(request)
#     if not name or not name.strip():
#         raise APIError('name cannot be empty')
#     if not summary or not summary.strip():
#         raise APIError('summary cannot be empty')
#     if not content or not content.strip():
#         raise APIError('content cannot be empty')
#     blog = Blog(user_id = request.__user__.id, user_name = request.__user__.name, user_image = request.__user__.image, name=name.strip(), summary=summary.strip(), content=content.strip())
#     await blog.save()
#     return blog

@post('/api/blogs{id}delete')
async def delete_blog_by_blogid(id):
    blog = await Blog.find(id)
    if blog==None:
        raise APIError('Blog doesnot exit')
    await blog.remove()
    return blog