# -*- coding: utf-8 -*-
import os
import re
import codecs
import sys
import operator
import functools
import warnings
import urllib
import datetime
import time
import random
import hashlib
import codecs
import urllib2
import urlparse
import cookielib
from HTMLParser import HTMLParser
import requests
try:
    from htmlentitydefs import name2codepoint
except ImportError:
    from html.entities import name2codepoint
try:
    import __builtin__
except ImportError:
    import builtin #__builtin__ as builtins
# ------------------------------------------------------------------------------
PY2 = sys.version_info[0] == 2
WIN = sys.platform.startswith('win')
_format_re = re.compile(r'\$(?:(%s)|\{(%s)\})' % (('[a-zA-Z_][a-zA-Z0-9_]*',) * 2))
_entity_re = re.compile(r'&([^;]+);')
_identity = lambda x: x

if PY2:
    unichr = unichr
    text_type = unicode
    string_types = (str, unicode)
    integer_types = (int, long)

    iterkeys = lambda d, *args, **kwargs: d.iterkeys(*args, **kwargs)
    itervalues = lambda d, *args, **kwargs: d.itervalues(*args, **kwargs)
    iteritems = lambda d, *args, **kwargs: d.iteritems(*args, **kwargs)

    iterlists = lambda d, *args, **kwargs: d.iterlists(*args, **kwargs)
    iterlistvalues = lambda d, *args, **kwargs: d.iterlistvalues(*args, **kwargs)

    int_to_byte = chr
    iter_bytes = iter

    exec('def reraise(tp, value, tb=None):\n raise tp, value, tb')

    def fix_tuple_repr(obj):
        def __repr__(self):
            cls = self.__class__
            return '%s(%s)' % (cls.__name__, ', '.join(
                '%s=%r' % (field, self[index])
                for index, field in enumerate(cls._fields)
            ))
        obj.__repr__ = __repr__
        return obj

    def implements_iterator(cls):
        cls.next = cls.__next__
        del cls.__next__
        return cls

    def implements_to_string(cls):
        cls.__unicode__ = cls.__str__
        cls.__str__ = lambda x: x.__unicode__().encode('utf-8')
        return cls

    def native_string_result(func):
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs).encode('utf-8')
        return functools.update_wrapper(wrapper, func)

    def implements_bool(cls):
        cls.__nonzero__ = cls.__bool__
        del cls.__bool__
        return cls

    from itertools import imap, izip, ifilter
    range_type = xrange

    from StringIO import StringIO
    from cStringIO import StringIO as BytesIO
    NativeStringIO = BytesIO

    def make_literal_wrapper(reference):
        return _identity

    def normalize_string_tuple(tup):
        """Normalizes a string tuple to a common type. Following Python 2
        rules, upgrades to unicode are implicit.
        """
        if any(isinstance(x, text_type) for x in tup):
            return tuple(to_unicode(x) for x in tup)
        return tup

    def try_coerce_native(s):
        """Try to coerce a unicode string to native if possible. Otherwise,
        leave it as unicode.
        """
        try:
            return to_native(s)
        except UnicodeError:
            return s

    wsgi_get_bytes = _identity

    def wsgi_decoding_dance(s, charset='utf-8', errors='replace'):
        return s.decode(charset, errors)

    def wsgi_encoding_dance(s, charset='utf-8', errors='replace'):
        if isinstance(s, bytes):
            return s
        return s.encode(charset, errors)

    def to_bytes(x, charset=sys.getdefaultencoding(), errors='strict'):
        if x is None:
            return None
        if isinstance(x, (bytes, bytearray, buffer)):
            return bytes(x)
        if isinstance(x, unicode):
            return x.encode(charset, errors)
        raise TypeError('Expected bytes')

    def to_native(x, charset=sys.getdefaultencoding(), errors='strict'):
        if x is None or isinstance(x, str):
            return x
        return x.encode(charset, errors)
