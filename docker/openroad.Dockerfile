FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    openroad \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work
ENTRYPOINT ["openroad"]
