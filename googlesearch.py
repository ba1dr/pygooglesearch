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


class SearchError(Exception):
    pass


class ResultPage(BeautifulSoup):
    def __init__(self, html):
        super(ResultPage, self).__init__(html)
        self.html = html

    def find_next_page_link(self):
        return 'https://www.google.com{}'.format(self.findAll('div', attrs={'id': 'navcnt'})[0].findAll('a')[0]['href'])

    def find_result_links(self):
        result_links = []
        result_divs = self.findAll('div', attrs={'class': 'rc'})
        for result_div in result_divs:
            result_links.append(result_div.findAll('a')[0]['href'])
        return result_links


class SearchTask(object):
    def __init__(self, query, results):
        super(SearchTask, self).__init__()
        self.cookies = self.get_cookies()
        self.query = query
        self.results = results
        self.user_agent = ''
        while not self.user_agent:
            self.user_agent = random.choice(USER_AGENTS)
        self.headers = {
            'User-Agent': self.user_agent,
            'DNT': '1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5'
        }
        self.init_url = 'https://www.google.com/search?rls=en&q={}&ie=UTF-8&oe=UTF-8'.format(self.query)

    def get_cookies(self):
        return requests.get('https://www.google.com/').cookies

    def __call__(self):
        result_urls = []
        time.sleep(random.randint(1, 1000) / 1000.0)
        initial_resp = requests.get(self.init_url, headers=self.headers, cookies=self.cookies)
        if not initial_resp.ok:
            raise SearchError("HTTP code %s" % initial_resp.status_code)
        initial_html = initial_resp.text
        initial_result_page = ResultPage(initial_html)
        initial_result_links = initial_result_page.find_result_links()
        for result_link in initial_result_links:
            result_urls.append(result_link)
        result_page = initial_result_page
        page = 1
        while len(result_urls) < self.results:
            page += 1
            next_url = result_page.find_next_page_link()
            time.sleep(random.randint(1, 1000) / 1000.0)
            resp = requests.get(next_url, headers=self.headers, cookies=self.cookies)
            if not resp.ok:
                raise SearchError("HTTP code %s" % initial_resp.status_code)
            html = resp.text
            result_page = ResultPage(html)
            result_links = result_page.find_result_links()
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
    def __init__(self, pool_size=1):
        super(GoogleSearcher, self).__init__()
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
                self.scan_engine.add_search_task(SearchTask(search_query, results))
        return self.scan_engine.run()

    def do_single_search(self, search_query, results=10):
        if self.scan_engine.finished:
            self.scan_engine = ScanEngine(pool_size=self.pool_size)
        self.scan_engine.add_search_task(SearchTask(search_query, results))
        return self.scan_engine.run()
