FROM alpine:latest

RUN apk add curl
RUN apk add jq
RUN apk add jq
RUN apk add bash
RUN apk add less
RUN apk add vim
RUN apk add coreutils
RUN apk add python3
RUN apk add py3-pip
RUN apk add lsb-release

WORKDIR /home/folio-eureka

COPY folio-dev ./folio-dev/
COPY folio-test ./folio-test/
COPY ./*.yaml .
COPY ./*.json .
COPY ./*.py .
COPY requirements.txt .

# Create venv
RUN python3 -m venv venv
RUN chmod +x venv/bin/activate
RUN source venv/bin/activate
ENV PATH="venv/bin:$PATH"
RUN pip3 install -r requirements.txt


ENV TENANT_DESC="Stanford University Libraries" 
ENV TENANT_ID="sul"