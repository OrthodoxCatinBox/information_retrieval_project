# INFO300 Term Project

## 1. Introduction

### 1.1 Data Source

Computerphile is a channel on the video site YouTube that introduces computer science. In each of its videos, a computer science scholar is invited to explain and analyze some interesting or important issues in the field.
On the YouTube video play page, the title, upload date, number of views, likes, comments, and a brief description of the video are displayed, which gives us a general idea of the content and quality (popularity) of the video.
Therefore, using a Web scraping tool, we can build a data set with the theme "Computerphile's lectures uploaded to YouTube", and after filtering, there are 747 legal data items corresponding to the lectures. Using this data, we will try to help viewers find more lectures they need.

### 1.2 Project Architecture

The project consists of three main components: the ElasticSearch search engine, the web backend, and the web frontend.
We build a Web crawler using Scrapy and Selenium to collect needed data from YouTube, and then upload the data to the ElasticSearch search engine and index it.
When a request from a user reaches the web backend, the web backend embeds the request into a pre-written ElasticSearch query, calls the ElasticSearch Python API to send the query to the ElasticSearch search engine, and processes the results returned by the search engine into a form usable for the web frontend.
The final appearance of the web page presented to the user is controlled by the web front-end, and this part needs to be adjusted to include the trade-offs of the content presented in the web page, the style of the web page, and the logic of the web page operations.

### 1.3 Division of Work

- 余正阳: 前端编程，Flask后端编程，评估系统性能
- 胡纪甚: 数据录入，web后端编程
- Chuanshi Wang: data collection, data cleaning、writing ElasticSearch queries

## 2. Data Collection

### 2.1 Tools Introduction

We use a Web scraping tool Scrapy to obtain the data needed for the project from the Internet. Since the website we want to crawl, YouTube, uses JavaScript to render pages dynamically, the HTML returned by the website does not contain most of the information presented in the web page. To solve the problem of getting dynamic webpage content, we utilized Selenium.
Selenium is an automated testing tool that can be used to drive the browser with Python code to perform clicks, dropdowns, and other actions to trigger some callbacks in the web page to render the desired content; after rendering, the Python program can also get the loaded HTML through Selenium, thus solving the problem of getting content from dynamic web pages. With the help of Selenium to load dynamic pages, Scrapy can handle the content in dynamic pages as if they were static pages.

### 2.2 Codes and Explanation

In order to create a Scrapy project, it is needed to run the following command firstly:

```shell
scrapy startproject computerphile
```

In order to make the project run, it is needed to create the file `computerphile.py` in the `spider` directory, which defines `ComputerphileSpider`, the subclass of `scrapy.Spider` and Spider needed for this crawling task. `computerphile.py` contains the following contents:

```python
import re
import time
import scrapy
from selenium import webdriver
from scrapy.http import HtmlResponse
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


class ComputerphileSpider(scrapy.Spider):
    name = "computerphile"

    def start_requests(self):
        # Create Browser Object
        option = webdriver.ChromeOptions()
        chrome_prefs = dict()
        option.experimental_options["prefs"] = chrome_prefs
        chrome_prefs["profile.default_content_settings"] = {"images": 2}
        chrome_prefs["profile.managed_default_content_settings"] = {"images": 2}
        browser = webdriver.Chrome(options=option)

        # Access home page and drop down to load all needed elements
        main_page_url = "https://www.youtube.com/user/Computerphile/videos"
        browser.get(main_page_url)
        while True:
            time.sleep(1)
            browser.find_element(By.TAG_NAME, 'body').send_keys(Keys.END)
            page = HtmlResponse(url=main_page_url, body=browser.page_source.encode())
            load_ring = page.css("#contents > ytd-continuation-item-renderer")
            if len(load_ring) == 0:
                break

        # Get video URLs on the homepage and crawl them one by one
        main_page_response = HtmlResponse(url=main_page_url, body=browser.page_source.encode())
        videos = main_page_response.css("#video-title-link::attr(href)")
        yield from main_page_response.follow_all(videos)
        browser.close()

    def parse(self, response, **kwargs):
        # Get video title
        title = response.css("#title > h1 > yt-formatted-string::text").get()

        # Get upload time and the number of views
        tooltip = response.css("#tooltip::text").getall()
        views_and_date = [x for x in tooltip if '次观看' in x][0]
        views_date_pair = views_and_date.split('•')
        # Get the number of views
        views = int("".join(re.findall("[0-9]+", views_date_pair[0])))
        # Get upload time
        upload_date = "-".join(map(lambda x: x if len(x) >= 2 else '0' + x, re.findall("[0-9]+", views_date_pair[1])))

        # Get the number of likes
        likes_str = response.css(
            "#segmented-like-button > "
            "ytd-toggle-button-renderer > "
            "yt-button-shape > button > "
            "div.cbox.yt-spec-button-shape-next--button-text-content > "
            "span::text").get()
        try:
            likes = int(likes_str)
        except ValueError:
            likes = int(float(likes_str[:-1]) * 10000)

        # Get the number of comments
        comments = int(''.join(response.css("#count > yt-formatted-string > span:nth-child(1)::text").get().split(',')))

        # Get video introduction
        intro_raw = response.css("#description-inline-expander > yt-formatted-string *::text").getall()
        intro_reduced = map(lambda x: x.replace('\n', '').replace('\r', ''), intro_raw)
        intro_list = [x for x in intro_reduced if len(x)]
        introduction = '\n'.join(intro_list)

        # Build a complete item
        result = {
            "title": title,
            "upload_date": upload_date,
            "views": views,
            "likes": likes,
            "comments": comments,
            "introduction": introduction
        }
        return result
```

