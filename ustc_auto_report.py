import requests
import json
from bs4 import BeautifulSoup
import pytesseract
from PIL import Image
import numpy as np
import cv2
import time
import datetime
import os


class USTCAutoHealthReport(object):
    def __init__(self):
        self.sess = requests.session()
        self.url = 'https://passport.ustc.edu.cn/login?service=https%3A%2F%2Fweixine.ustc.edu.cn%2F2020%2Fcaslogin'
        # 登录url
        self.login_url = 'https://passport.ustc.edu.cn/login'
        # 验证码url
        self.validate_url = 'https://passport.ustc.edu.cn/validatecode.jsp?type=login'
        # 打卡url
        self.clock_in_url = 'https://weixine.ustc.edu.cn/2020/daliy_report'
        # 报备url
        self.report_url = 'https://weixine.ustc.edu.cn/2020/apply/daliy/post'
        # 验证码图片存放路径
        self.LT_save_path = '/tmp'
        # 验证码图片文件名
        self.LT_file = ''
        # 验证码识别结果
        self.LT = ''

    def _get_CAS_LT(self):
        """
        获取登录时需要提供的验证字段
        """
        response = self.sess.get(self.url)
        CAS_LT = BeautifulSoup(response.text, 'lxml').find(attrs={'id': 'CAS_LT'}).get('value')
        return CAS_LT

    def _get_token(self, response):
        """
        获取打卡时需要提供的验证字段
        """
        s = BeautifulSoup(response.text, 'lxml')
        token = s.find(attrs={'name': '_token'}).get('value')
        return token

    def _save_validate_number(self):
        """
        将验证码图片保存到一个文件
        """
        validate_number = self.sess.get(self.validate_url)
        self.LT_file = str(time.time()) + '.jpg'
        with open(os.path.join(self.LT_save_path, self.LT_file), 'wb') as f:
            f.write(validate_number.content)

    def _recognize_validate_number(self):
        """
        识别验证码
        """
        image = cv2.imread(os.path.join(self.LT_save_path, self.LT_file))
        kernel = np.ones((2, 2), np.uint8)
        image = cv2.dilate(image, kernel, iterations=1)
        image = Image.fromarray(image).convert('L')
        config = '--psm 6 --oem 3 -c tessedit_char_whitelist=0123456789'
        self.LT = pytesseract.image_to_string(image, config=config).strip()
        return self.LT

    def _check_success(self, response):
        """
        简单check一下有没有成功打卡、报备
        """
        return '成功' in response.text

    def login(self, username, password):
        """
        登录,需要提供用户名、密码，顺便返回后续表单需要提供的token
        """
        self.sess.cookies.clear()
        self.LT_file = ''
        self.LT = ''
        try:
            CAS_LT = self._get_CAS_LT()
            self._save_validate_number()
            LT = self._recognize_validate_number()
            login_data = {
                'username': username,
                'password': password,
                'warn': '',
                'CAS_LT': CAS_LT,
                'showCode': '1',
                'button': '',
                'model': 'uplogin.jsp',
                'service': 'https://weixine.ustc.edu.cn/2020/caslogin',
                'LT': LT
            }
            response = self.sess.post(self.login_url, login_data)
            token = self._get_token(response)
            return token
        except:
            return 0

    def daily_clock_in(self, token, post_data_file):
        """
        打卡函数，需要提供token(调用login方法获取)和包含表单内容的json文件
        打卡成功返回True，打卡失败返回False
        """
        try:
            with open(post_data_file, 'r') as f:
                post_data = json.loads(f.read())
            post_data['_token'] = token
            response = self.sess.post(self.clock_in_url, data=post_data)
            return self._check_success(response)
        except:
            return False

    def weekly_report(self, token):
        """
        报备函数，需要提供token(调用login方法获取)
        报备成功返回1，七天内重复报备返回-1，因其他原因报备失败返回0
        """
        try:
            start_date = datetime.datetime.now()
            date_delta = datetime.timedelta(days=6)
            end_date = start_date + date_delta
            data = {
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "_token": token
            }
            response = self.sess.post(self.report_url, data=data)
            if not self._check_success(response):
                if '请不要在有效期内重复报备' in response.text:
                    return -1
                return 0
            return 1
        except:
            return 0
