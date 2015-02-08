# pygooglesearch

This is a fork of [https://github.com/735tesla/pygooglesearch](https://github.com/735tesla/pygooglesearch)

##Python google search module

A while ago I was disappointed to see that pygoogle no longer worked because of google got rid of their SOAP api.

This is my replacement solution. It makes get requests that look like the ones your browser makes and then parses html responses using BeautifulSoup to find results and next page links.

It is also multithreaded.

A requirement of this program is the python requests module.


Example:

```python
from pygooglesearch import googlesearch as gs

search_string = "fish and cat"
myproxy = {'ip': '192.168.0.1', 'port': 3128}
searcher = gs.GoogleSearcher(proxy=proxy)
result = searcher.do_single_search(search_string, 20)
print result
```