`ComputerphileSpider` has two class methods: `start_requests` and `parse`. The `start_requests` is a generator function that, after accessing Computerphile's YouTube homepage, uses Selenium to control the browser to continuously scroll down the page to load all the videos, and then gets the URLs of all Computerphile's contributed videos from the completely loaded page to provide to the Scheduler for subsequent download and processing. `parse` is used to process the response from Downloader Middlewares, which parses the content in the response into `dict` form and returns it, and will be used by Item Pipeline to generate the data we finally collect.
As mentioned earlier, because of dynamic rendering, the content contained in the response passed to `parse` is loaded with the help of Selenium. In Scrapy, this can be achieved by writing a Downloader Middleware that contains the logic to call Selenium for loading, which means that the following code needs to be added to the file middlewares.py to create the `ComputerphileMiddleware` class, which means adding the following code to the file:

```python
import time
from selenium import webdriver
from scrapy.http import HtmlResponse
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class ComputerphileMiddleware:
    def __init__(self):
        option = webdriver.ChromeOptions()
        chrome_prefs = dict()
        option.experimental_options["prefs"] = chrome_prefs
        chrome_prefs["profile.default_content_settings"] = {"images": 2}
        chrome_prefs["profile.managed_default_content_settings"] = {"images": 2}
        self.browser = webdriver.Chrome(options=option)

    def __del__(self):
        self.browser.close()

    def process_request(self, request, spider):
        # Access the video detail page
        url = request.url
        self.browser.get(url)

        time.sleep(1)

        # Expand and load introduction of video
        show_intro = self.browser.find_element("css selector", "#expand")
        show_intro.click()

        # Scroll down to load comments
        self.browser.find_element(By.TAG_NAME, 'body').send_keys(Keys.END)
        wait = WebDriverWait(self.browser, 120)
        wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#count > yt-formatted-string > span:nth-child(1)")))

        # Return page contents
        response_body = self.browser.page_source.encode()
        response = HtmlResponse(url=url, body=response_body)
        return response
```

Downloader Middleware receives requests from the Scheduler and gives the corresponding response to the `parse` method of the Spider, which shows that its core logic is precisely the `process_request` method, which uses Selenium to call the browser to access the URL contained in the request, control the browser to render the needed content, and obtain the rendered page HTML, which is wrapped into an `HtmlResponse` object and returned.
In order for `ComputerphileMiddleware` to take effect, the following is required in settings.py:

```python
DOWNLOADER_MIDDLEWARES = {
   'computerphile.middlewares.ComputerphileMiddleware': 543,
}
```

Run the following command to crawl all video information of Computerphile, and the crawl results will be saved in the file computerphile.csv:

```shell
scrapy crawl computerphile -O computerphile.csv
```

## 3. Baseline IR System

### 3.1 Imported data into elasticsearch
将数据处理完之后，我们便开始对网站的后端进行搭建，而第一步便是将清洗好的数据放入elasticsearch中。
我们在本地配置了elasticsearch和kibana，分别启动两个程序。
其中elasticsearch的端口号为`9200`,kibana的端口号为`5601`。随后在`Upload a file`中将数据文件放入其中即可。

