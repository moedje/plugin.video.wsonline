# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os.path as path
import json
import re
import urllib
from urllib import quote_plus
import ssl
import requests
from unidecode import unidecode
import webutil as WebUtils
from xbmcswift2 import Plugin, xbmc, ListItem, download_page, clean_dict, SortMethod

plugin = Plugin()
ssl._create_default_https_context = ssl._create_unverified_context
__BASEURL__ = u'https://watchseries-online.pl'
__addondir__ = xbmc.translatePath(plugin.addon.getAddonInfo('path'))
__datadir__ = xbmc.translatePath('special://profile/addon_data/{0}/'.format(plugin.id))
__cookie__ = path.join(__datadir__, 'cookies.lwp')
__temp__ = path.join(__datadir__, 'temp/')
__resdir__ = path.join(__addondir__, 'resources')
__imgsearch__ = path.join(__resdir__, 'search.png')
__savedjson__ = path.join(xbmc.translatePath(plugin.addon.getAddonInfo('profile')), 'savedshows.json')
getWeb = WebUtils.CachedWebRequest(path.join(__datadir__, 'cookies.lwp'), __temp__)
#getWeb = WebUtils.BaseRequest(path.join(__datadir__, 'cookies.lwp'))


def loadsaved():
    sitems = []
    litems = []
    items = []
    savedpath = ''
    try:
        savedpath = path.join(__datadir__, "saved.json")
        if path.exists(savedpath):
            fpin = file(savedpath)
            rawjson = fpin.read()
            sitems = json.loads(rawjson)
            fpin.close()
        else:
            return []
        for item in sitems:
            li = ListItem.from_dict(**item)
            li.add_context_menu_items(
                [('Remove Saved Show', 'RunPlugin("{0}")'.format(plugin.url_for(removeshow, name=li.label, link=li.path)),)])
            litems.append(li)
    except:
        pass
    return litems


def makecatitem(name, link, removelink=False):
    item = {}
    ctxitem = {}
    itempath = plugin.url_for(category, name=name, url=link)
    item = {'label': name, 'label2': link, 'icon': 'DefaultFolder.png', 'thumbnail': 'DefaultFolder.png', 'path': itempath}
    item.setdefault(item.keys()[0])
    litem = ListItem.from_dict(**item)
    #if removelink:
    #    litem.add_context_menu_items([('Remove Saved Show', 'RunPlugin("{0}")'.format(plugin.url_for(removeshow, name=name, link=itempath)),)])
    #else:
    litem.add_context_menu_items([('Save Show', 'RunPlugin("{0}")'.format(plugin.url_for(saveshow, name=name, link=link)),)])
    return litem


def DL(url):
    html = u''
    getWeb = WebUtils.CachedWebRequest(__cookie__, __temp__)
    html = getWeb.getSource(url, form_data=None, referer=__BASEURL__, xml=False, mobile=False).encode('latin', errors='ignore')
    return html


def formatshow(name=""):
    epname = name.replace('&#8211;', '-')
    epnum = ''
    epname = ''
    epdate = ''
    numparts = re.compile(r'[Ss]\d+[Ee]\d+').findall(name)
    if len(numparts) > 0:
        epnum = numparts.pop()
    datematch = re.compile(r'[12][0-9][0-9][0-9].[0-9][0-9]?.[0-9][0-9]?').findall(name)
    if len(datematch) > 0:
        epdate = datematch[0]
    name = name.replace('  ', ' ').strip()
    name = name.replace(epnum, '').strip()
    name = name.replace(epdate, '').strip()
    if epdate == '':
        # Let's see if we can find the date in the form of a string of Month_Abbr Daynum Year
        try:
            from calendar import month_abbr, month_name
            monthlist = month_name[:]
            monthlist.extend(month_abbr)
            monthlist.pop(13)
            monthlist.pop(0)
            regex = "{0}.(\d\d).(\d\d\d\d)"
            nummonth = 1
            for mon in monthlist:
                matches = re.compile(regex.format(mon)).findall(name)
                if len(matches) > 0:
                    day, year = matches.pop()
                    if nummonth < 10:
                        epdate = "{0} 0{1} {2}".format(year, nummonth, day)
                    else:
                        epdate = "{0} {1} {2}".format(year, nummonth, day)
                    name = name.replace(mon, '').strip()
                    name = name.replace(year, '').strip()
                    name = name.replace(day, '').strip()
                    break
                nummonth += 1
                if nummonth > 12: nummonth = 1
            if epdate == '':
                year = re.split(r'\d\d\d\d', name, 1)[0]
                epdate = name.replace(year, '').strip()
                name = name.replace(epdate, '').strip()
        except:
            pass
    epname = name.replace('(','').replace(')','').strip()
    epdate = epdate.replace('(','').replace(')','').strip()
    epnum = epnum.replace('(','').replace(')','').strip()
    return epname.strip(), epdate.strip(), epnum.strip()