else:
    unichr = chr
    text_type = str
    string_types = (str, )
    integer_types = (int, )

    iterkeys = lambda d, *args, **kwargs: iter(d.keys(*args, **kwargs))
    itervalues = lambda d, *args, **kwargs: iter(d.values(*args, **kwargs))
    iteritems = lambda d, *args, **kwargs: iter(d.items(*args, **kwargs))

    iterlists = lambda d, *args, **kwargs: iter(d.lists(*args, **kwargs))
    iterlistvalues = lambda d, *args, **kwargs: iter(d.listvalues(*args, **kwargs))

    int_to_byte = operator.methodcaller('to_bytes', 1, 'big')
    iter_bytes = functools.partial(map, int_to_byte)

    def reraise(tp, value, tb=None):
        if value.__traceback__ is not tb:
            raise value.with_traceback(tb)
        raise value

    fix_tuple_repr = _identity
    implements_iterator = _identity
    implements_to_string = _identity
    implements_bool = _identity
    native_string_result = _identity
    imap = map
    izip = zip
    ifilter = filter
    range_type = range

    from io import StringIO, BytesIO
    NativeStringIO = StringIO

    _latin1_encode = operator.methodcaller('encode', 'latin1')

    def make_literal_wrapper(reference):
        if isinstance(reference, text_type):
            return _identity
        return _latin1_encode

    def normalize_string_tuple(tup):
        """Ensures that all types in the tuple are either strings
        or bytes.
        """
        tupiter = iter(tup)
        is_text = isinstance(next(tupiter, None), text_type)
        for arg in tupiter:
            if isinstance(arg, text_type) != is_text:
                raise TypeError('Cannot mix str and bytes arguments (got %s)'
                                % repr(tup))
        return tup

    try_coerce_native = _identity
    wsgi_get_bytes = _latin1_encode

    def wsgi_decoding_dance(s, charset='utf-8', errors='replace'):
        return s.encode('latin1').decode(charset, errors)

    def wsgi_encoding_dance(s, charset='utf-8', errors='replace'):
        if isinstance(s, text_type):
            s = s.encode(charset)
        return s.decode('latin1', errors)

    def to_bytes(x, charset=sys.getdefaultencoding(), errors='strict'):
        if x is None:
            return None
        if isinstance(x, (bytes, bytearray, memoryview)):  # noqa
            return bytes(x)
        if isinstance(x, str):
            return x.encode(charset, errors)
        raise TypeError('Expected bytes')

    def to_native(x, charset=sys.getdefaultencoding(), errors='strict'):
        if x is None or isinstance(x, str):
            return x
        return x.decode(charset, errors)


def to_unicode(x, charset=sys.getdefaultencoding(), errors='strict',
               allow_none_charset=False):
    if x is None:
        return None
    if not isinstance(x, bytes):
        return text_type(x)
    if charset is None and allow_none_charset:
        return x
    return x.decode(charset, errors)