### 3.2 Build the backend with flask
我们将这个项目的前后端分开进行，后端主要负责接收前端传进来的`keyword`并根据不同的算法查找出elasticsearch中的有效信息，进行一定的加工后发回给前端。
为了完成这个任务，我们建立了一个名为`search.py`的文件。使用flask搭建两个页面，主界面`home`负责输入需要查找的信息，分界面`results`负责展示输出的结果。
算法部分后面会有改进，这里只展现一种算法。
代码如下：

```python
from flask import Flask, url_for
from flask import request
from flask import render_template
from elasticsearch import Elasticsearch
from elasticsearch.connection import create_ssl_context

app = Flask(__name__,  static_url_path='/static')

'''主界面'''
@app.route('/')
def home():
    return render_template('home.html')

es = Elasticsearch(
    ["127.0.0.1"],
    port=9200,
    sniff_on_start=True,    
    sniff_on_connection_fail=True,  
    sniff_timeout=60    
)


'''结果界面'''
@app.route('/search', methods=['get'])
def search():
    keywords = request.args.get('keywords')

    query1 =  {
    "query": {
        "multi_match": {
        "query": "Python game",
        "fields": [
            "title",
            "introduction"
      ]
    }
  }
}

    res = es.search(index="results", body=query1)
    hits = res["hits"]["total"]["value"]
    return render_template("results.html", keywords=keywords, hits=hits, doc=res["hits"]["hits"])
```

### 3.3 Build the front end with HTML and CSS

前端由HTML和CSS编写而成，文件夹结构（包括Flask后端）如下：
```
project
│   search.py
└───static
│   │   listview.css
│   │   style.css
|
└───templates
     |   result.html
     |   search.html
```

运行流程如下，首先我们需要启动search.py（在3.2中已经说明了），然后程序会自动调用search.html，

```html
<!-此代码为search.html->
<head>
    <link rel="stylesheet" type="text/css" href="../static/style.css">
</head>
<div class="container">
    <form action="/result" method="get" class="parent"> 
        <input type="text" id="keywords" name="keywords" placeholder="搜点东西">
        <input type="submit" type="button" value="逆天一下">
    </form>
</div>
```

search.html会导入style.css

```css
/*此代码为style.css*/
body {
    width: 100%;
    height: 100vh;
    background: rgb(240,239,243);
    margin:auto;
    display: flex;
    align-items: center;
    justify-content: center;
}

.container {
    width: 95%;
    height: 90%;
    margin: 100px auto;
    background: #fff;
    border-radius: 15px;
    box-shadow: 4px 4px 30px rgba(0, 0, 0, 0.06);
}

.parent {
    width: 100%;
    height: 42px;
    top: 40px;
    left: 0px;
    position: relative;
    /*border: 1px solid #ccc;*/
}

.parent>input:first-of-type {
    /*输入框高度设置为40px, border占据2px，总高度为42px*/
    width: 38%;
    height: 100%;
    border: 1px solid #ccc;
    font-size: 16px;
    padding-left:10px;
    outline: none;
    left: 26%;
    position: relative;
}

.parent>input:first-of-type:focus {
    border: 1px solid #317ef3;
    padding-left: 10px;
}

.parent>input:last-of-type {
    /*button按钮border并不占据外围大小，设置高度42px*/
    width: 10%;
    height: 100%;
    position: absolute;
    background: #317ef3;
    border: 1px solid #317ef3;
    color: #fff;
    font-size: 16px;
    outline: none;
    top: 2.5%;
    left: 25.5%;
    position: relative;
}
```

![image-20221129030231552](C:\Users\YZY\AppData\Roaming\Typora\typora-user-images\image-20221129030231552.png)

当用户输入内容，并点击搜索时，search.py会自动运行result.html。在这个html文件中，我们嵌入了可以被Flask识别的python循环代码，这样后端返回多少个结果，前端就会出现多少个搜索项

```html
<!该文件是result.html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Title</title>
    
    <link rel="stylesheet" href="../static/listView.css">
</head>
<body>

<div id="mainContentDiv">

    <div class="mainDivMainImgDiv" >
        <div class="headLeftDiv headLeftDivFont">Search Results</div>
        <div class="link-top"></div>
        <div class="headLineBlowDiv">
            <div class="headLeftDiv">
                Hit<span>【{{HITS}}】</span>results
            </div>
        </div>
    </div>

    <div class="mainDivMainInfoiv">
        <div class="mainInfoSubDiv">
            {% for item in Data %}
                <div class="mainDIvMainInfoDivSubInfoDiv" >
                    <div class="mainDivMainInfoiv_HeadTextDiv " >
                        <div class="mainDivMainInfoiv_HeadTextDiv_TextBox cardInfoTitle findKey" >
                            {{item['title']}}
                        </div>
                    </div>
                    <div class="mainDivMainInfoiv_mainTextDiv  findKey">
                        {{item['introduction']}}
                    </div>
                    <div class="InfoDiv_Right_2 rightFlexFont">
                        {{item['date']}}
                    </div>
                </div>
            {% endfor %}
        </div>
    </div>
</div>
</body>
</html>
```

