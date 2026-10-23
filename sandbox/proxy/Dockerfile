# Allow-list proxy: the sandbox's only way out. Only the npm registry is allowed.
FROM alpine:3.24
RUN apk add --no-cache squid
COPY squid.conf /etc/squid/squid.conf
EXPOSE 3128
# -N: stay in the foreground (Docker needs a foreground process)
CMD ["squid", "-N", "-f", "/etc/squid/squid.conf"]
