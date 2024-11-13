FROM ubuntu:18.04
LABEL maintainer="test@vtexlab.com"
WORKDIR /root

# Install selenium
ENV LC_ALL C
ENV DEBIAN_FRONTEND noninteractive
ENV DEBCONF_NONINTERACTIVE_SEEN true

RUN useradd -d /home/seleuser -m seleuser
RUN chown -R seleuser /home/seleuser
RUN chgrp -R seleuser /home/seleuser

RUN apt-get update -y && apt-get install -yq \
    software-properties-common\
    python3.6
RUN add-apt-repository -y ppa:openjdk-r/ppa
RUN apt-get update -y && apt-get install -yq \
    curl \
    wget \
    sudo \
    gnupg \
    && curl -sL https://deb.nodesource.com/setup_8.x | sudo bash -
RUN apt-get update -y && apt-get install -yq \
    nodejs -yq
RUN apt-get update -y && apt-get install -yq \
  unzip \
  xvfb \
  libxi6 \
  libgconf-2-4 \
  default-jdk \
  ca-certificates \
  fonts-liberation \
  libappindicator3-1 \
  libasound2 \
  libatk-bridge2.0-0 \
  libatspi2.0-0 \
  libcups2 \
  libdbus-glib-1-2 \
  libgbm1 \
  libnspr4 \
  libnss3 \
  libxss1 \
  xdg-utils 

# https://www.ubuntuupdates.org/package/google_chrome/stable/main/base/google-chrome-stable for references around the latest versions
RUN curl -sS -o - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add
# Download and unzip specific Chrome version
# For more information, see https://developer.chrome.com/docs/chromedriver/downloads/version-selection?hl=pt-br
# and https://stackoverflow.com/questions/54927496/how-to-download-older-versions-of-chrome-from-a-google-official-site

RUN apt-get update -y && apt-get install -yq \
    wget \
    unzip \
    && wget -q -O /tmp/chrome-linux.zip https://commondatastorage.googleapis.com/chromium-browser-snapshots/Linux_x64/1146059/chrome-linux.zip \
    && unzip /tmp/chrome-linux.zip -d /opt \
    && ln -s /opt/chrome-linux/chrome /usr/bin/google-chrome \
    && rm /tmp/chrome-linux.zip \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN apt-get clean && rm -rf /var/lib/apt/lists/*

ENV chromedriverStableVersion=114.0.5735.90
RUN wget -q "https://chromedriver.storage.googleapis.com/${chromedriverStableVersion}/chromedriver_linux64.zip"


RUN unzip chromedriver_linux64.zip

RUN mv chromedriver /usr/bin/chromedriver
RUN chown root:root /usr/bin/chromedriver
RUN chmod +x /usr/bin/chromedriver

RUN wget -q https://selenium-release.storage.googleapis.com/3.13/selenium-server-standalone-3.13.0.jar
RUN wget -q http://www.java2s.com/Code/JarDownload/testng/testng-6.8.7.jar.zip
RUN unzip testng-6.8.7.jar.zip

# Install DocSearch dependencies

COPY Pipfile .
COPY Pipfile.lock .

ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8
ENV PIPENV_HIDE_EMOJIS 1
RUN apt-get update -y && apt-get install -yq \
    python3-pip
RUN pip3 install pipenv==2018.11.26
RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --python 3.6

ENV APPLICATION_ID A4TXCBOC74
ENV API_KEY 1da0649a869d5dca609b2b5421472209
ENV CHROMEDRIVER_PATH /usr/bin/chromedriver

WORKDIR /root
COPY ./scraper/src ./src
# Change config file here
COPY configs/scraper_openapi.json config.json
COPY ./utils/webclient.py ./.venv/lib/python3.6/site-packages/scrapy/core/downloader/


ENTRYPOINT ["pipenv", "run", "python", "-m", "src.index"]