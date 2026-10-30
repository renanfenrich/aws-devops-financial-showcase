pipeline {
  agent { label 'showcase-agent' }
  options { skipDefaultCheckout(true); timestamps(); timeout(time: 20, unit: 'MINUTES') }
  stages {
    stage('Snapshot') {
      steps { sh 'cp -a /snapshot/. "$WORKSPACE/"; cat /snapshot/.source-sha > source-sha.txt' }
    }
    stage('Dependencies') {
      steps { sh 'uv sync --frozen' }
    }
    stage('Shared contracts') {
      steps { sh 'make UV=uv check integration-test infra-test helm-check' }
    }
  }
  post {
    always {
      junit allowEmptyResults: true, testResults: 'artifacts/*junit.xml'
      archiveArtifacts allowEmptyArchive: true, artifacts: 'source-sha.txt,artifacts/*.xml'
    }
  }
}