def formatlabel(epname, epdate, epnum):
    eplbl = ''
    epname = epname.replace('!', '')
    try:
        if len(epdate) == 0 and len(epnum) == 0:
            return epname
        else:
            if len(epdate) > 0 and len(epnum) > 0:
                eplbl = "{0} ([COLOR blue]{1}[/COLOR] [COLOR cyan]{2}[/COLOR])".format(epname, epdate, epnum)
            else:
                if len(epdate) > 0:
                    eplbl = "{0} ([COLOR blue]{1}[/COLOR])".format(epname, epdate)
                else:
                    eplbl = "{0} ([COLOR cyan]{1}[/COLOR])".format(epname, epnum)
    except:
        eplbl = epname + ' ' + epdate + ' ' + epnum
    return eplbl


def findepseason(epnum):
    numseason = ''
    numep = ''
    parts = epnum.lower().split('e', 1)
    numseason = parts[0].replace('s', '').strip()
    numep = parts[-1].replace('e', '').strip()
    return numseason, numep


def episode_makeitem(episodename, episodelink, dateadded=None):
    '''
    Will return a ListItem for the given link to an episode and it's full linked name.
    Name will be sent to format show to attempt to parse out a date or season from the title.
    Infolabels are populated with any details that can be parsed from the title as well.
    Should be used anytime an item needs to be created that is an item for one specific episode of a show.
    Latest 350, Saved Show, Category (Show listing of all episodes for that series) would all use this.
    '''
    infolbl = {}
    spath = plugin.url_for(episode, name=episodename, url=episodelink)
    img = "DefaultVideoFolder.png"
    seasonstr = ''
    try:
        eptitle, epdate, epnum = formatshow(episodename)
        eplbl = formatlabel(eptitle, epdate, epnum)
        plotstr = "{0} ({1}): {2} {3}".format(epdate, epnum, eptitle, episodelink)
        infolbl = {'EpisodeName': epdate, 'Title': eptitle, 'Plot': plotstr}
        if len(epnum) > 0:
            showS, showE = findepseason(epnum)
            snum = int(showS)
            epnum = int(showE)
            infolbl.update({'Episode': showE, 'Season': showS})
            if snum > 0 and epnum > 0:
                epdate = "S{0}e{1}".format(snum, epnum)
                infolbl.update({'PlotOutline': epdate})
        if dateadded is not None:
            dateout = dateadded.replace(' ', '-').trim()
            eplbl += " [I][B][LIGHT]{0}[/LIGHT][/B][/I]".format(dateout)
            infolbl.update({"Date": dateout})
        item = {'label': eplbl, 'label2': epdate, 'icon': img, 'thumbnail': img, 'path': spath}
        item.setdefault(item.keys()[0])
        li = ListItem.from_dict(**item)
        li.set_info(type='video', info_labels=infolbl)
    except:
        li = ListItem(label=episodename, label2=episodelink, icon=img, thumbnail=img, path=spath)
    return li


def findvidlinks(html=''):
    matches = re.compile(ur'<div class="play-btn">.*?</div>', re.DOTALL).findall(html)
    vids = []
    for link in matches:
        url = re.compile(ur'href="(.+)">', re.DOTALL+re.S).findall(str(link))[0]
        if url is not None:
            host = str(url.lower().split('://', 1)[-1])
            host = host.replace('www.', '')
            host = str(host.split('.', 1)[0]).title()
            label = "{0} [COLOR blue]{1}[/COLOR]".format(host, url.rpartition('/')[-1])
            vids.append((label, url,))
    return vids


def sortSourceItems(litems=[]):
    try:
        litems.sort(key=lambda litems: litems['label'], reverse=False)
        sourceslist = []
        stext = plugin.get_setting('topSources')
        if len(stext) < 1:
            sourceslist.append('streamcloud')
            sourceslist.append('movpod')
            sourceslist.append('thevideo')
        else:
            sourceslist = stext.split(',')
        sorteditems = []
        for sortsource in sourceslist:
            for item in litems:
                if str(item['label2']).find(sortsource) != -1: sorteditems.append(item)
        for item in sorteditems:
            try:
                litems.remove(item)
            except:
                pass
        sorteditems.extend(litems)
        return sorteditems
    except:
        plugin.notify(msg="ERROR SORTING: #{0}".format(str(len(litems))), title="Source Sorting", delay=20000)
        return litems


