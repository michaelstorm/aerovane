FROM ubuntu:14.04

WORKDIR /root
RUN apt-get install -y wget curl unzip
RUN wget "https://releases.hashicorp.com/terraform/0.6.8/terraform_0.6.8_linux_amd64.zip"
RUN unzip terraform_0.6.8_linux_amd64.zip -d /usr/local/bin
RUN rm terraform_0.6.8_linux_amd64.zip

# fixes arrow keys and backspace in insert mode
RUN echo "set nocompatible" >> /root/.vimrc

ADD add_aws_proxy.sh .

ADD aerovane.crt /usr/local/share/ca-certificates
RUN update-ca-certificates

ADD single_micro_instance.tf /root
