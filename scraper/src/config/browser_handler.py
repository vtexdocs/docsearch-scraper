import re
import os
from selenium import webdriver

from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from ..custom_downloader_middleware import CustomDownloaderMiddleware
from ..js_executor import JsExecutor


class BrowserHandler:
    @staticmethod
    def conf_need_browser(config_original_content, js_render):
        group_regex = re.compile(r'\(\?P<(.+?)>.+?\)')
        results = re.findall(group_regex, config_original_content)

        return len(results) > 0 or js_render

    @staticmethod
    def _create_driver(chromedriver_path, chrome_options):
        # Selenium 4 accepts `service=`; Selenium 3.141 (Action / Python 3.6)
        # still has chrome.service.Service but Chrome() rejects that kwarg.
        try:
            from selenium.webdriver.chrome.service import Service
            return webdriver.Chrome(
                service=Service(executable_path=chromedriver_path),
                options=chrome_options)
        except TypeError:
            return webdriver.Chrome(
                executable_path=chromedriver_path,
                options=chrome_options)

    @staticmethod
    def init(config_original_content, js_render, user_agent):
        driver = None

        if BrowserHandler.conf_need_browser(config_original_content,
                                            js_render):
            chrome_options = Options()
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('user-agent={0}'.format(user_agent))
            chrome_binary = os.environ.get(
                'CHROME_BIN',
                '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
            if os.path.isfile(chrome_binary):
                chrome_options.binary_location = chrome_binary

            CHROMEDRIVER_PATH = os.environ.get('CHROMEDRIVER_PATH',
                                               "/usr/bin/chromedriver")
            if not os.path.isfile(CHROMEDRIVER_PATH):
                raise Exception(
                    "Env CHROMEDRIVER_PATH='{}' is not a path to a file".format(
                        CHROMEDRIVER_PATH))
            driver = webdriver.Chrome(
                service=Service(executable_path=CHROMEDRIVER_PATH),
                options=chrome_options)
            CustomDownloaderMiddleware.driver = driver
            JsExecutor.driver = driver
            BrowserHandler._user_agent = user_agent
        return driver

    @staticmethod
    def restart():
        try:
            BrowserHandler.destroy(CustomDownloaderMiddleware.driver)
        except Exception:
            pass
        return BrowserHandler.init(
            '{"js_render": true}',
            True,
            getattr(BrowserHandler, '_user_agent', 'Algolia DocSearch Crawler')
        )

    @staticmethod
    def destroy(driver):
        # Start browser if needed
        if driver is not None:
            driver.quit()
            driver = None

        return driver
