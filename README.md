# DocSearch scraper

## 

This repository is a fork of the [DocSearch Scraper](https://github.com/algolia/docsearch-scraper) and its goal is to update it with any necessary changes to make the crawler run and get all elements inside of shadow DOM.

## Installation and Usage

### Dependencies
- python 3.6
- pip
- Specific version of pipenv
  ```bash
  pip3 install pipenv==2018.11.26
  ```

### &rarr; Installation to **STATIC PAGES**
**(1)** Clone this repository

**(2)** Create your `config.json` file with everything you need extracted from your pages by the crawler.

**(3)** Create your .env file with:
  - `APPLICATION_ID`: The ID of the application you want to store the crawler extractions in.
  - `API_KEY`: API key for your targeted application. Make sure to use an API key with write access to your index. It needs the ACL addObject, editSettings and deleteIndex.

**(4)** Install and create the isolated environment
  ```bash
  pipenv install
  ```

**(5)** Copy the contents of the `utils/webclient.py` file in this repository and paste it in the `webclient.py` file inside the directory of `scrapy` where the project dependencies were installed, located at `virtualenvs/created-environment/lib/python3.6/site-packages/scrapy/core/downloader/webclient.py`

**(6)** Turn on your project with
  ```bash
  pipenv shell
  ```

**(7)** So, in the shell prompt, put:
  ```bash
  ./docsearch run ./path/to/your/config.json
  ```

### &rarr; Installation to **CLIENT-SIDE PAGES**
In the case of Client-Side Rendering, we need one more step in this configuration. First, `"js_render": true` is required in the config file. So that the crawler knows that the page will not be static. Also, the `"js_wait"` attribute will define how long the crawler should wait for the page to load (in seconds).

#### Below, only the different steps compared to the previous case:

**(3)** Some websites rendering require JavaScript. Our crawler relies on a headless chrome emulation. You will need to set up a ChromeDriver.
[Install the driver](https://chromedriver.chromium.org/getting-started) suited to your OS and the version of your Chrome. We do recommend to use the latest version.

**(3.5)** Create your .env file with:
  - `APPLICATION_ID`: The ID of the application you want to store the crawler extractions in.
  - `API_KEY`: API key for your targeted application. Make sure to use an API key with write access to your index. It needs the ACL addObject, editSettings and deleteIndex.
  - `CHROMEDRIVER_PATH`: Put the path that targets the downloaded extracted driver.

## Useful links

- [Documentation](https://docsearch.algolia.com/)
- [Config file Docs](https://docsearch.algolia.com/docs/legacy/config-file/)
- [Run your own](https://docsearch.algolia.com/docs/legacy/run-your-own/)
- [DocSearch UI](https://github.com/algolia/docsearch)