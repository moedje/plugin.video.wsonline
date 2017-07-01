# -*- coding: utf-8 -*-
import os
import re
import urllib
import datetime, time
import random
import hashlib
import codecs
import urllib2
import urlparse
import cookielib
from HTMLParser import HTMLParser
import requests
#------------------------------------------------------------------------------

class Cleaner(object):

    def __init__(self, text=''):
        self.txt = text
        if len(text) > 0:
            self.cleantext = self.CLEANUP(text)
            self.encodedtext = self.GetEncodeString(text)
            self.nohtml = self.replaceHTMLCodes(text)
            self.notags = self.strip_tags(text)


    def GetEncodeString(self, text=''):
        if text is None or len(text) < 1:
            str = self.txt
        else:
            str = text
        try:
            import chardet
            str = str.decode(chardet.detect(str)["encoding"]).encode("utf-8")
        except:
            try:
                str = str.encode("utf-8")
            except:
                pass
        return str


    def CLEANUP(self, text=''):
        if text is None or len(text) < 1:
            text = self.txt
        text = str(text)
        text = text.replace('\\r','')
        text = text.replace('\\n','')
        text = text.replace('\\t','')
        text = text.replace('\\','')
        text = text.replace('<br />','\n')
        text = text.replace('<hr />','')
        text = text.replace('&#039;',"'")
        text = text.replace('&quot;','"')
        text = text.replace('&rsquo;',"'")
        text = text.replace('&amp;',"&")
        text = text.replace('&#39;',"'")
        text = text.replace('&#8211;',"&")
        text = text.replace('&#8217;',"'")
        text = text.replace('&#038;',"&")
        text = text.lstrip(' ')
        text = text.lstrip('    ')

        return text


    def replaceHTMLCodes(self, text=''):
        # Code from Lambdas ParseDOM file.
        if text is None or len(text) < 1:
            txt = self.txt
        txt = re.sub("(&#[0-9]+)([^;^0-9]+)", "\\1;\\2", txt)
        txt = HTMLParser().unescape(txt)
        txt = txt.replace("&quot;", "\"")
        txt = txt.replace("&amp;", "&")
        txt = txt.strip()
        return txt

    class MLStripper(HTMLParser):
        def __init__(self):
            self.reset()
            self.fed = []
        def handle_data(self, d):
            self.fed.append(d)
        def get_data(self):
            return ''.join(self.fed)

    def strip_tags(self, text):
        if text is None or len(text) < 1:
            html = self.txt
        else:
            html = text
        s = MLStripper()
        s.feed(html)
        return s.get_data()



