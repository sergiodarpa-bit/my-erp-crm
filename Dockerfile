# my-erp-crm: immagine costruita dal sorgente di questo repository.
FROM python:3.12-slim-bookworm

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Librerie di sistema per le dipendenze Python, client PostgreSQL e font per i PDF.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        fonts-dejavu-core \
        fonts-noto-core \
        libffi-dev \
        libjpeg62-turbo-dev \
        libldap2-dev \
        libpq-dev \
        libsasl2-dev \
        libxml2-dev \
        libxslt1-dev \
        postgresql-client \
        xfonts-75dpi \
        xfonts-base \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# wkhtmltopdf (versione con Qt modificato) per stampare preventivi e fatture in PDF.
ARG WKHTMLTOPDF_VERSION=0.12.6.1-3
RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    curl -fsSL -o /tmp/wkhtmltox.deb \
        "https://github.com/wkhtmltopdf/packaging/releases/download/${WKHTMLTOPDF_VERSION}/wkhtmltox_${WKHTMLTOPDF_VERSION}.bookworm_${arch}.deb"; \
    apt-get update; \
    apt-get install -y --no-install-recommends /tmp/wkhtmltox.deb; \
    rm -rf /var/lib/apt/lists/* /tmp/wkhtmltox.deb

WORKDIR /opt/my-erp-crm

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN useradd --system --home-dir /var/lib/my-erp-crm --create-home --shell /usr/sbin/nologin myerp \
    && mkdir -p /etc/my-erp-crm \
    && chown myerp:myerp /var/lib/my-erp-crm

USER myerp
EXPOSE 8069 8072
VOLUME ["/var/lib/my-erp-crm"]

CMD ["/opt/my-erp-crm/my-erp-crm", "--config=/etc/my-erp-crm/my-erp-crm.conf"]
