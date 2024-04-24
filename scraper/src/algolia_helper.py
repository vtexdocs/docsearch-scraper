"""AlgoliaHelper
Wrapper on top of the AlgoliaSearch API client"""

from algoliasearch.search_client import SearchClient

from builtins import range


class AlgoliaHelper:
    """AlgoliaHelper"""

    def __init__(self, app_id, api_key, index_name, index_name_tmp, settings, query_rules, clear_index):
        self.algolia_client = SearchClient.create(app_id, api_key)
        self.index_name = index_name
        self.index_name_tmp = index_name_tmp
        self.algolia_index = self.algolia_client.init_index(self.index_name)


        self.algolia_index_tmp = self.algolia_client.init_index(
            self.index_name_tmp)

        self.clear_index = clear_index

        if self.clear_index:
            """Initialize the tmp-index empty"""
            self.algolia_client.copy_rules(
                self.index_name,
                self.index_name_tmp
            )
            self.algolia_index_tmp.set_settings(settings)
            if len(query_rules) > 0:
                self.algolia_index_tmp.save_rules(query_rules, True, True)
        else:
            """Initialize the tmp-index with an copy of curr index content"""
            self.algolia_client.copy_index(index_name, index_name_tmp)


    def add_records(self, records, url, from_sitemap):
        """Add new records to the temporary index"""
        record_count = len(records)

        for i in range(0, record_count, 50):
            self.algolia_index_tmp.save_objects(records[i:i + 50])

        color = "96" if from_sitemap else "94"

        print(
            '\033[{}m> DocSearch: \033[0m{}\033[93m {} records\033[0m)'.format(
                color, url, record_count))

    def add_synonyms(self, synonyms):
        synonyms_list = []
        for _, value in list(synonyms.items()):
            synonyms_list.append(value)

        self.algolia_index_tmp.save_synonyms(synonyms_list)
        print(
            '\033[94m> DocSearch: \033[0m Synonyms (\033[93m{} synonyms\033[0m)'.format(
                len(synonyms_list)))

    def commit_tmp_index(self):
        """Clear index (if needed) after all scraping to prevent search break on production"""
        if self.clear_index:
            try:
                print("Cleaning index")

                self.algolia_index.clear_objects()

                print("Index Clean!")
            except Exception:
                print("Couldn't clear index records")
        """Overwrite the real index with the temporary one"""
        self.algolia_client.move_index(self.index_name_tmp, self.index_name)