# ------------------------------------------------------------------------------
class HTMLBuilder(object):
    """Helper object for HTML generation.

    Per default there are two instances of that class.  The `html` one, and
    the `xhtml` one for those two dialects.  The class uses keyword parameters
    and positional parameters to generate small snippets of HTML.

    Keyword parameters are converted to XML/SGML attributes, positional
    arguments are used as children.  Because Python accepts positional
    arguments before keyword arguments it's a good idea to use a list with the
    star-syntax for some children:

    >>> html.p(class_='foo', *[html.a('foo', href='foo.html'), ' ',
    ...                        html.a('bar', href='bar.html')])
    u'<p class="foo"><a href="foo.html">foo</a> <a href="bar.html">bar</a></p>'

    This class works around some browser limitations and can not be used for
    arbitrary SGML/XML generation.  For that purpose lxml and similar
    libraries exist.

    Calling the builder escapes the string passed:

    >>> html.p(html("<foo>"))
    u'<p>&lt;foo&gt;</p>'
    """

    _entity_re = re.compile(r'&([^;]+);')
    _entities = name2codepoint.copy()
    _entities['apos'] = 39
    _empty_elements = set(
        ['area', 'base', 'basefont', 'br', 'col', 'command', 'embed', 'frame', 'hr', 'img', 'input', 'keygen',
         'isindex', 'link', 'meta', 'param', 'source', 'wbr'])
    _boolean_attributes = set(
        ['selected', 'checked', 'compact', 'declare', 'defer', 'disabled', 'ismap', 'multiple', 'nohref', 'noresize',
         'noshade', 'nowrap'])
    _plaintext_elements = set(['textarea'])
    _c_like_cdata = set(['script', 'style'])

    def __init__(self, dialect):
        self._dialect = dialect

    def __call__(self, s):
        return escape(s)

    def __getattr__(self, tag):
        if tag[:2] == '__':
            raise AttributeError(tag)

        def proxy(*children, **arguments):
            buffer = '<' + tag
            for key, value in iteritems(arguments):
                if value is None:
                    continue
                if key[-1] == '_':
                    key = key[:-1]
                if key in self._boolean_attributes:
                    if not value:
                        continue
                    if self._dialect == 'xhtml':
                        value = '="' + key + '"'
                    else:
                        value = ''
                else:
                    value = '="' + escape(value) + '"'
                buffer += ' ' + key + value
            if not children and tag in self._empty_elements:
                if self._dialect == 'xhtml':
                    buffer += ' />'
                else:
                    buffer += '>'
                return buffer
            buffer += '>'

            children_as_string = ''.join([text_type(x) for x in children
                                          if x is not None])

            if children_as_string:
                if tag in self._plaintext_elements:
                    children_as_string = escape(children_as_string)
                elif tag in self._c_like_cdata and self._dialect == 'xhtml':
                    children_as_string = '/*<![CDATA[*/' + \
                                         children_as_string + '/*]]>*/'
            buffer += children_as_string + '</' + tag + '>'
            return buffer

        return proxy

    def __repr__(self):
        return '<%s for %r>' % (
            self.__class__.__name__,
            self._dialect
        )


html = HTMLBuilder('html')
xhtml = HTMLBuilder('xhtml')


def escape(s, quote=None):
    """Replace special characters "&", "<", ">" and (") to HTML-safe sequences.

    There is a special handling for `None` which escapes to an empty string.

    .. versionchanged:: 0.9
       `quote` is now implicitly on.

    :param s: the string to escape.
    :param quote: ignored.
    """
    if s is None:
        return ''
    elif hasattr(s, '__html__'):
        return text_type(s.__html__())
    elif not isinstance(s, string_types):
        s = text_type(s)
    if quote is not None:
        from warnings import warn
        warn(DeprecationWarning('quote parameter is implicit now'), stacklevel=2)
    s = s.replace('&', '&amp;').replace('<', '&lt;') \
        .replace('>', '&gt;').replace('"', "&quot;")
    return s


def unescape(s):
    """The reverse function of `escape`.  This unescapes all the HTML
    entities, not only the XML entities inserted by `escape`.

    :param s: the string to unescape.
    """

    def handle_match(m):
        name = m.group(1)
        if name in HTMLBuilder._entities:
            return unichr(HTMLBuilder._entities[name])
        try:
            if name[:2] in ('#x', '#X'):
                return unichr(int(name[2:], 16))
            elif name.startswith('#'):
                return unichr(int(name[1:]))
        except ValueError:
            pass
        return u''

    return _entity_re.sub(handle_match, s)


# ------------------------------------------------------------------------------
class MLStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return ''.join(self.fed)

