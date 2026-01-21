RUN apt update
RUN apt-get install -y curl
RUN apt-get install -y jq
RUN apt-get install -y bash
RUN apt-get install -y less
RUN apt-get install -y vim
RUN apt-get install -y coreutils
RUN apt-get install -y python3
RUN apt-get install -y python3-requests
RUN apt-get install -y python3-httpx
RUN apt-get install -y lsb-release

WORKDIR /home/folio-eureka

COPY ./*.yaml .
COPY ./*.json .
COPY ./*.txt .
COPY ./*.py .

ENV TENANT_DESC="Stanford University Libraries" 
ENV TENANT_ID="sul"