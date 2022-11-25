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
        # 创建浏览器对象
        option = webdriver.ChromeOptions()
        chrome_prefs = dict()
        option.experimental_options["prefs"] = chrome_prefs
        chrome_prefs["profile.default_content_settings"] = {"images": 2}
        chrome_prefs["profile.managed_default_content_settings"] = {"images": 2}
        browser = webdriver.Chrome(options=option)

        # 访问主页并下拉加载所有所需元素
        main_page_url = "https://www.youtube.com/user/Computerphile/videos"
        browser.get(main_page_url)
        while True:
            time.sleep(1)
            browser.find_element(By.TAG_NAME, 'body').send_keys(Keys.END)
            page = HtmlResponse(url=main_page_url, body=browser.page_source.encode())
            load_ring = page.css("#contents > ytd-continuation-item-renderer")
            if len(load_ring) == 0:
                break

        # 获取主页上视频URL并逐一爬取
        main_page_response = HtmlResponse(url=main_page_url, body=browser.page_source.encode())
        videos = main_page_response.css("#video-title-link::attr(href)")
        yield from main_page_response.follow_all(videos)
        browser.close()

    def parse(self, response, **kwargs):
        # 获取视频标题
        title = response.css("#title > h1 > yt-formatted-string::text").get()

        # 获取播放量和发布时间
        tooltip = response.css("#tooltip::text").getall()
        views_and_date = [x for x in tooltip if '次观看' in x][0]
        views_date_pair = views_and_date.split('•')
        # 获取播放量
        views = int("".join(re.findall("[0-9]+", views_date_pair[0])))
        # 获取发布时间
        upload_date = "-".join(map(lambda x: x if len(x) >= 2 else '0' + x, re.findall("[0-9]+", views_date_pair[1])))

        # 获取点赞数
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

        # 获取评论数
        comments = int(''.join(response.css("#count > yt-formatted-string > span:nth-child(1)::text").get().split(',')))

        # 获取视频简介
        intro_raw = response.css("#description-inline-expander > yt-formatted-string *::text").getall()
        intro_reduced = map(lambda x: x.replace('\n', '').replace('\r', ''), intro_raw)
        intro_list = [x for x in intro_reduced if len(x)]
        introduction = '\n'.join(intro_list)

        # 一条完整记录
        result = {
            "title": title,
            "upload_date": upload_date,
            "views": views,
            "likes": likes,
            "comments": comments,
            "introduction": introduction
        }
        return result
