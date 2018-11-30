FROM debian:stretch

ADD . /project/enos_openvpn
WORKDIR /project/enos_openvpn

RUN apt-get update
RUN bash template/openvpn_all_in_one.sh 11.8.0.1 127.0.0.1 TRUE 127.0.0.1 127.0.0.1 127.0.0.1 127.0.0.1

