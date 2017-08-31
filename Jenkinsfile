pipeline {
    agent duffy

    stages {
        stage('Build') {
            steps {
                bash cico_build.sh
            }
        }
        stage('Test') {
            steps {
                bash cico_test.sh
            }
        }
    }
}