@plugin.route('/')
def index():
    litems = []
    plugin.set_content('episodes')
    itemlatest = {'label': 'Last 350 Episodes', 'icon': 'DefaultFolder.png', 'thumbnail': 'DefaultFolder.png', 'path': plugin.url_for(latest)}
    itemsaved = {'label': 'Saved Shows', 'path': plugin.url_for(saved), 'icon': 'DefaultFolder.png', 'thumbnail': 'DefaultFolder.png'}
    itemplay = {'label': 'Resolve URL and Play (URLresolver required)', 'path': plugin.url_for(playurl), 'icon': 'DefaultFolder.png', 'thumbnail': 'DefaultFolder.png'}
    itemsearch = {'label': 'Search', 'icon': __imgsearch__, 'thumbnail': __imgsearch__, 'path': plugin.url_for(search, dopaste=bool(False))}
    # itemsearchpasted = {'label': 'Search (Paste Clipboard)', 'icon': __imgsearch__, 'thumbnail': __imgsearch__, 'path': plugin.url_for(search, paste=True)}
    litems.append(itemlatest)
    litems.append(itemsaved)
    litems.append(itemsearch)
    #litems.append(itemsearchpasted)
    litems.append(itemplay)
    return litems


@plugin.route('/playurl')
def playurl():
    url = ''
    url = plugin.keyboard(default='', heading='Video Page URL')
    if url != '' and len(url) > 0:
        item = ListItem.from_dict(path=plugin.url_for(endpoint=play, url=url))
        item.set_is_playable(True)
        item.set_info(type='video', info_labels={'Title': url, 'Plot': url})
        item.add_stream_info(stream_type='video', stream_values={})
        return play(url)


@plugin.route('/saved')
def saved():
    litems = []
    sitems = []
    sitems = loadsaved()
    noitem = {'label': "No Saved Shows", 'icon': 'DefaultFolder.png', 'path': plugin.url_for('index')}
    if len(sitems) < 1:
        return [noitem]
    else:
        return sitems


@plugin.route('/saveshow/<name>/<link>')
def saveshow(name='', link=''):
    sitems = []
    litems = []
    try:
        savedpath = path.join(__datadir__, "saved.json")
        if path.exists(savedpath):
            fpin = file(savedpath)
            rawjson = fpin.read()
            sitems = json.loads(rawjson)
            fpin.close()
        saveitem = {'label': name, 'path': plugin.url_for(endpoint=category, name=name, url=link)}
        saveitem.setdefault(saveitem.keys()[0])
        sitems.insert(0, saveitem)
        fpout = file(savedpath, mode='w')
        json.dump(sitems, fpout)
        fpout.close()
        plugin.notify(msg="SAVED {0}".format(name), title=link)
    except:
        plugin.notify(msg="ERROR save failed for {0}".format(name), title=link)


@plugin.route('/saveshowfromepisode/<name>/<link>')
def saveshowfromepisode(name='', link=''):
    '''
    Loads the episode page and searches html for the category for the entire show not this specific episode to then save the show using the same show function used when we alreaedy know the category.
    <span class="info-category"><a href="https://watchseries-online.pl/category/late-night-with-seth-meyers" rel="category tag">Late Night with Seth Meyers</a></span>
    '''
    html = DL(link)
    matches = re.compile(ur'span class="info-category">.+?href="(http.+?[^"])".+?>(.+?[^<])</a>', re.DOTALL+re.S+re.U).findall(html)
    litems = []
    categorylink = ''
    showname = ''
    if matches is not None:
        for showlink, catname in matches:
            categorylink = showlink
            showname = catname
        saveshow(name=showname, link=categorylink)


@plugin.route('/removeshow/<name>/<link>')
def removeshow(name='', link=''):
    sitems = []
    litems = []
    sitems = loadsaved()
    for item in sitems:
        if item.get('name') == name or item.get('link') == link:
            plugin.notify(title='Removed {0}'.format(name), msg='Removed "{0}": {1}'.format(name, link))
        else:
            litems.append(item)
    jsout = json.dumps(litems)
    plugin.addon.setSetting('savedshows', jsout)
    plugin.notify(title='Removed {0}'.format(name), msg='{0} Removed Show link: {1}'.format(name, link))


