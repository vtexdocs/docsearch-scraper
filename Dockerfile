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
    python3.7
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
  default-jdk

# https://www.ubuntuupdates.org/package/google_chrome/stable/main/base/google-chrome-stable for references around the latest versions
RUN curl -sS -o - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add
RUN echo "deb [arch=amd64]  http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list

RUN apt-get update -y && apt-get install -yq \
  google-chrome-stable \
  unzip

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
COPY config_md.json config.json
COPY ./utils/webclient.py ./.venv/lib/python3.6/site-packages/scrapy/core/downloader/


ENTRYPOINT ["pipenv", "run", "python", "-m", "src.index"]