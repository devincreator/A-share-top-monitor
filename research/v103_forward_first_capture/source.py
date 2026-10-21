"""CSI official index-perf source; raw bytes and HTTP headers only."""
import datetime as dt
import hashlib
import urllib.parse
import urllib.request

HOST="www.csindex.com.cn"
PATH="/csindex-home/perf/index-perf"
MAX_BYTES=3000000

def official_url(day):
    end=day-dt.timedelta(days=1)
    start=end-dt.timedelta(days=370)
    query=urllib.parse.urlencode({
        "indexCode":"000985","startDate":start.strftime("%Y%m%d"),
        "endDate":end.strftime("%Y%m%d")})
    return "https://"+HOST+PATH+"?"+query

def fetch(url, opener=urllib.request.urlopen):
    request=urllib.request.Request(url,headers={
        "User-Agent":"Mozilla/5.0","Referer":"https://www.csindex.com.cn/"})
    with opener(request,timeout=20) as response:
        status=response.getcode()
        final_url=response.geturl()
        date_header=response.headers.get("Date")
        last_modified=response.headers.get("Last-Modified")
        etag=response.headers.get("ETag")
        raw=response.read(MAX_BYTES+1)
    return {"status":status,"final_url":final_url,"http_date":date_header,
            "last_modified":last_modified,"etag":etag,
            "sha256":hashlib.sha256(raw).hexdigest(),"size":len(raw)},raw