@plugin.route('/latest')
def latest():
    url = __BASEURL__ + '/last-350-episodes'
    fullhtml = DL(url)
    html = fullhtml.partition("</nav>")[-1].split("</ul>",1)[0]
    strDate = ur"<li class='listEpisode'>(\d+ \d+ \d+) : "
    strUrl = ur'<a.+?href="([^"]*?)">'
    strName = ur'</span>([^<]*?)</a>' # reDate = re.compile(strDate) #ur"<li class='listEpisode'>(\d+ \d+ \d+) :") reUrl = re.compile(strUrl) #ur'<a.+?href="([^"]*?)">') reName = re.compile(strName) #ur'</span>([^<]*?)</a>')
    regexstr = "{0}{1}.+?{2}".format(strDate, strUrl, strName) 
    matches = re.compile(regexstr).findall(html)    
    litems = []
    epdate = ''
    eptitle = ''
    for dateadd, eplink, epname in matches:
        if not filterout(epname):
            item = episode_makeitem(epname, eplink, dateadded=dateadd)
            item.set_path(plugin.url_for(episode, name=epname, url=eplink))
            litems.append(item)
    return litems


def filterout(text):
    filterwords = []
    filtertxt = plugin.get_setting('filtertext')
    if len(filtertxt) < 1:
        return False
    if filtertxt.find(',') != -1:
        filterwords = filtertxt.split(',')
    else:
        return False
    for word in filterwords:
        if text.lower().find(word.lower()) != -1:
            return True
    return False


@plugin.route('/search/<dopaste>')
def search(dopaste):
    searchtxt = plugin.get_setting('lastsearch')
    if dopaste is None:
        dopaste = False
    elif dopaste:
        try:
            import pyperclip
            searchtxt = pyperclip.paste()
            plugin.notify("Searching: " + str(dopaste), searchtxt)
            if len(searchtxt) > 50:
                nsearchtxt = searchtxt[0:50]
                searchtxt = searchtxt.replace(nsearchtxt, '').split(' ', 1)[0]
        except:
            searchtxt = plugin.get_setting('lastsearch')
    else:
        searchtxt = plugin.get_setting('lastsearch')
    searchtxt = plugin.keyboard(searchtxt, 'Search All Sites', False)
    if len(searchtxt) > 1:
        plugin.set_setting(key='lastsearch', val=searchtxt)
        return query(searchquery=searchtxt)
    else:
        return []


@plugin.route('/query/<searchquery>')
def query(searchquery):
    if searchquery.find(' ') != -1:
        searchquery = searchquery.replace(' ', '+')
    urlsearch = __BASEURL__ + '/?s={0}&search='.format(quote_plus(searchquery))
    html = DL(urlsearch)
    htmlres = html.partition('<div class="ddmcc">')[2].split('</div>',1)[0]
    matches = re.compile(ur'href="(https?.+?watchseries-online\.[a-z]+/category.+?[^"])".+?[^>]>(.+?[^<])<.a>', re.DOTALL + re.S + re.U).findall(htmlres)
    litems = []
    for slink, sname in matches:
        litems.append(makecatitem(sname, slink))
    plugin.notify(msg="Search {0}".format(urlsearch), title="{0} {1}".format(str(len(litems)), searchquery))
    #plugin.ad(litems, update_listing=True)
    return litems
    #return plugin.finish()


@plugin.route('/queryshow/<searchquery>')
def queryshow(searchquery):
    plugin.clear_added_items()
    plugin.add_items(items=query(searchquery))
    return plugin.finish(update_listing=True) # plugin.redirect(url=plugin.url_for(query, searchquery=searchquery))


@plugin.route('/category/<name>/<url>')
def category(name, url):
    fullhtml = DL(url)
    html = fullhtml.partition("</nav>")[-1].split("</ul>",1)[0]
    strDate = ur"<li class='listEpisode'>(\d+ \d+ \d+) : "
    strUrl = ur'<a.+?href="([^"]*?)">'
    strName = ur'</span>([^<]*?)</a>'
    reDate = re.compile(strDate) #ur"<li class='listEpisode'>(\d+ \d+ \d+) :")
    reUrl = re.compile(strUrl) #ur'<a.+?href="([^"]*?)">')
    reName = re.compile(strName) #ur'</span>([^<]*?)</a>')
    regexstr = "{0}{1}.+?{2}".format(strDate, strUrl, strName) 
    banner = None
    try:
        banner = str(html.split('id="banner_single"', 1)[0].rpartition('src="')[2].split('"',1)[0])
        if banner.startswith('/'): banner = __BASEURL__ + banner
    except:
        pass
    if banner is None: banner = 'DefaultVideoFolder.png'
    matches = re.compile(ur"href='(https?.+watchseries-online.[a-z]+/episode.+?[^'])'.+?</span>(.+?[^<])</a>", re.DOTALL + re.S + re.U).findall(html)
    litems =[]
    for eplink, epname in matches:
        item = episode_makeitem(epname, eplink)
        item.path = plugin.url_for(episode, name=epname, url=eplink)
        litems.append(item)
    litems.sort(key=lambda litems : litems.label, reverse=True)
    return litems


