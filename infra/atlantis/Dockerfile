# G1 is tested on Linux amd64; all runtime dependencies are baked in before isolation.
FROM ghcr.io/runatlantis/atlantis:v0.49.0@sha256:389f1c1bf12bd08d647f0383b13cd531e5667a6c654adadf4932d6bf4d5e0c13
USER root
ADD --checksum=sha256:4638628058e71a55212b1c563712eac03b902128f40740f3dc8174df12135061 https://releases.hashicorp.com/terraform/1.17.1/terraform_1.17.1_linux_amd64.zip /tmp/terraform.zip
RUN unzip /tmp/terraform.zip terraform -d /usr/local/bin && rm /tmp/terraform.zip
COPY --chmod=0555 authz.sh /usr/local/bin/showcase-atlantis-authz
COPY --chmod=0555 deny-apply.sh /usr/local/bin/showcase-deny-apply
COPY server.yaml repos.yaml /etc/atlantis/
USER atlantis
CMD ["server", "--config=/etc/atlantis/server.yaml"]
