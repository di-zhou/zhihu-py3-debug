#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import getpass
import importlib
import json
import time
from urllib.parse import urlencode

import requests

from .common import *


class ZhihuClient:        
            
    def __init__(self, username: str = None, password: str = None):
        self.username = username
        self.password = password

        self.login_data = {
            'client_id': 'c3cef7c66a1843f8b3a9e6a1e3160e20',
            'grant_type': 'password',
            'source': 'com.zhihu.web',
            'username': '',
            'password': '',
            'lang': 'en',
            'ref_source': 'homepage',
            'utm_source': ''
        }
        self.session = requests.session()
        self.session.headers = {
            'accept-encoding': 'gzip, deflate, br',
            'Host': 'www.zhihu.com',
            'Referer': 'https://www.zhihu.com/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36'
        }
        self.session.cookies = cookiejar.LWPCookieJar(filename='./cookies.txt')  
        self.proxies = None

    # ===== login staff =====

    def login(self, captcha_lang: str = 'en', load_cookies: bool = True):
        """
        模拟登录知乎
        :param captcha_lang: 验证码类型 'en' or 'cn'
        :param load_cookies: 是否读取上次保存的 Cookies
        :return: bool
        若在 PyCharm 下使用中文验证出现无法点击的问题，
        需要在 Settings / Tools / Python Scientific / Show Plots in Toolwindow，取消勾选
        """
        if load_cookies and self.load_cookies():
            print('读取 Cookies 文件')
            if self.check_login():
                print('登录成功')
                return True
            print('Cookies 已过期')

        self._check_user_pass()
        self.login_data.update({
            'username': self.username,
            'password': self.password,
            'lang': captcha_lang
        })

        timestamp = int(time.time() * 1000)
        self.login_data.update({
            'captcha': self._get_captcha(self.login_data['lang']),
            'timestamp': timestamp,
            'signature': self._get_signature(timestamp)
        })

        headers = self.session.headers.copy()
        headers.update({
            'content-type': 'application/x-www-form-urlencoded',
            'x-zse-83': '3_1.1',
            'x-xsrftoken': self._get_xsrf()
        })
        data = self._encrypt(self.login_data)
        login_api = 'https://www.zhihu.com/api/v3/oauth/sign_in'
        resp = self.session.post(login_api, data=data, headers=headers)
        if 'error' in resp.text:
            print(json.loads(resp.text)['error'])
        if self.check_login():
            print('登录成功')
            return True
        print('登录失败')
        return False

    def load_cookies(self):
        """
        读取 Cookies 文件加载到 Session
        :return: bool
        """
        try:
            self.session.cookies.load(ignore_discard=True)
            return True
        except FileNotFoundError:
            return False

    def check_login(self):
        """
        检查登录状态，访问登录页面出现跳转则是已登录，
        如登录成功保存当前 Cookies
        :return: bool
        """
        login_url = 'https://www.zhihu.com/signup'
        resp = self.session.get(login_url, allow_redirects=False)
        if resp.status_code == 302:
            self.session.cookies.save()
            return True
        return False

    def _get_xsrf(self):
        """
        从登录页面获取 xsrf
        :return: str
        """
        self.session.get('https://www.zhihu.com/', allow_redirects=False)
        for c in self.session.cookies:
            if c.name == '_xsrf':
                return c.value
        raise AssertionError('获取 xsrf 失败')

    def _get_captcha(self, lang: str):
        """
        请求验证码的 API 接口，无论是否需要验证码都需要请求一次
        如果需要验证码会返回图片的 base64 编码
        根据 lang 参数匹配验证码，需要人工输入
        :param lang: 返回验证码的语言(en/cn)
        :return: 验证码的 POST 参数
        """
        if lang == 'cn':
            api = 'https://www.zhihu.com/api/v3/oauth/captcha?lang=cn'
        else:
            api = 'https://www.zhihu.com/api/v3/oauth/captcha?lang=en'
        resp = self.session.get(api)
        show_captcha = re.search(r'true', resp.text)

        if show_captcha:
            put_resp = self.session.put(api)
            json_data = json.loads(put_resp.text)
            img_base64 = json_data['img_base64'].replace(r'\n', '')
            with open('./captcha.jpg', 'wb') as f:
                f.write(base64.b64decode(img_base64))
            img = Image.open('./captcha.jpg')
            if lang == 'cn':
                import matplotlib.pyplot as plt
                plt.imshow(img)
                print('点击所有倒立的汉字，在命令行中按回车提交')
                points = plt.ginput(7)
                capt = json.dumps({'img_size': [200, 44],
                                   'input_points': [[i[0] / 2, i[1] / 2] for i in points]})
            else:
                img_thread = threading.Thread(target=img.show, daemon=True)
                img_thread.start()
                capt = input('请输入图片里的验证码：')
            # 这里必须先把参数 POST 验证码接口
            self.session.post(api, data={'input_text': capt})
            return capt
        return ''

    def _get_signature(self, timestamp: int or str):
        """
        通过 Hmac 算法计算返回签名
        实际是几个固定字符串加时间戳
        :param timestamp: 时间戳
        :return: 签名
        """
        ha = hmac.new(b'd1b964811afb40118a12068ff74a12f4', digestmod=hashlib.sha1)
        grant_type = self.login_data['grant_type']
        client_id = self.login_data['client_id']
        source = self.login_data['source']
        ha.update(bytes((grant_type + client_id + source + str(timestamp)), 'utf-8'))
        return ha.hexdigest()

    def _check_user_pass(self):
        """
        检查用户名和密码是否已输入，若无则手动输入
        """
        if not self.username:
            self.username = input('请输入手机号：')
        if self.username.isdigit() and '+86' not in self.username:
            self.username = '+86' + self.username

        if not self.password:
            self.password = input('请输入密码：')

    @staticmethod
    def _encrypt(form_data: dict):
        with open('./encrypt.js') as f:
            js = execjs.compile(f.read())
            return js.call('Q', urlencode(form_data))

    # ===== network staff =====

    def set_proxy(self, proxy):
        """设置代理

        :param str proxy: 使用 "http://example.com:port" 的形式
        :return: 无
        :rtype: None

        :说明:
            由于一个 :class:`.ZhihuClient` 对象和它创建出来的其他知乎对象共用
            一个Session，所以调用这个方法也会将所有生成出的知乎类设置上代理。
        """
        self._session.proxies.update({'http': proxy})

    def set_proxy_pool(self, proxies, auth=None, https=True):
        """设置代理池

        :param proxies: proxy列表, 形如 ``["ip1:port1", "ip2:port2"]``
        :param auth: 如果代理需要验证身份, 通过这个参数提供, 比如
        :param https: 默认为 True, 传入 False 则不设置 https 代理
        .. code-block:: python

              from requests.auth import HTTPProxyAuth
              auth = HTTPProxyAuth('laike9m', '123')
        :说明:
             每次 GET/POST 请求会随机选择列表中的代理
        """
        from random import choice

        if https:
            self.proxies = [{'http': p, 'https': p} for p in proxies]
        else:
            self.proxies = [{'http': p} for p in proxies]

        def get_with_random_proxy(url, **kwargs):
            proxy = choice(self.proxies)
            kwargs['proxies'] = proxy
            if auth:
                kwargs['auth'] = auth
            return self._session.original_get(url, **kwargs)

        def post_with_random_proxy(url, *args, **kwargs):
            proxy = choice(self.proxies)
            kwargs['proxies'] = proxy
            if auth:
                kwargs['auth'] = auth
            return self._session.original_post(url, *args, **kwargs)

        self._session.original_get = self._session.get
        self._session.get = get_with_random_proxy
        self._session.original_post = self._session.post
        self._session.post = post_with_random_proxy

    def remove_proxy_pool(self):
        """
        移除代理池
        """
        self.proxies = None
        self._session.get = self._session.original_get
        self._session.post = self._session.original_post
        del self._session.original_get
        del self._session.original_post

    # ===== getter staff ======

    def me(self):
        """获取使用特定 cookies 的 Me 实例

        :return: cookies对应的Me对象
        :rtype: Me
        """
        from .me import Me
        headers = dict(Default_Header)
        headers['Host'] = 'zhuanlan.zhihu.com'
        res = self._session.get(Get_Me_Info_Url, headers=headers)
        json_data = res.json()
        url = json_data['profileUrl']
        name = json_data['name']
        motto = json_data['bio']
        photo = json_data['avatar']['template'].format(
            id=json_data['avatar']['id'], size='r')
        return Me(url, name, motto, photo, session=self._session)

    def __getattr__(self, item: str):
        """本函数用于获取各种类，如 `Answer` `Question` 等.

        :支持的形式有:
            1. client.answer()
            2. client.author()
            3. client.collection()
            4. client.column()
            5. client.post()
            6. client.question()
            7. client.topic()

            参数均为对应页面的url，返回对应的类的实例。
        """
        def getter(url):
            return getattr(module, item.capitalize())(url,
                                                      session=self._session)
        attr_list = ['answer', 'author', 'collection',
                     'column', 'post', 'question', 'topic']
        if item.lower() in attr_list:
            module = importlib.import_module('.'+item.lower(), 'zhihu')
            return getter
