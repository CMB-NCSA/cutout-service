FROM python:3.13.5 AS mc

RUN curl https://dl.min.io/client/mc/release/linux-amd64/mc \
    -o /usr/local/bin/mc && \
    chmod +x /usr/local/bin/mc

FROM python:3.13.5 AS deps

RUN apt-get update && DEBIAN_FRONTEND=noninteractive && \
    apt-get install -y --no-install-recommends \
    libtiff-dev \
    libjpeg-dev \
    imagemagick \
    gcc \
    && rm -rf /var/lib/apt/list/*

COPY ./requirements.base.txt /requirements.txt
RUN pip install -r /requirements.txt --no-cache-dir

FROM python:3.13.5 AS cutter

COPY ./requirements.cutter.txt /requirements.txt
RUN pip install -r /requirements.txt --no-cache-dir

RUN git clone https://github.com/CMB-NCSA/stiff.git  && \
    cd stiff && \
    ./configure --prefix=/usr/local && \
    make && \
    make install

# Install des_cutter
# ARG DES_CUTTER_VERSION=1.0.0
# RUN git clone https://github.com/CMB-NCSA/des_cutter -b $DES_CUTTER_VERSION /tmp/des_cutter
ARG DES_CUTTER_COMMIT=v1.0.3
RUN git clone https://github.com/CMB-NCSA/des_cutter /tmp/des_cutter && \
    cd /tmp/des_cutter && \
    git checkout $DES_CUTTER_COMMIT && \
    pip install . --no-deps --break-system-packages

FROM python:3.13.5

ARG UID=1000
ARG USERNAME=app
ARG APP_ROOT_DIR=/opt

RUN useradd --create-home --shell /bin/bash ${USERNAME} --uid ${UID}

COPY --from=mc /usr/local/bin/mc /usr/local/bin/mc
COPY --from=deps /usr/local/bin/ /usr/local/bin/
COPY --from=deps /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --from=cutter /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --from=cutter /usr/local/bin/ /usr/local/bin/
COPY --from=cutter /tmp/des_cutter/etc/ /etc/

## Create application base directory
RUN mkdir -p ${APP_ROOT_DIR} && chown ${UID} -R ${APP_ROOT_DIR}
USER ${USERNAME}

WORKDIR ${APP_ROOT_DIR}
COPY --chown=${USERNAME}:${USERNAME} . ./app
WORKDIR ${APP_ROOT_DIR}/app
