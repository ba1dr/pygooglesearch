#!/usr/bin/env python
# Created by Tesla on January 20, 2015
# Module for searching google, multithreaded
# There are no commments and I didn't write any documentation, so just read the code
# The only class you'll need to use is GoogleSearcher (lines 93-113)
import os
import requests
import time
import urllib
import multiprocessing
import threading
import random
from BeautifulSoup import BeautifulSoup

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'useragents.txt'), 'r') as uaf:
    uatxt = uaf.read()

USER_AGENTS = uatxt.split("\n")

DEFAULT_GOOGLE = "google.com"


class SearchError(Exception):
    pass


def normalize_proxy(proxy):
    """ Returns proxy in the request's format
        Only HTTP proxies supported yet - requesocks can be used
    """
    if not proxy:
        return None
    p = None
    if isinstance(proxy, (str, unicode)):  # just string like '192.168.0.1:3128'
        if not (proxy.startswith('http://') or proxy.startswith('https://')):  # proxy should include protocol
            p = {'http': "http://%s" % proxy, 'https': "http://%s" % proxy}
        else:
            p = {'http': proxy, 'https': proxy}
    elif isinstance(proxy, dict):
        dproxy = ""
        host, auth = "", ""
        proto = proxy.get('proto', None) or proxy.get('protocol', None) or proxy.get('type', None) or 'http'
        if proto.lower() in ['socks', 'socks5', 'socks4']:
            raise ValueError("SOCKS proxies are not supported yet")
        for hn in ['ip', 'ipaddress', 'host', 'hostname']:
            if hn in proxy:
                host = proxy.get(hn, '')
                break
        port = proxy.get('port', 3128)
        username = proxy.get('user', None)
        password = proxy.get('pass', None) or proxy.get('password', None)
        if username and password:
            auth = "%s:%s@" % (username, password)
        dproxy = "%s://%s%s:%s" % (proto.lower(), auth, host, port)
        p = {'http': dproxy, 'https': dproxy}
    return p


class ResultPage(BeautifulSoup):
    def __init__(self, html, google=None):
        super(ResultPage, self).__init__(html)
        self.google = google or DEFAULT_GOOGLE
        self.html = html

    def find_next_page_link(self):
        return ('https://www.%s' % self.google) + \
            '{}'.format(self.findAll('div', attrs={'id': 'navcnt'})[0].findAll('a')[0]['href'])

    def find_result_links(self, extended=False):
        result_links = []
        result_divs = self.findAll('div', attrs={'class': 'rc'})
        for result_div in result_divs:
            link = result_div.findAll('a')[0]['href']
            if not extended:
                result_links.append(link)
                continue
            item = {'url': link, 'date': None}
            # search for results date
            rdate = None
            d = result_div.findAll('span', attrs={'class': 'f'})
            if d:
                rdate = d[0].text
            else:
                d = result_div.findAll('div', attrs={'class': 'f slp'})
                if d:
                    rdate = d[0].text
            if rdate:
                rdate = rdate.split(' -')[0]
            item['date'] = rdate
            print item
            result_links.append(item)
        return result_links


class SearchTask(object):
    def __init__(self, query, results, proxy=None, timeout=None, google=None, extended_search=False, debug=False):
        super(SearchTask, self).__init__()
        self.google = google or DEFAULT_GOOGLE
        self.query = query
        self.results = results
        self.debug = debug
        self.extended_search = extended_search
        self.user_agent = ''
        self.proxy = proxy
        self.timeout = timeout or (30, 90)  # requests timeout: tuple(connect, read)
        while not self.user_agent:
            self.user_agent = random.choice(USER_AGENTS)
        self.headers = {
            'User-Agent': self.user_agent,
            'DNT': '1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5'
        }
        self.init_url = ('https://www.%s' % self.google) + \
            '/search?rls=en&q={}&ie=UTF-8&oe=UTF-8&tbs=cdr%3A1%2Ccd_min%3A1980'.format(self.query)
        self.cookies = self.get_cookies()
        self.cookies.update({"x": '222'})

    def _get_response(self, url):
        """ General method for request """
        resp = requests.get(url, headers=self.headers, cookies=self.cookies,
                            proxies=self.proxy, timeout=self.timeout)
        if not resp.ok:
            raise SearchError("HTTP code %s" % resp.status_code)
        if self.debug:
            with open("/tmp/searchresult.txt", 'w') as srw:
                srw.write(resp.text.encode('utf-8'))
        return resp.text

    def get_cookies(self):
        return requests.get('https://www.%s/' % self.google, headers=self.headers, proxies=self.proxy).cookies

    def __call__(self):
        result_urls = []
        time.sleep(random.randint(1, 1000) / 1000.0)
        initial_html = self._get_response(self.init_url)
        initial_result_page = ResultPage(initial_html, google=self.google)
        initial_result_links = initial_result_page.find_result_links(extended=self.extended_search)
        for result_link in initial_result_links:
            result_urls.append(result_link)
        result_page = initial_result_page
        page = 1
        while len(result_urls) < self.results:
            page += 1
            next_url = result_page.find_next_page_link()
            time.sleep(random.randint(1, 1000) / 1000.0)
            html = self._get_response(next_url)
            result_page = ResultPage(html, google=self.google)
            result_links = result_page.find_result_links(extended=self.extended_search)
            if result_links == 0:
                raise SearchError("Received 0 results on page %s!" % page)
            result_urls += result_links
        return result_urls[:self.results]


class ScanEngine(object):
    def __init__(self, pool_size=1):
        super(ScanEngine, self).__init__()
        self.finished = False
        self.pool_size = pool_size
        self.thread_pool = multiprocessing.Pool(pool_size)
        self.result_urls = []
        self.search_tasks = []

    def add_search_task(self, search_task):
        self.search_tasks.append(search_task)

    def run(self):
        threads = []
        for task in self.search_tasks:
            if self.pool_size == 1:
                self.result_urls.extend(task())
            else:
                self.thread_pool.apply_async(task, callback=self.result_urls.extend)
        self.thread_pool.close()
        self.thread_pool.join()
        self.finished = True
        return self.result_urls


class GoogleSearcher(object):
    def __init__(self, pool_size=1, proxy=None, timeout=None, google=None, extended_search=False):
        super(GoogleSearcher, self).__init__()
        self.proxy = normalize_proxy(proxy)
        self.timeout = timeout
        self.google = google
        self.extended = extended_search
        self.pool_size = pool_size
        self.scan_engine = ScanEngine(pool_size=self.pool_size)

    def do_searches_from_file(self, filename, results=10):
        if self.scan_engine.finished:
            self.scan_engine = ScanEngine(pool_size=self.pool_size)
        with open(filename, 'r') as f:
            search_queries = f.read().replace('\r', '')
            while '\n\n' in search_queries:
                search_queries = search_queries.replace('\n\n', '\n')
            search_queries = search_queries.split('\n')
            for search_query in search_queries:
                self.scan_engine.add_search_task(SearchTask(search_query, results, proxy=self.proxy,
                                                            timeout=self.timeout, google=self.google,
                                                            extended_search=self.extended))
        return self.scan_engine.run()

    def do_single_search(self, search_query, results=10):
        if self.scan_engine.finished:
            self.scan_engine = ScanEngine(pool_size=self.pool_size)
        self.scan_engine.add_search_task(SearchTask(search_query, results, proxy=self.proxy,
                                         timeout=self.timeout, google=self.google,
                                         extended_search=self.extended))
        return self.scan_engine.run()
