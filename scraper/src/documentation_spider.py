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
import time

# End of import for the sitemap behavior

from scrapy.spidermiddlewares.httperror import HttpError

from scrapy.exceptions import CloseSpider

from algoliasearch.search_client import SearchClient

from scrapy import signals  # Import Scrapy signals

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

        super(DocumentationSpider, self).__init__(*args, **kwargs)

        # Connect to the spider_closed signal to print statistics after the spider finishes
        self.signals.connect(self.engine_stopped, signals.engine_stopped)

        # Get rid of scheme consideration
        # Start_urls must stays authentic URL in order to be reached, we build agnostic scheme regex based on those URL
        start_urls_any_scheme = [DocumentationSpider.to_any_scheme(start_url)
                                 for start_url in self.start_urls] if not config.sitemap_urls else ['']

        if not self.is_file_update:
            link_extractor = LxmlLinkExtractor(
                allow=start_urls_any_scheme,
                deny=self.stop_urls,
                tags=('a', 'area', 'iframe'),
                attrs=('href', 'src'),
                canonicalize=(not config.js_render or not config.use_anchors)
            )

            DocumentationSpider.rules = [
                Rule(link_extractor, callback=self.parse_from_start_url,
                    follow=False if self.is_file_update else True),
            ]

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


        # START _init_ part from SitemapSpider
        # We son't want to check anything if we don't even have a sitemap URL
        if config.sitemap_urls:
            # In case we don't have a special documentation regex,
            # we assume that start_urls are there to match a documentation part
            self.sitemap_urls_regexs =\
                config.sitemap_urls_regexs if config.sitemap_urls_regexs else start_urls_any_scheme

            sitemap_rules = []
            if self.sitemap_urls_regexs:
                for regex in self.sitemap_urls_regexs:
                    sitemap_rules.append((regex, 'parse_from_sitemap'))
            else:  # Neither start url nor regex: default, we parse all
                print("Neither start url nor regex: default, we scrap all")
                sitemap_rules = [('.*', 'parse_from_sitemap')]

            self.__init_sitemap_(config.sitemap_urls, sitemap_rules,
                                 config.sitemap_alternate_links)
            self.force_sitemap_urls_crawling = config.force_sitemap_urls_crawling
        # END _init_ part from SitemapSpider
        super(DocumentationSpider, self)._compile_rules()

    def start_requests(self):
        # VTEXDocs: crawl according to the file updates
        # This method is used for the Help Center, the assembled URL won't work for the Developer Portal 

        # Initialize counters and lists for tracking
        self.total_files_processed = 0
        self.successfully_indexed = 0
        self.failed_indexing = 0
        self.failed_500_files = []
        self.failed_404_files = []

        if self.is_file_update:
            self.remove_records()
            try:
                for value in self.docs_to_add:
                    self.total_files_processed += 1
                    url_bar = '' if self.start_urls[0][-1] == '/' else '/'
                    has_language = value["language"] if value["language"] else ''
                    doc_type = f'docs/{value["type"]}' if value["type"] == "tutorials" or value["type"] == "tracks" else value["type"]
                    url = f'{self.start_urls[0]}{url_bar}{has_language}/{doc_type}/{value["filename"]}'

                    yield Request(url, callback=self.parse_from_files,
                                meta={
                                    "alternative_links": DocumentationSpider.to_other_scheme(
                                        url),
                                    "retry_count": 0,  # Initialize retry count
                                    "max_retries": 3,   # Set maximum retries
                                    "sleep_time": 1.0,  # Add 1 second sleep between retries
                                    "original_url": url  # Track the original URL
                                },
                                errback=self.errback_alternative_link)
            except Exception as e:
                print("Error: ", e)
                
        # We crawl according to the sitemap
        # This method is used for the Developer Portal
        elif self.sitemap_urls:
            for url in self.sitemap_urls:
                try:
                    yield Request(url, callback=self._parse_sitemap,
                                meta={
                                    "alternative_links": DocumentationSpider.to_other_scheme(
                                        url),
                                    "retry_count": 0,  # Initialize retry count
                                    "max_retries": 3,   # Set maximum retries
                                    "sleep_time": 1.0  # Add 1 second sleep between retries
                                },
                                flags=['sitemap'],
                                errback=self.errback_alternative_link)
                except Exception as e:
                    print("The error is: ", e)
        # Redirection is neither an error (4XX status) nor a success (2XX) if dont_redirect=False, thus we force it
        # We crawl the start URL in order to ensure we didn't miss anything (Even if we used the sitemap)
        else:
            for url in self.start_urls:
                yield Request(url,
                            callback=self.parse_from_start_url if self.scrape_start_urls else self.parse,
                            # If we wan't to crawl (default behavior) without scraping, we still need to let the
                            # crawling spider acknowledge the content by parsing it with the built-in method
                            meta={
                                "alternative_links": DocumentationSpider.to_other_scheme(
                                    url),
                                    "retry_count": 0,  # Initialize retry count
                                    "max_retries": 3,   # Set maximum retries
                                    "sleep_time": 1.0  # Add 1 second sleep between retries
                            },
                            errback=self.errback_alternative_link)

    def add_records(self, response, from_sitemap):
        if 200 <= response.status < 300:  # Check if the response status is 2xx
            self.successfully_indexed += 1  # Increment success counter
        else:
            # Log final failure
            original_url = response.url
            if response.status == 500:
                self.failed_indexing += 1
                self.failed_500_files.append(original_url)
            elif response.status == 404:
                self.failed_indexing += 1
                self.failed_404_files.append(original_url)

        records = self.strategy.get_records_from_response(response)
        self.algolia_helper.add_records(records, response.url, from_sitemap)

        DocumentationSpider.NB_INDEXED += len(records)

        # Arbitrary limit
        if self.nb_hits_max > 0 and DocumentationSpider.NB_INDEXED > self.nb_hits_max:
            DocumentationSpider.NB_INDEXED = 0
            self.reason_to_stop = "Too much hits, DocSearch only handle {} records".format(
                int(self.nb_hits_max))
            raise ValueError(self.reason_to_stop)
            exit(EXIT_CODE_EXCEEDED_RECORDS)

    def remove_records(self):
        if len(self.docs_to_remove) == 0:
            return
        try:
            algolia_client = SearchClient.create(self.app_id, self.api_key)
            algolia_index = algolia_client.init_index(self.index_name)
            delete_objs = []
            for item in self.docs_to_remove:
                print("\033[94m> Deleting: \033[0m " + item['filename'] + ", language: " + item['language'])
                records = algolia_index.browse_objects({
                    'filters': f"slug:'{item['filename']}' AND language:'{item['language']}'",
                    'attributesToRetrieve': ["objectID"]
                })
                objs = list(map(lambda x: x['objectID'], records))
                delete_objs.extend(objs)
            algolia_index.delete_objects(delete_objs)
        except Exception as e:
            print('Error on delete', e)
            pass

    def parse_from_sitemap(self, response):
        if self.reason_to_stop is not None:
            raise CloseSpider(reason=self.reason_to_stop)

        if (not self.force_sitemap_urls_crawling) and (
                not self.is_rules_compliant(response)):
            print("\033[94m> Ignored from sitemap:\033[0m " + response.url)
        else:
            self.add_records(response, from_sitemap=True)
            # We don't return self.parse(response) in order to avoid crawling those web page

    def parse_from_files(self, response):
        if self.reason_to_stop is not None:
            raise CloseSpider(reason=self.reason_to_stop)

        if self.is_rules_compliant(response):
            self.add_records(response, from_sitemap=False)

        else:
            print("\033[94m> Ignored: from start url\033[0m " + response.url)

        return self.parse(response)

    def parse_from_start_url(self, response):
        if self.reason_to_stop is not None:
            raise CloseSpider(reason=self.reason_to_stop)

        if self.is_rules_compliant(response):
            self.add_records(response, from_sitemap=False)

        else:
            print("\033[94m> Ignored: from start url\033[0m " + response.url)

        return self.parse(response)

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
        """
        This error callback will first attempt to retry the failed request up to max_retries.
        If retries are exhausted, it will try alternative_links if there are some left.
        Only for start_urls and sitemap_urls
        """
        if hasattr(failure.value, 'response'):
            if hasattr(failure.value.response, 'status'):
                status = failure.value.response.status
                self.logger.error('------testeeee------ http Status:%s on %s',
                                  status,
                                  failure.value.response.url)
                
                print('running retry condition')

                meta = failure.request.meta
                retry_count = meta.get("retry_count", 0)
                max_retries = meta.get("max_retries", 3)
                sleep_time = meta.get("sleep_time", 1.0)
                
                print('retry_count: %s', retry_count)
                print('max_retries: %s', max_retries)
                print('sleep_time: %s', sleep_time)
    
                # First try retrying the same URL
                if retry_count < max_retries:
                    retry_count += 1
                    print(f'Retrying request ({retry_count}/{max_retries}) after {sleep_time}s sleep: {failure.request.url}')
                    time.sleep(sleep_time)  # Sleep before retry
                    meta["retry_count"] = retry_count
                    yield failure.request.replace(
                        meta=meta
                    )
                    return
    
                # If retries exhausted, try alternative links
                meta["alternative_fallback"] = True
                if len(meta["alternative_links"]) > 0:
                    alternative_link = meta["alternative_links"].pop(0)
                    self.logger.error('Alternative link: %s', alternative_link)
                    # Reset retry count for new alternative link
                    meta["retry_count"] = 0
                    yield failure.request.replace(
                        url=alternative_link,
                        meta=meta
                    )
                else:
                    # Count errors only after retries and alternative links are exhausted
                    self.failed_indexing += 1
                    original_url = meta.get("original_url", "Unknown URL")
                    if status == 500:
                        self.failed_500_files.append(failure.request.url)
                    elif status == 404:
                        self.failed_404_files.append(failure.request.url)
            else:
                self.logger.error('Failure : %s', failure.value)
        else:
            self.logger.error('Failure without response %s', failure.value)

    def __init_sitemap_(self, sitemap_urls, custom_sitemap_rules,
                        sitemap_alternate_links):
        """Init method of a SiteMapSpider @Scrapy"""
        self.sitemap_alternate_links = sitemap_alternate_links
        self.sitemap_urls = sitemap_urls
        self.sitemap_rules = custom_sitemap_rules
        self._cbs = []
        for r, c in self.sitemap_rules:
            if isinstance(c, str):
                c = getattr(self, c)
            self._cbs.append((regex(r), c))
        self._follow = [regex(x) for x in self.sitemap_follow]

    def engine_stopped(self):
        """Print statistics after the spider finishes."""
        print(f"Total files processed: {self.total_files_processed}")
        print(f"Successfully indexed: {self.successfully_indexed}")
        print(f"Failed indexing: {self.failed_indexing}")
        print(f"Files failed with error 500: {self.failed_500_files}")
        print(f"Files failed with error 404: {self.failed_404_files}")
