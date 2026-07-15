import requests
from bs4 import BeautifulSoup, Comment
import urllib.parse
import json

keyword = '北京'
url = f'https://www.baidu.com/s?rtt=1&bsst=1&cl=2&tn=news&rsv_dl=ns_pc&word={urllib.parse.quote(keyword)}&pn=0'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Cookie': 'BAIDUID=8A9A2116228B24C21CB8F516B31237EA:FG=1;'
}
res = requests.get(url, headers=headers)
res.encoding = 'utf-8'
soup = BeautifulSoup(res.text, 'html.parser')

items = soup.find_all('div', class_='result-op')
results = []
for item in items:
    # 查找 HTML 注释
    comments = item.find_all(string=lambda text: isinstance(text, Comment))
    for c in comments:
        if c.startswith('s-data:'):
            try:
                data_str = c[len('s-data:'):]
                data = json.loads(data_str)
                title = data.get('title', '').replace('<em>', '').replace('</em>', '')
                url = data.get('titleUrl', '')
                summary = data.get('summary', '').replace('<em>', '').replace('</em>', '')
                source = data.get('sourceName', '')
                time = data.get('dispTime', '')
                
                if title and url and summary:
                    results.append({
                        'title': title,
                        'url': url,
                        'summary': summary,
                        'source': source,
                        'time': time
                    })
            except Exception as e:
                pass

print(f"Extracted {len(results)} items using s-data JSON:")
for r in results[:3]:
    print(r)