class FileUtils(object):
    """docstring for FileUtils - File Helpers"""

    def fileExists(self, filename):
        return os.path.isfile(filename)

    def getFileExtension(self, filename):
        ext_pos = filename.rfind('.')
        if ext_pos != -1:
            return filename[ext_pos+1:]
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


    def randomFilename(self, directory, chars = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ', length = 8, prefix = '', suffix = '', attempts = 10000):
        for _ in range(attempts):
            filename = ''.join([random.choice(chars) for _ in range(length)])
            filename = prefix + filename + suffix
            if not os.path.exists(os.path.join(directory, filename)):
                return filename
        return None


    def getFileContent(self, filename):
        try:
            f = codecs.open(filename,'r','utf-8')
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
            f = codecs.open(filename, 'w','utf-8')
            f.write(txt)
            f.close()
            return True
        except:
            return False

    def appendFileContent(self, filename, txt):
        try:
            f = codecs.open(filename, 'a','utf-8')
            f.write(txt)
            f.close()
            return True
        except:
            return False

    def md5(self, fileName, excludeLine="", includeLine=""):
        """Compute md5 hash of the specified file"""
        m = hashlib.md5()
        try:
            fd = codecs.open(fileName,"rb",'utf-8')
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
            for root, _, files in os.walk(path , topdown = False):
                for name in files:
                    os.remove(os.path.join(root, name))
        except:
            return False
        
        return True

    def GetHashofDirs(self, directory, verbose=0):

        SHAhash = hashlib.sha1()
        if not os.path.exists (directory):
            return -1
          
        try:
            for root, _, files in os.walk(directory):
                for names in files:
                    if verbose == 1:
                        print 'Hashing', names
                    filepath = os.path.join(root,names)
                    try:
                        f1 = codecs.open(filepath, 'rb','utf-8')
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
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
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
        self.head = {'User-Agent' : 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/46.0.2490.71 Safari/537.36'}
        self.head.update({'Accept' : 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'})
        self.head.update({'Accept-Language' : 'en-US,en;q=0.5'})
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
        #url is unicode (quoted or unquoted)
        try:
            #url is already quoted
            url = url.encode('ascii')
        except:
            #quote url if it is unicode
            parsed_link = urlparse.urlsplit(url)
            parsed_link = parsed_link._replace(netloc=parsed_link.netloc.encode('idna'),path=urllib.quote(parsed_link.path.encode('utf-8')))
            url = parsed_link.geturl().encode('ascii')
        #url is str (quoted)
        self.url = url
        return url

    def getSource(self, url, form_data="", referer="", xml=False, mobile=False):
        url = self.fixurl(url)
        if len(referer) < 1 or referer is None:
            referer = 'http://' + urlparse.urlsplit(url).hostname
        if 'arenavision.in' in urlparse.urlsplit(url).netloc:
            self.s.headers.update({'Cookie' : 'beget=begetok'})
        if 'pushpublish' in urlparse.urlsplit(url).netloc:
            del self.s.headers['Accept-Encoding']
            
        if not referer:
            referer = url
        else:
            referer = self.fixurl(referer)
        
        headers = {'Referer': referer}
        if mobile:
            self.s.headers.update({'User-Agent' : 'Mozilla/5.0 (Linux; Android 4.4.2; Nexus 4 Build/KOT49H) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/34.0.1847.114 Mobile Safari/537.36'})
            
        if xml:
            headers['X-Requested-With'] = 'XMLHttpRequest'
        
        if form_data:
            r = self.s.post(url, headers=headers, data=form_data, timeout=20)
            response  = r.text
        else:
            try:
                r = self.s.get(url, headers=headers, timeout=20)
                response  = r.text
            except (requests.exceptions.MissingSchema):
                response  = 'pass'
        
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
        if vblocks is None:
            matchresult = dict(html=html, videos={}, matches=matches)
            matchresult.setdefault(matchresult.keys()[0])
            return matchresult            
        else:
            listvids = []
            for vid in vblocks:
                vmatch = re.compile(ur'href="([^"]+)".*?src="([^"]+)".+?alt="([^"]+)"',  re.IGNORECASE + re.DOTALL + re.MULTILINE + re.UNICODE).findall(vid)
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
            matchresult = dict(html=html, videos=self._cleanlist(listvids)) #, matches=vblocks)
            matchresult.setdefault(matchresult.keys()[0])
            return matchresult
        return html
    

    def _cleanlist(self, listvids):
        resultlist = []
        for vid in listvids:
            assert isinstance(vid, dict)
            vid.setdefault(vid.keys()[0])
            url=str(vid.get('url'))
            thumb=str(vid.get('thumb'))
            label=str(vid.get('label'))
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
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
class DemystifiedWebRequest(BaseRequest):

    def __init__(self, cookiePath):
        super(DemystifiedWebRequest,self).__init__(cookiePath)

    def getSource(self, url, form_data, referer='', xml=False, mobile=False, demystify=False):
        data = super(DemystifiedWebRequest, self).getSource(url, form_data, referer, xml, mobile)
        if not data:
            return None

        if not demystify:
            # remove comments
            r = re.compile('<!--.*?(?!//)--!*>', re.IGNORECASE + re.DOTALL + re.MULTILINE)
            m = r.findall(data)
            if m:
                for comment in m:
                    data = data.replace(comment,'')
        else:
            import decryptionUtils as crypt
            data = crypt.doDemystify(data)

        return data
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
class CachedWebRequest(DemystifiedWebRequest):

    def __init__(self, cookiePath, cachePath):
        super(CachedWebRequest,self).__init__(cookiePath)
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
        

    def getSource(self, url, form_data, referer='', xml=False, mobile=False, ignoreCache=False, demystify=False):
        filepart = url.rpartition('/')[-1] + '.html'
        self.cachedSourcePath = self.cachedSourcePath.replace('.html', '-') + filepart
        if url == self.getLastUrl() and not ignoreCache:
            data = self.__getCachedSource()
        elif os.path.exists(self.cachedSourcePath):
            data = self.__getCachedSource()
        else:
            data = super(CachedWebRequest,self).getSource(url, form_data, referer, xml, mobile, demystify)
            if data:
                # Cache url
                self.__setLastUrl(url)
                # Cache page
                self._fileUtils.setFileContent(self.cachedSourcePath, data)
        return data
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
# END OF WEBUTILS HELPER CLASSES
#------------------------------------------------------------------------------
