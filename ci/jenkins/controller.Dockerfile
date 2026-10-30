FROM jenkins/jenkins:2.580.2-jdk25@sha256:415ab90d4e3b25148f7191bc04f455a20817d6c4c3b0a98f6c6b0da4877f7081
COPY --chown=jenkins:jenkins plugins/ /usr/share/jenkins/ref/plugins/
COPY --chown=jenkins:jenkins init.groovy /usr/share/jenkins/ref/init.groovy.d/showcase.groovy
ENV JAVA_OPTS="-Djenkins.install.runSetupWizard=false -Xms256m -Xmx768m"
USER jenkins
