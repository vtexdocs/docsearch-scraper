"""
DocumentationSpider
"""
from scrapy.linkextractors.lxmlhtml import LxmlLinkExtractor
from scrapy.spiders import CrawlSpider, Rule
from scrapy.http import Request

# Import for the sitemap behavior
from scrapy.spiders import SitemapSpider
from scrapy.spiders.sitemap import regex
import re
import os

# End of import for the sitemap behavior

from scrapy.spidermiddlewares.httperror import HttpError

from scrapy.exceptions import CloseSpider

from scrapy import signals  # Import Scrapy signals

import requests
from datetime import datetime

EXIT_CODE_EXCEEDED_RECORDS = 4

def parse_file(file_path):
    if len(file_path) == 0:
        return False

    print("FILE PATH: ", file_path)

    extension = file_path.split(".")[1]
    if extension in ['md', 'mdx']:
        filename = file_path.split(".")[0].split("/")[-1]
        language = file_path.split("/")[1]
        type = file_path.split("/")[2]
        return  {
            'file_path': file_path,
            'filename': filename,
            'language': language,
            'type': type
        }
    return False


class DocumentationSpider(CrawlSpider, SitemapSpider):
    """
    DocumentationSpider
    """
    http_user = os.environ.get('DOCSEARCH_BASICAUTH_USERNAME', None)
    http_pass = os.environ.get('DOCSEARCH_BASICAUTH_PASSWORD', None)
    NB_INDEXED = 0  # Add this line
    algolia_helper = None
    strategy = None
    js_render = False
    js_wait = 0
    match_capture_any_scheme = re.compile(r"^(https?)(.*)")
    backreference_any_scheme = r"^https?\2(.*)$"
    # Could be any url prefix such as http://www or http://
    every_schemes = ["http", "https"]
    reason_to_stop = None

    @staticmethod
    def to_any_scheme(url):
        """Return a regex that represent the URL and match any scheme from it"""
        return url if not re.match(
            DocumentationSpider.match_capture_any_scheme, url) else re.sub(
            DocumentationSpider.match_capture_any_scheme,
            DocumentationSpider.backreference_any_scheme, url)

    @staticmethod
    def to_other_scheme(url):
        """Return a list with the translation to this url into each other scheme."""
        other_scheme_urls = []
        match = DocumentationSpider.match_capture_any_scheme.match(url)
        assert match
        if not (match and match.group(1) and match.group(2)):
            raise ValueError(
                "Must have a match and split the url into the scheme and the rest. url: " + url)

        previous_scheme = match.group(1)
        url_with_no_scheme = match.group(2)

        for scheme in DocumentationSpider.every_schemes:
            if scheme != previous_scheme:
                other_scheme_urls.append(scheme + url_with_no_scheme)
        return other_scheme_urls

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(DocumentationSpider, cls).from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.engine_stopped, signal=signals.engine_stopped)
        return spider

    def __init__(self, config, algolia_helper, strategy, *args, **kwargs):
        # Scrapy config
        self.name = config.index_name
        self.allowed_domains = config.allowed_domains
        self.start_urls = [start_url['url'] for start_url in config.start_urls]
        # We need to ensure that the stop urls are scheme agnostic too if it represents URL
        self.stop_urls = [DocumentationSpider.to_any_scheme(stop_url) for
                          stop_url in config.stop_urls]
        self.algolia_helper = algolia_helper
        self.strategy = strategy
        self.js_render = config.js_render
        self.js_wait = config.js_wait
        self.scrape_start_urls = config.scrape_start_urls
        self.remove_get_params = config.remove_get_params
        self.strict_redirect = config.strict_redirect
        self.nb_hits_max = config.nb_hits_max

        self.is_file_update = config.is_file_update
        self.added_files = config.added_files
        self.removed_files = config.removed_files
        self.updated_files = config.updated_files
        self.renamed_files = config.renamed_files
        self.docs_to_add = []
        self.docs_to_remove = []
        self.app_id = config.app_id
        self.api_key = config.api_key
        self.index_name = config.index_name

        # Initialize counters and lists for tracking
        self.total_files_processed = 0
        self.failed_indexing = 0
        self.failed_indexing_404 = 0
        self.failed_indexing_500 = 0
        self.failed_500_urls = []
        self.failed_404_urls = []
        self.failed_500_filepaths = []
        self.failed_404_filepaths = []

        super(DocumentationSpider, self).__init__(*args, **kwargs)

        # Get rid of scheme consideration
        # Start_urls must stays authentic URL in order to be reached, we build agnostic scheme regex based on those URL
        start_urls_any_scheme = [DocumentationSpider.to_any_scheme(start_url)
                                 for start_url in self.start_urls] if not config.sitemap_urls else ['']

        # Convert file paths to get slugs for crawl or remove records
        if self.is_file_update:
            if isinstance(self.added_files, str):
                print('ADDED: ', self.added_files)
                for item in self.added_files.split(','):
                    parsed_content = parse_file(item)
                    if(parsed_content):
                        self.docs_to_add.append(parsed_content)
            if isinstance(self.removed_files, str):
                print('REMOVED: ', self.removed_files)
                for item in self.removed_files.split(','):
                    parsed_content = parse_file(item)
                    if(parsed_content):
                        self.docs_to_remove.append(parsed_content)
            if isinstance(self.updated_files, str):
                print('UPDATED: ', self.updated_files)
                for item in self.updated_files.split(','):
                    parsed_content = parse_file(item)
                    if(parsed_content):
                        self.docs_to_add.append(parsed_content)
                        self.docs_to_remove.append(parsed_content)
            # if isinstance(self.renamed_files, str):
            #     print('RENAMED', self.renamed_files)
            #     for item in self.renamed_files.split(' '):
            #         [old_file, new_file] = item.split(',')
            #         old_parsed_content = parse_file(old_file)
            #         new_parsed_content = parse_file(new_file)
            #         if(old_parsed_content and new_parsed_content):
            #             self.docs_to_add.append(new_parsed_content)
            #             self.docs_to_remove.append(old_parsed_content)

    def start_requests(self):
        if self.is_file_update:
            try:
                for value in self.docs_to_add:
                    self.total_files_processed += 1
                    url_bar = '' if self.start_urls[0][-1] == '/' else '/'
                    has_language = value["language"] if value["language"] else ''
                    doc_type = f'docs/{value["type"]}' if value["type"] == "tutorials" or value["type"] == "tracks" else value["type"]
                    url = f'{self.start_urls[0]}{url_bar}{has_language}/{doc_type}/{value["filename"]}'

                    yield Request(
                        url, 
                        callback=self.log_unbroken_pages,
                        meta={
                            "file_path": value["file_path"],
                            "original_url": url
                        },
                        errback=self.errback_alternative_link
                    )
            except Exception as e:
                print("Error: ", e)

   
    def log_unbroken_pages(self, response):
        """Log successful page loads to Zapier"""
        if response.status == 200:
            file_path = response.meta.get("file_path")
            url = response.meta.get("original_url")
            
            requests.post(
                "https://hooks.zapier.com/hooks/catch/12058878/20il2ne/",
                json={
                    "file_path": file_path,
                    "url": url,
                    "status": "200",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "time": datetime.now().strftime("%H:%M:%S")
                }
            )
        return "200 OK"

    def is_rules_compliant(self, response):

        # Even if the link extract were compliant, we may have been redirected. Hence we check a new time

        # Redirection redirect on a start url
        if not self.scrape_start_urls and (
                response.url in self.start_urls or response.request.url in self.start_urls):
            return False

        for rule in self._rules:
            if not self.strict_redirect:
                if rule.link_extractor._link_allowed(response):
                    continue

                if rule.link_extractor._link_allowed(response.request):
                    response.replace(url=response.request.url)
                    continue
            else:
                if rule.link_extractor._link_allowed(
                        response) and rule.link_extractor._link_allowed(
                    response.request):
                    continue
            return False

        return True

    def errback_alternative_link(self, failure):
        meta = failure.request.meta
        original_url = meta.get("original_url", failure.request.url)
        file_path = meta.get("file_path", None)
        status = None

        # Get status code and log it for debugging
        if hasattr(failure.value, 'response'):
            if hasattr(failure.value.response, 'status'):
                status = failure.value.response.status
                self.logger.error('HTTP Status:%s on %s', status, original_url)

                # Record errors based on status code
                if not (original_url in self.failed_404_urls or original_url in self.failed_500_urls):
                    self.failed_indexing += 1
                    if status == 404:
                        self.failed_404_urls.append(original_url)
                        self.failed_404_filepaths.append(file_path)
                        self.failed_indexing_404 += 1
                    elif status == 500:
                        self.failed_500_urls.append(original_url)
                        self.failed_500_filepaths.append(file_path)
                        self.failed_indexing_500 += 1
            else:
                self.logger.error('No status code in response for %s', original_url)
                status = 404  # Assume 404 if no status code
        else:
            self.logger.error('Connection error for %s: %s', original_url, str(failure.value))
            status = 404  # Treat connection errors as 404s
        
        

        # Try alternative links
        if len(meta.get("alternative_links", [])) > 0:
            alternative_link = meta["alternative_links"].pop(0)
            print('Trying alternative link: %s', alternative_link)
            yield failure.request.replace(url=alternative_link, meta=meta)
            return

    def engine_stopped(self):
        """Print statistics after the spider finishes."""
        print("\n=== Crawling Statistics ===")
        print(f"Total files processed:    {self.total_files_processed}")
        print(f"  Total failed:          {self.failed_indexing}")
        print(f"  404 errors:            {self.failed_indexing_404}")
        print(f"  500 errors:            {self.failed_indexing_500}")
        
        if self.failed_500_urls:
            print("\nFiles failed with 500 error:")
            for url in self.failed_500_urls:
                file_path = self.failed_500_filepaths[self.failed_500_urls.index(url)]

                print(f"{url}")
                requests.post(
                    "https://hooks.zapier.com/hooks/catch/12058878/20il2ne/",
                    json={
                        "file_path": file_path,
                        "url": url,
                        "status": "500", 
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "time": datetime.now().strftime("%H:%M:%S")
                    }
                )
                
        if self.failed_404_urls:
            print("\nFiles failed with 404 error:")
            for url in self.failed_404_urls:
                file_path = self.failed_404_filepaths[self.failed_404_urls.index(url)]

                print(f"{url}")
                requests.post(
                    "https://hooks.zapier.com/hooks/catch/12058878/20il2ne/",
                    json={
                        "file_path": file_path,
                        "url": url,
                        "status": "404",
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "time": datetime.now().strftime("%H:%M:%S")
                    }
                )