@plugin.route('/episode/<name>/<url>')
def episode(name, url):
    html = DL(url)
    litems = []
    linklist = findvidlinks(html)
    itemparent = None
    if len(linklist) > 0:
        for name, link in linklist:
            itempath = plugin.url_for(play, url=link)
            item = dict(label=name, label2=link, icon='DefaultFolder.png', thumbnail='DefaultFolder.png', path=itempath)
            item.setdefault(item.keys()[0])
            litems.append(item)
        vitems = sortSourceItems(litems)
        litems = []
        for li in vitems:
            item = ListItem.from_dict(**li)
            item.set_is_playable(True)
            item.set_info(type='video', info_labels={'Title': item.label, 'Plot': item.label2})
            item.add_stream_info(stream_type='video', stream_values={})
            litems.append(item)
    else:
        plugin.notify(title="ERROR No links: {0}".format(name), msg=url)
    return litems


@plugin.route('/play/<url>')
def play(url):
    resolved = ''
    stream_url = ''
    item = None
    try:
        import urlresolver
        resolved = urlresolver.HostedMediaFile(url).resolve()
        if not resolved or resolved == False or len(resolved) < 1:
            resolved = urlresolver.resolve(url)
            if resolved is None or len(resolved) < 1:
                resolved = urlresolver.resolve(urllib.unquote(url))
        if len(resolved) > 1:
            plugin.notify(msg="PLAY {0}".format(resolved.partition('.')[-1]), title="URLRESOLVER", delay=1000)
            plugin.set_resolved_url(resolved)
            item = ListItem.from_dict(path=resolved)
            item.add_stream_info('video', stream_values={})
            item.set_is_playable(True)
            return item
    except:
        resolved = ''
        plugin.notify(msg="FAILED {0}".format(url.partition('.')[-1]), title="URLRESOLVER", delay=1000)
    try:
        import YDStreamExtractor
        info = YDStreamExtractor.getVideoInfo(url, resolve_redirects=True)
        resolved = info.streamURL()
        for s in info.streams():
            try:
                stream_url = s['xbmc_url'].encode('utf-8', 'ignore')
                xbmc.log(msg="**YOUTUBE-DL Stream found: {0}".format(stream_url))
            except:
                pass
        if len(stream_url) > 1:
            resolved = stream_url
        if len(resolved) > 1:
            plugin.notify(msg="Playing: {0}".format(resolved.partition('.')[-1]), title="YOUTUBE-DL", delay=1000)
            plugin.set_resolved_url(resolved)
            item = ListItem.from_dict(path=resolved)
            item.add_stream_info('video', stream_values={})
            item.set_is_playable(True)
            return item
    except:
        plugin.notify(msg="Failed: {0}".format(resolved.partition('.')[-1]), title="YOUTUBE-DL", delay=1000)

    if len(resolved) > 1:
        plugin.set_resolved_url(resolved)
        item = ListItem.from_dict(path=resolved)
        return item
    else:
        plugin.set_resolved_url(url) #url)
        #plugurl = 'plugin://plugin.video.live.streamspro/?url={0}'.format(urllib.quote_plus(url))
        #item = ListItem.from_dict(path=plugurl)
        #item.add_stream_info('video', stream_values={})
        #item.set_is_playable(True)
        #plugin.notify(msg="RESOLVE FAIL: {0}".format(url.split('.', 1)[-1]),title="Trying {0}".format(item.path.split('.', 1)[-1]), delay=2000)
        return None


if __name__ == '__main__':
    hostname = ''
    hostname = plugin.get_setting('setHostname')
    if len(hostname) > 1:
        hostname = hostname.strip()
        hostname = hostname.strip('/')
        if str(hostname).startswith('http'):
            __BASEURL__ = hostname
        else:
            __BASEURL__ = 'https://' + hostname
    plugin.run()
    plugin.set_content('episodes')
    plugin.set_view_mode(0)