# ------------------------------------------------------------------------------
class FileUtils(object):
    """docstring for FileUtils - File Helpers"""

    def fileExists(self, filename):
        return os.path.isfile(filename)

    def getFileExtension(self, filename):
        ext_pos = filename.rfind('.')
        if ext_pos != -1:
            return filename[ext_pos + 1:]
        else:
            return ''

    def get_immediate_subdirectories(self, directory):
        return [name for name in os.listdir(directory)
                if os.path.isdir(os.path.join(directory, name))]

    def findInSubdirectory(self, filename, subdirectory=''):
        if subdirectory:
            path = subdirectory
        else:
            path = os.getcwd()
        for root, _, names in os.walk(path):
            if filename in names:
                return os.path.join(root, filename)
        raise 'File not found'

    def cleanFilename(self, s):
        if not s:
            return ''
        badchars = '\\/:*?\"<>|'
        for c in badchars:
            s = s.replace(c, '')
        return s;

    def randomFilename(self, directory, chars='0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ',
                       length=8, prefix='', suffix='', attempts=10000):
        for _ in range(attempts):
            filename = ''.join([random.choice(chars) for _ in range(length)])
            filename = prefix + filename + suffix
            if not os.path.exists(os.path.join(directory, filename)):
                return filename
        return None

    def getFileContent(self, filename):
        try:
            f = codecs.open(filename, 'r', 'utf-8')
            txt = f.read()
            f.close()
            return txt
        except:
            return ''

    def setFileContent(self, filename, txt, createFolders=False):
        try:
            if createFolders:
                folderPath = os.path.dirname(filename)
                if not os.path.exists(folderPath):
                    os.makedirs(folderPath, 0777)
            f = codecs.open(filename, 'w', 'utf-8')
            f.write(txt)
            f.close()
            return True
        except:
            return False

    def appendFileContent(self, filename, txt):
        try:
            f = codecs.open(filename, 'a', 'utf-8')
            f.write(txt)
            f.close()
            return True
        except:
            return False

    def md5(self, fileName, excludeLine="", includeLine=""):
        """Compute md5 hash of the specified file"""
        m = hashlib.md5()
        try:
            fd = codecs.open(fileName, "rb", 'utf-8')
        except IOError:
            print "Unable to open the file in readmode:", fileName
            return
        content = fd.readlines()
        fd.close()
        for eachLine in content:
            if excludeLine and eachLine.startswith(excludeLine):
                continue
            m.update(eachLine)
        m.update(includeLine)
        return m.hexdigest()

    def lastModifiedAt(self, path):
        return datetime.datetime.utcfromtimestamp(os.path.getmtime(path))

    def setLastModifiedAt(self, path, date):
        try:
            stinfo = os.stat(path)
            atime = stinfo.st_atime
            mtime = int(time.mktime(date.timetuple()))
            os.utime(path, (atime, mtime))
            return True
        except:
            pass

        return False

    def clearDirectory(self, path):
        try:
            for root, _, files in os.walk(path, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
        except:
            return False

        return True

    def GetHashofDirs(self, directory, verbose=0):

        SHAhash = hashlib.sha1()
        if not os.path.exists(directory):
            return -1

        try:
            for root, _, files in os.walk(directory):
                for names in files:
                    if verbose == 1:
                        print 'Hashing', names
                    filepath = os.path.join(root, names)
                    try:
                        f1 = codecs.open(filepath, 'rb', 'utf-8')
                    except:
                        # You can't open the file for some reason
                        f1.close()
                        continue

            while 1:
                # Read file in as little chunks
                buf = f1.read(4096)
                if not buf:
                    break
                SHAhash.update(hashlib.sha1(buf).hexdigest())
                f1.close()

        except:
            import traceback
            # Print the stack traceback
            traceback.print_exc()
            return -2
        # GetHashofDirs - http://akiscode.com/articles/sha-1directoryhash.shtml
        # Copyright (c) 2009 Stephen Akiki
        # MIT License (Means you can do whatever you want with this)
        #  See http://www.opensource.org/licenses/mit-license.php
        return SHAhash.hexdigest()


# ------------------------------------------------------------------------------
class BaseRequest(object):
    ''' HTTP REQUEST HELPER cooking handling, call BaseRequest.getSource(url,form_data,referer) '''

    def __init__(self, cookie_file=None):
        self._regex = r'<a href="([^"]*)".*?<img.+src="([^"]*)".+alt="([^"]*)".+?>.*?/a>'
        self._fileUtils = FileUtils()
        self.fileExists = self._fileUtils.fileExists
        self.setFileContent = self._fileUtils.setFileContent
        self.getFileContent = self._fileUtils.getFileContent
        self.cookietemplate = '#LWP-Cookies-2.0'
        if cookie_file is None:
            cookie_file = 'cookies.lwp'
            self.setFileContent(cookie_file, self.cookietemplate)
        self.cookie_file = cookie_file
        self.head = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/46.0.2490.71 Safari/537.36'}
        self.head.update({'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'})
        self.head.update({'Accept-Language': 'en-US,en;q=0.5'})
        try:
            self.s = requests.Session()
            if self.fileExists(self.cookie_file):
                self.s.cookies = self.load_cookies_from_lwp(self.cookie_file)
            self.s.headers.update(self.head)
            self.s.keep_alive = False
        except:
            pass
        self.url = ''

    def save_cookies_lwp(self, cookiejar, filename):
        lwp_cookiejar = cookielib.LWPCookieJar()
        for c in cookiejar:
            args = dict(vars(c).items())
            args['rest'] = args['_rest']
            del args['_rest']
            c = cookielib.Cookie(**args)
            lwp_cookiejar.set_cookie(c)
        lwp_cookiejar.save(filename, ignore_discard=True)

    def load_cookies_from_lwp(self, filename):
        lwp_cookiejar = cookielib.LWPCookieJar()
        lwp_cookiejar.load(filename, ignore_discard=True)
        return lwp_cookiejar

    def fixurl(self, url):
        # url is unicode (quoted or unquoted)
        try:
            # url is already quoted
            url = url.encode('ascii')
        except:
            # quote url if it is unicode
            parsed_link = urlparse.urlsplit(url)
            parsed_link = parsed_link._replace(netloc=parsed_link.netloc.encode('idna'),
                                               path=urllib.quote(parsed_link.path.encode('utf-8')))
            url = parsed_link.geturl().encode('ascii')
        # url is str (quoted)
        self.url = url
        return url

    def getSource(self, url, form_data="", referer="", xml=False, mobile=False):
        url = self.fixurl(url)
        if len(referer) < 1 or referer is None:
            referer = 'http://' + urlparse.urlsplit(url).hostname
        if 'arenavision.in' in urlparse.urlsplit(url).netloc:
            self.s.headers.update({'Cookie': 'beget=begetok'})
        if 'pushpublish' in urlparse.urlsplit(url).netloc:
            del self.s.headers['Accept-Encoding']

        if not referer:
            referer = url
        else:
            referer = self.fixurl(referer)

        headers = {'Referer': referer}
        if mobile:
            self.s.headers.update({'User-Agent': 'Mozilla/5.0 (Linux; Android 4.4.2; Nexus 4 Build/KOT49H) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/34.0.1847.114 Mobile Safari/537.36'})

        if xml:
            headers['X-Requested-With'] = 'XMLHttpRequest'

        if form_data and form_data != '':
            r = self.s.post(url, headers=headers, data=form_data, timeout=20)
            response = r.text
        else:
            try:
                r = self.s.get(url, headers=headers, timeout=20)
                response = r.text
            except (requests.exceptions.MissingSchema):
                response = 'pass'

        if len(response) > 10:
            if self.cookie_file:
                self.save_cookies_lwp(self.s.cookies, self.cookie_file)
        return HTMLParser().unescape(response)

    def getThumbs(self, url, regex=""):
        html = self.getSource(url)
        iregex = ur'[(<p)|(<div)|(<span)](.*?href=.*?<img.*?[(</a)|(</p)|(</div)|(</span)].+[^>])'
        if regex == "": regex = self._regex
        matches = re.compile(regex, re.IGNORECASE + re.DOTALL + re.MULTILINE + re.UNICODE).findall(html)
        vblocks = re.compile(iregex, re.IGNORECASE + re.DOTALL + re.MULTILINE + re.UNICODE).findall(html)
        allmatches = []
        listvids = []
        if vblocks is None:
            matchresult = dict(html=html, videos={}, matches=matches)
            matchresult.setdefault(matchresult.keys()[0])
            return matchresult
        else:
            for vid in vblocks:
                vmatch = re.compile(ur'href="([^"]+)".*?src="([^"]+)".+?alt="([^"]+)"',
                                    re.IGNORECASE + re.DOTALL + re.MULTILINE + re.UNICODE).findall(vid)
                if vmatch is not None:
                    vids = []
                    for m1, m2, m3 in vmatch:
                        link = m1
                        img = m2
                        text = m3
                        dictvid = dict(url=link, thumb=img, label=text)
                        dictvid.setdefault(dictvid.keys()[0])
                        vids.append(dictvid)
                    listvids.extend(vids)
        return html, self._cleanlist(listvids) #matchresult

    def _cleanlist(self, listvids):
        resultlist = []
        for vid in listvids:
            assert isinstance(vid, dict)
            vid.setdefault(vid.keys()[0])
            url = HTMLParser().unescape(vid.get('url'))
            thumb = HTMLParser().unescape(vid.get('thumb'))
            label = HTMLParser().unescape(vid.get('label'))
            upr = urlparse.urlparse(self.url)
            vbase = upr.scheme + '://' + upr.netloc + '/'
            if not url.startswith('http'):
                url = urlparse.urlparse(vbase + url.lstrip('/')).geturl()
            if not thumb.startswith('http'):
                thumb = urlparse.urlparse(vbase + thumb.lstrip('/')).geturl()
            if thumb.endswith('.jpg') or thumb.endswith('.png') or thumb.endswith('.jpeg'):
                newvid = dict(url=url, thumb=thumb, label=label)
                newvid.setdefault(newvid.keys()[0])
                resultlist.append(newvid)
        return resultlist


# ------------------------------------------------------------------------------
class DemystifiedWebRequest(BaseRequest):
    def __init__(self, cookiePath):
        super(DemystifiedWebRequest, self).__init__(cookiePath)

    def getSource(self, url, form_data='', referer='', xml=False, mobile=False, demystify=False):
        data = super(DemystifiedWebRequest, self).getSource(url, form_data, referer, xml, mobile)
        if not data:
            return None

        if not demystify:
            # remove comments
            r = re.compile('<!--.*?(?!//)--!*>', re.IGNORECASE + re.DOTALL + re.MULTILINE)
            m = r.findall(data)
            if m:
                for comment in m:
                    data = data.replace(comment, '')
        else:
            import decryptionUtils as crypt
            data = crypt.doDemystify(data)

        return data


# ------------------------------------------------------------------------------
class CachedWebRequest(DemystifiedWebRequest):
    def __init__(self, cookiePath, cachePath):
        super(CachedWebRequest, self).__init__(cookiePath)
        self._fileUtils = FileUtils()
        self.cachePath = cachePath
        self.cachedSourcePath = os.path.join(self.cachePath, 'page.html')
        self.currentUrlPath = os.path.join(self.cachePath, 'currenturl')
        self.lastUrlPath = os.path.join(self.cachePath, 'lasturl')

    def __setLastUrl(self, url):
        self._fileUtils.setFileContent(self.lastUrlPath, url)

    def __getCachedSource(self):
        try:
            data = self._fileUtils.getFileContent(self.cachedSourcePath)
        except:
            pass
        return data

    def getLastUrl(self):
        return self._fileUtils.getFileContent(self.lastUrlPath)

    def getSource(self, url, form_data='', referer='http://www.google.com', xml=False, mobile=False, ignoreCache=False,
                  demystify=False):
        filepart = url.rpartition('/')[-1] + '.html'
        self.cachedSourcePath = self.cachedSourcePath.replace('.html', '-') + filepart
        if url == self.getLastUrl() and not ignoreCache:
            data = self.__getCachedSource()
        elif os.path.exists(self.cachedSourcePath):
            data = self.__getCachedSource()
        else:
            data = super(CachedWebRequest, self).getSource(url, form_data, referer, xml, mobile, demystify)
            if data:
                # Cache url
                self.__setLastUrl(url)
                # Cache page
                self._fileUtils.setFileContent(self.cachedSourcePath, data)
        return data

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# END OF WEBUTILS HELPER CLASSES
# ------------------------------------------------------------------------------
