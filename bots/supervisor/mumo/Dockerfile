FROM python:3.10

RUN pip install --no-cache-dir "zeroc-ice<3.8" python-daemon

COPY entrypoint.sh /entrypoint.sh
COPY . /mumo

RUN chmod +x /entrypoint.sh && \
    ln -sf /dev/stdout /mumo/mumo.log

VOLUME ["/data"]

WORKDIR /mumo
ENTRYPOINT [ "/entrypoint.sh" ]

CMD ["/mumo/mumo.py", "-a", "--ini", "/data/mumo.ini"]