reuslt.html还会调用listview.css

```css
/*该文件是listview.css*/
body {
    background: whitesmoke;
}

#mainContentDiv {
    position: absolute;
    width: 70%;
    height: 100%;
    background: whitesmoke;
    top: 10%;
    left: 10%;
}

.mainDivMainImgDiv {
    position: absolute;
    width: 100%;
    height: 120px;
    background: white;
}

.mainDivMainInfoiv {
    position: absolute;
    width: 100%;
    height: 100%;
    background: whitesmoke;
    top: 130px;
}

.mainInfoSubDiv{
    position: relative;
    width: 100%;
    height: 100%;
    background: whitesmoke;
    overflow-y: auto;
    overflow-x: hidden;
}

.headLeftDiv {
    position: absolute;
    width: 50%;
    height: 100%;
    left: 4%;
    top: 25%;
}

.headLeftDivFont {
    font-weight: 500;
    /*line-height: 58px;*/
    font-size: 20px;
    color: #333;
}

.headRightDiv {
    position: absolute;
    width: 40%;
    height: 100%;
    right: 2%;
    top: 20%;
}

/*中间的过度的横线*/
.link-top {
    position: absolute;
    top: 60%;
    left: 4%;
    width: 90%;
    height: 1px;
    border-top: solid #e8edf3 1px;
}

.headLineBlowDiv {
    position: absolute;
    top: 63%;
    height: 40%;
    width: 100%;
}

/*---------------------------subInfoDiv--------------*/
.mainDIvMainInfoDivSubInfoDiv {
    position: relative;
    width: 100%;
    height: 13%;
    background: white;
    border: 1px solid #eaeaea;
}

.mainDIvMainInfoDivSubInfoDiv:hover {
    background: rgba(0, 0, 0, 0.05);
}

.mainDivMainInfoiv_HeadTextDiv {
    position: absolute;
    top: 10%;
    left: 4%;
    width: 30%;
    height: 30%;
    background: rgba(0, 0, 0, 0);

}

.mainDivMainInfoiv_mainTextDiv {
    position: absolute;
    top: 52%;
    left: 4%;
    width: 80%;
    background: rgba(0, 0, 0, 0);
    overflow: hidden;
    text-overflow:ellipsis;
    display:-webkit-box;
    -webkit-box-orient:vertical;
    -webkit-line-clamp:2;
    font-size: 12px;
    color: rgb(102, 102, 102);
}

.mainDivMainInfoiv_HeadTextDiv_TextBox {
    position: absolute;
    top: 25%;
    width: 100%;
    height: 50%;
    background: rgba(0, 0, 0, 0);
}

.cardInfoTitle {
    font-weight: 700;
    /*color: #1f264d;*/
    height: 22px;
    display: inline-block;
    max-width: 600px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    cursor: pointer;
}

.rightFlexFont {
    color: #b3b3b3;
    font-weight: 500;
    text-align: right;
    font-size: 12px;
    color: rgb(179, 179, 179);
}

.InfoDiv_Right_2 {
    position: absolute;
    top: 55%;
    right: 2%;
    width: 18%;
    height: 30%;
    background: rgba(0, 0, 0, 0);
}
```

用户最终会看到结果
![image-20221129030904136](C:\Users\YZY\AppData\Roaming\Typora\typora-user-images\image-20221129030904136.png)

### 3.4 Search work correctly

在这个项目中，我们使用的是`Flask`框架。这是一个基于python编写的轻量级web应用框架。
首先运行如下命令，设置`Flask`的运行环境:

```shell
set FLASK_EVN=development
```
其次运行如下命令，调入刚刚写好的Python文件：
```shell
set FLASK_APP=server.py
```
最后运行如下命令，运行`Flask`:
```shell
flask run
```
在界面中输入想要查询的内容，例如`python game`,返回搜索到的结果。

## 4. Enhanced IR System

## 5. Evaluation and Comparison
